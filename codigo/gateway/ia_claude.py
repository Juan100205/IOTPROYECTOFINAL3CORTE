"""Módulo de IA del gateway: predicción, anomalías y recomendación.

Dos capas:
  1. Base estadística local (siempre disponible, sin internet):
     regresión lineal del nivel en la última hora -> horas hasta el
     nivel crítico. Sirve de respaldo y de referencia para la IA.
  2. Claude (API de Anthropic): recibe el resumen por minuto de las
     últimas 2 h, los eventos recientes y la base estadística, y
     devuelve un JSON validado con riesgo, horas estimadas, anomalía
     y una recomendación corta para las autoridades.
Si no hay API key o la llamada falla, se usa solo la capa 1.
"""
import json
import logging
import time

log = logging.getLogger("ia")

try:
    import anthropic
except ImportError:  # el gateway funciona igual sin la librería
    anthropic = None

# Modelos que aceptan el respaldo automático del servidor ante un rechazo
MODELOS_CON_FALLBACK = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}

ESQUEMA = {
    "type": "object",
    "properties": {
        "riesgo": {"type": "string", "enum": ["bajo", "medio", "alto", "critico"]},
        "horas_hasta_critico": {"anyOf": [{"type": "number"}, {"type": "null"}]},
        "anomalia": {"type": "boolean"},
        "tipo_anomalia": {"type": "string"},
        "explicacion": {"type": "string"},
        "recomendacion": {"type": "string"},
        "acciones": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["riesgo", "horas_hasta_critico", "anomalia", "tipo_anomalia",
                 "explicacion", "recomendacion", "acciones"],
    "additionalProperties": False,
}

SISTEMA = """Eres el módulo de análisis de WaterGuard, un sistema IoT que vigila un tanque \
de almacenamiento de agua en la región Sabana Centro (Cundinamarca, Colombia) durante \
el Fenómeno de El Niño. Tus lectores son autoridades locales (alcaldía, gestión del \
riesgo) que deciden racionamientos.

Recibes el resumen por minuto de las últimas horas (nivel en %, temperaturas, humedad, \
presión, luminosidad, índice de evaporación potencial 0-100 e índice de riesgo hídrico \
IRH 0-100 calculado en el dispositivo), los eventos recientes y una estimación \
estadística por regresión lineal.

Tu trabajo:
- Estimar en cuántas horas el nivel llegará al umbral crítico. Usa la tendencia real de \
los datos; corrige la regresión si ves que el descenso se acelera o se frena (por \
ejemplo, más evaporación al mediodía). Si el nivel no baja, devuelve null.
- Detectar anomalías: descensos bruscos que no explica la evaporación (posible fuga o \
consumo excesivo), sensores con valores imposibles o congelados, o el patrón "descenso \
anómalo con calor extremo".
- Clasificar el riesgo: bajo, medio, alto o critico.
- Escribir una recomendación concreta y accionable para la autoridad, en español, de \
máximo 120 caracteres (se muestra en una pantalla pequeña).
- En "acciones", de 1 a 4 acciones concretas (racionamiento por horarios, inspección de \
fugas, revisión de un sensor, aviso a la comunidad, etc.).
- En "explicacion", 2 o 3 frases con los datos que justifican tu conclusión.
Si hay pocos datos, dilo en la explicación y sé prudente con el riesgo. Los datos del \
prototipo pueden estar acelerados (tanque pequeño, demostración de minutos): razona \
con las tasas tal como vienen."""


# ---------------------------------------------------------------- base estadística
def regresion(puntos):
    """puntos: [(t_horas, valor)] -> pendiente por hora (mínimos cuadrados)."""
    n = len(puntos)
    if n < 3:
        return None
    mx = sum(p[0] for p in puntos) / n
    my = sum(p[1] for p in puntos) / n
    sxx = sum((p[0] - mx) ** 2 for p in puntos)
    if sxx == 0:
        return None
    return sum((p[0] - mx) * (p[1] - my) for p in puntos) / sxx


def base_estadistica(resumen, nivel_critico):
    pts = [(r["minuto"] / 3_600_000, r["nivel"]) for r in resumen if r["nivel"] is not None]
    if len(pts) < 3:
        return {"datos": len(pts), "nivel_actual": pts[-1][1] if pts else None,
                "tasa_pct_h": None, "horas_hasta_critico": None}
    ultima_hora = [p for p in pts if p[0] >= pts[-1][0] - 1]
    tasa = regresion(ultima_hora if len(ultima_hora) >= 3 else pts)
    actual = pts[-1][1]
    horas = None
    if tasa is not None and tasa < -0.05 and actual > nivel_critico:
        horas = round((actual - nivel_critico) / -tasa, 1)
    elif actual <= nivel_critico:
        horas = 0.0
    return {"datos": len(pts), "nivel_actual": actual,
            "tasa_pct_h": None if tasa is None else round(tasa, 2),
            "horas_hasta_critico": horas}


def respuesta_estadistica(base, irh_actual):
    """Respuesta de respaldo con reglas simples cuando no hay IA."""
    h = base["horas_hasta_critico"]
    irh = irh_actual or 0
    if (h is not None and h <= 2) or irh >= 70:
        riesgo, rec = "critico", "Activar racionamiento inmediato e inspeccionar fugas"
    elif (h is not None and h <= 12) or irh >= 30:
        riesgo, rec = "alto", "Programar racionamiento por horarios y avisar a la comunidad"
    elif h is not None and h <= 48:
        riesgo, rec = "medio", "Vigilar consumo; preparar plan de racionamiento"
    else:
        riesgo, rec = "bajo", "Operación normal; mantener monitoreo"
    return {
        "riesgo": riesgo, "horas_hasta_critico": h, "anomalia": False, "tipo_anomalia": "",
        "explicacion": f"Estimación estadística: tasa {base['tasa_pct_h']} %/h con {base['datos']} minutos de datos.",
        "recomendacion": rec, "acciones": [rec],
    }


# ---------------------------------------------------------------- Claude
class ModuloIA:
    def __init__(self, cfg):
        self.cfg = cfg
        self.cliente = None
        if cfg["ia_activa"] and anthropic is not None and cfg["anthropic_key"]:
            self.cliente = anthropic.Anthropic(api_key=cfg["anthropic_key"], timeout=120.0, max_retries=2)
        elif cfg["ia_activa"]:
            log.warning("IA sin API key o sin librería 'anthropic': se usará solo la base estadística")

    def analizar(self, resumen, eventos):
        """Devuelve (fuente, respuesta_dict)."""
        base = base_estadistica(resumen, self.cfg["nivel_critico"])
        irh = next((r["irh"] for r in reversed(resumen) if r["irh"] is not None), None)
        if self.cliente is None or base["datos"] < 3:
            return "estadistico", respuesta_estadistica(base, irh)
        try:
            return "claude", self._preguntar_claude(resumen, eventos, base)
        except Exception as e:  # cualquier falla -> respaldo, nunca tumbar el gateway
            log.error("IA: fallo la consulta a Claude (%s); se usa la base estadística", e)
            return "estadistico", respuesta_estadistica(base, irh)

    def _preguntar_claude(self, resumen, eventos, base):
        datos = {
            "tanque": {"capacidad_litros": self.cfg["tanque_litros"],
                       "umbral_critico_pct": self.cfg["nivel_critico"]},
            "hora_local": time.strftime("%Y-%m-%d %H:%M"),
            "estimacion_estadistica": base,
            "eventos_recientes": [
                {"hace_min": round((time.time() * 1000 - e["ts"]) / 60000), "tipo": e["tipo"], "msg": e["msg"]}
                for e in eventos],
            "resumen_por_minuto": [
                {k: v for k, v in r.items() if k != "minuto"} | {
                    "hace_min": round((time.time() * 1000 - r["minuto"]) / 60000)}
                for r in resumen],
        }
        kwargs = dict(
            model=self.cfg["ia_modelo"],
            max_tokens=8000,
            system=SISTEMA,
            messages=[{"role": "user", "content": "Datos del tanque (JSON):\n" +
                       json.dumps(datos, ensure_ascii=False)}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA}},
        )
        if self.cfg["ia_modelo"] in MODELOS_CON_FALLBACK:
            # Si el modelo rechaza la solicitud, el servidor la reintenta con otro modelo
            resp = self.cliente.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
        else:
            resp = self.cliente.messages.create(**kwargs)

        if resp.stop_reason == "refusal":
            raise RuntimeError("el modelo rechazó la solicitud")
        if resp.stop_reason == "max_tokens":
            raise RuntimeError("respuesta cortada por max_tokens")
        texto = next(b.text for b in resp.content if b.type == "text")
        r = json.loads(texto)
        r["recomendacion"] = r["recomendacion"][:120]
        log.info("IA (%s): riesgo=%s horas=%s tokens in/out=%s/%s", resp.model, r["riesgo"],
                 r["horas_hasta_critico"], resp.usage.input_tokens, resp.usage.output_tokens)
        return r
