"""Tablero 'WaterGuard · Monitoreo hídrico' para ThingsBoard 4.x.

Parte de la configuración por defecto de cada widget (pedida al propio
ThingsBoard, así sirve aunque cambie la versión) y le aplica los datos,
colores y textos de WaterGuard / LeMarTek Cloud.
"""
import copy
import json
import urllib.parse
import uuid

# Paleta LeMarTek Cloud
AZUL_NOCHE = "#0B2545"
AZUL_AGUA = "#1B98E0"
TURQUESA = "#13C4A3"
AMBAR = "#F2A541"
ROJO = "#E5484D"
TINTA = "#1E293B"
SUAVE = "#64748B"
FONDO = "#EEF3F8"

LOGO = ("data:image/svg+xml;base64,"
        "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyMjAgNDgiPjxkZWZzPjxs"
        "aW5lYXJHcmFkaWVudCBpZD0iZyIgeDE9IjAiIHkxPSIwIiB4Mj0iMCIgeTI9IjEiPjxzdG9wIG9mZnNldD0iMCIgc3Rv"
        "cC1jb2xvcj0iIzM3QjZGRiIvPjxzdG9wIG9mZnNldD0iMSIgc3RvcC1jb2xvcj0iIzBCNkJDQiIvPjwvbGluZWFyR3Jh"
        "ZGllbnQ+PC9kZWZzPjxwYXRoIGQ9Ik0yNCA0QzI0IDQgMTAgMjAgMTAgMjlhMTQgMTQgMCAwIDAgMjggMEMzOCAyMCAy"
        "NCA0IDI0IDR6IiBmaWxsPSJ1cmwoI2cpIi8+PHBhdGggZD0iTTE3IDMwYTcgNyAwIDAgMCA3IDciIHN0cm9rZT0iI2Zm"
        "ZiIgc3Ryb2tlLXdpZHRoPSIzIiBmaWxsPSJub25lIiBzdHJva2UtbGluZWNhcD0icm91bmQiLz48dGV4dCB4PSI0OCIg"
        "eT0iMjYiIGZvbnQtZmFtaWx5PSJSb2JvdG8sQXJpYWwsc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxOSIgZm9udC13ZWln"
        "aHQ9IjcwMCIgZmlsbD0iIzBCMjU0NSI+V2F0ZXJHdWFyZDwvdGV4dD48dGV4dCB4PSI0OCIgeT0iNDEiIGZvbnQtZmFt"
        "aWx5PSJSb2JvdG8sQXJpYWwsc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxMCIgbGV0dGVyLXNwYWNpbmc9IjEuNSIgZmls"
        "bD0iIzY0NzQ4QiI+TEVNQVJURUsgQ0xPVUQgRk9SIElPVDwvdGV4dD48L3N2Zz4=")

CSS_TABLERO = f"""
.tb-widget-container > .tb-widget {{ border-radius: 16px !important; box-shadow: 0 1px 2px rgba(15,23,42,.06), 0 8px 24px rgba(15,23,42,.06) !important; }}
.tb-dashboard-page .tb-dashboard-toolbar {{ background: transparent; }}
"""


class Constructor:
    def __init__(self, tb, device_id):
        self.tb = tb
        self.alias = str(uuid.uuid4())
        self.device_id = device_id
        self.widgets = {}
        self.layout = {}
        self._cache = {}

    # -------------------------------------------------------- base
    def defecto(self, fqn):
        if fqn not in self._cache:
            if not hasattr(self, "_ids"):
                res = self.tb.req("GET", "/api/widgetTypes?pageSize=2000&page=0")
                self._ids = {w["fqn"]: w["id"]["id"] for w in res["data"]}
            wid = self._ids[fqn]
            d = self.tb.req("GET", f"/api/widgetType/{wid}")["descriptor"]
            self._cache[fqn] = (d["type"], json.loads(d["defaultConfig"]))
        tipo, cfg = self._cache[fqn]
        return tipo, copy.deepcopy(cfg)

    def clave(self, nombre, etiqueta=None, color=AZUL_AGUA, unidades=None, decimales=None, **extra):
        k = {"name": nombre, "type": "timeseries", "label": etiqueta or nombre, "color": color,
             "settings": {}, "_hash": abs(hash(nombre)) / 1e19, "units": unidades, "decimals": decimales}
        k.update(extra)
        return k

    def ds(self, claves, latest=None):
        d = {"type": "entity", "name": None, "entityAliasId": self.alias, "filterId": None, "dataKeys": claves}
        if latest is not None:
            d["latestDataKeys"] = latest
        return [d]

    def agregar(self, fqn, x, y, w, h, cfg_mod):
        tipo, cfg = self.defecto(fqn)
        cfg.update({"showTitle": True, "dropShadow": True, "backgroundColor": "#FFFFFF",
                    "titleFont": {"size": 15, "sizeUnit": "px", "family": "Roboto", "weight": "600",
                                  "style": "normal", "lineHeight": "22px"},
                    "titleColor": TINTA, "borderRadius": "16px", "padding": "12px",
                    "enableFullscreen": False})
        cfg_mod(cfg)
        wid = str(uuid.uuid4())
        self.widgets[wid] = {"id": wid, "typeFullFqn": "system." + fqn, "type": tipo,
                             "sizeX": w, "sizeY": h, "row": y, "col": x, "config": cfg}
        self.layout[wid] = {"sizeX": w, "sizeY": h, "row": y, "col": x}
        return wid

    # -------------------------------------------------------- widgets
    def banner_estado(self, x, y, w, h):
        fn = r"""
var d = (data && data.length) ? data[0] : {};
var e = d['estado'] || '';
var M = {
  NORMAL:    ['#0F9D74', '#E7F8F1', 'Operación normal', 'El suministro está dentro de los rangos esperados.'],
  ALERTA:    ['#C27C0E', '#FFF5E1', 'Vigilancia reforzada', 'Se detectó una condición de riesgo. Revise la recomendación.'],
  CRITICO:   ['#D92D3A', '#FDECEE', 'Acción inmediata', 'Riesgo crítico de desabastecimiento: active el plan de contingencia.'],
  DEGRADADO: ['#5B61D6', '#EEF0FF', 'Sensores sin confirmar', 'Algunas lecturas no son confiables; el sistema sigue vigilando.'],
  ERROR:     ['#D92D3A', '#FDECEE', 'Falla de sensores', 'El nodo no recibe datos de sus sensores.']
};
var m = M[e] || ['#64748B', '#F1F5F9', 'Esperando datos', 'Aún no llegan datos del nodo WaterGuard.'];
function num(v, dec) { return (v === undefined || v === null || v === '' || isNaN(Number(v))) ? '--' : Number(v).toFixed(dec); }
var online = String(d['nodo_online']) !== 'false';
var sonando = String(d['alarma_sonando']) === 'true';
var silenciada = String(d['alarma_silenciada']) === 'true';
var chip = sonando ? '<span class="chip on">🔔 Alarma sonando en sitio</span>'
         : (silenciada ? '<span class="chip">🔕 Alarma silenciada</span>' : '<span class="chip">Alarma en espera</span>');
var nodo = online ? '<span class="chip ok">● Nodo en línea</span>' : '<span class="chip off">● Nodo sin conexión</span>';
return '<div class="wg" style="--c:' + m[0] + ';--f:' + m[1] + '">' +
  '<div class="izq"><div class="eti">Estado del sistema</div>' +
  '<div class="est">' + (e || '—') + '</div><div class="tit">' + m[2] + '</div>' +
  '<div class="txt">' + m[3] + '</div><div class="chips">' + nodo + chip + '</div></div>' +
  '<div class="der"><div class="kpi"><span>' + num(d['irh'], 0) + '</span><small>Riesgo hídrico (IRH)</small></div>' +
  '<div class="kpi"><span>' + num(d['nivel'], 0) + '<i>%</i></span><small>Nivel del tanque</small></div>' +
  '<div class="kpi"><span>' + num(d['tasa_h'], 1) + '<i>%/h</i></span><small>Tendencia (gateway)</small></div></div></div>';
"""
        css = """
.wg{height:100%;box-sizing:border-box;display:flex;gap:16px;align-items:stretch;justify-content:space-between;
    background:var(--f);border-left:8px solid var(--c);border-radius:14px;padding:16px 20px;font-family:Roboto,sans-serif}
.wg .eti{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#64748B;font-weight:600}
.wg .est{font-size:40px;line-height:1.05;font-weight:800;color:var(--c);margin-top:4px}
.wg .tit{font-size:17px;font-weight:700;color:#1E293B;margin-top:2px}
.wg .txt{font-size:13px;color:#475569;margin-top:4px;max-width:420px}
.wg .chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.wg .chip{font-size:12px;font-weight:600;padding:4px 10px;border-radius:999px;background:#fff;color:#334155;border:1px solid #E2E8F0}
.wg .chip.on{background:#D92D3A;color:#fff;border-color:#D92D3A}
.wg .chip.ok{color:#0F9D74}.wg .chip.off{color:#D92D3A}
.wg .der{display:flex;gap:10px;align-items:center}
.wg .kpi{background:#fff;border-radius:12px;padding:10px 14px;min-width:92px;text-align:center;box-shadow:0 1px 2px rgba(15,23,42,.06)}
.wg .kpi span{display:block;font-size:28px;font-weight:800;color:#0B2545}
.wg .kpi i{font-style:normal;font-size:13px;color:#64748B;margin-left:2px}
.wg .kpi small{display:block;font-size:11px;color:#64748B;margin-top:2px}
@media (max-width: 700px){.wg{flex-direction:column}.wg .der{flex-wrap:wrap}}
"""
        claves = [self.clave(k) for k in ("estado", "irh", "nivel", "tasa_h", "nodo_online",
                                          "alarma_sonando", "alarma_silenciada")]

        def mod(c):
            c.update({"datasources": self.ds(claves), "showTitle": False, "padding": "0px",
                      "backgroundColor": "rgba(0,0,0,0)", "dropShadow": False})
            c["settings"].update({"useMarkdownTextFunction": True, "markdownTextFunction": fn,
                                  "applyDefaultMarkdownStyle": False, "markdownCss": css})
        return self.agregar("cards.markdown_card", x, y, w, h, mod)

    def tarjeta_ia(self, x, y, w, h):
        fn = r"""
var d = (data && data.length) ? data[0] : {};
var r = d['ia_riesgo'] || '';
var C = {bajo:'#0F9D74', medio:'#C27C0E', alto:'#E8590C', critico:'#D92D3A'};
var c = C[r] || '#64748B';
var h = d['ia_horas_critico'];
var horas = (h === undefined || h === null || h === '' || isNaN(Number(h))) ? 'Sin descenso proyectado'
          : (Number(h) <= 0 ? 'Nivel crítico alcanzado' : 'Nivel crítico en ~' + Number(h).toFixed(1) + ' h');
var anom = String(d['ia_anomalia']) === 'true' ? '<span class="tag">⚠ Anomalía detectada</span>' : '';
var fuente = d['ia_fuente'] === 'claude' ? 'Claude (Anthropic)' : (d['ia_fuente'] ? 'Modelo estadístico local' : '—');
return '<div class="ia"><div class="top"><div><div class="eti">Asistente IA</div>' +
  '<div class="rie" style="color:' + c + '">Riesgo ' + (r ? r.toUpperCase() : '—') + '</div></div>' +
  '<div class="hor">' + horas + '</div></div>' + anom +
  '<div class="rec">' + (d['ia_recomendacion'] || 'Esperando el primer análisis del gateway…') + '</div>' +
  '<div class="exp">' + (d['ia_explicacion'] || '') + '</div>' +
  '<div class="pie">Motor: ' + fuente + '</div></div>';
"""
        css = """
.ia{height:100%;box-sizing:border-box;display:flex;flex-direction:column;gap:6px;padding:16px 18px;font-family:Roboto,sans-serif;
    background:linear-gradient(135deg,#0B2545 0%,#13315C 60%,#134074 100%);border-radius:14px;color:#E2E8F0;overflow:auto}
.ia .top{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.ia .eti{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#8DA9C4;font-weight:600}
.ia .rie{font-size:24px;font-weight:800;margin-top:2px;filter:brightness(1.35)}
.ia .hor{font-size:13px;font-weight:600;background:rgba(255,255,255,.1);padding:6px 10px;border-radius:10px;white-space:nowrap}
.ia .tag{align-self:flex-start;font-size:12px;font-weight:700;background:#E8590C;color:#fff;padding:3px 10px;border-radius:999px}
.ia .rec{font-size:16px;font-weight:600;color:#fff;line-height:1.35}
.ia .exp{font-size:12.5px;color:#B6C6D8;line-height:1.45}
.ia .pie{margin-top:auto;font-size:11px;color:#8DA9C4}
"""
        claves = [self.clave(k) for k in ("ia_riesgo", "ia_horas_critico", "ia_anomalia", "ia_recomendacion",
                                          "ia_explicacion", "ia_fuente")]

        def mod(c):
            c.update({"datasources": self.ds(claves), "showTitle": False, "padding": "0px",
                      "backgroundColor": "rgba(0,0,0,0)", "dropShadow": False})
            c["settings"].update({"useMarkdownTextFunction": True, "markdownTextFunction": fn,
                                  "applyDefaultMarkdownStyle": False, "markdownCss": css})
        return self.agregar("cards.markdown_card", x, y, w, h, mod)

    def boton_rpc(self, x, y, w, h, texto, metodo, primario):
        css = (".tb-rpc-button, button{width:100%!important;height:100%!important;border-radius:12px!important;"
               "font-weight:700!important;font-size:15px!important;letter-spacing:.02em}")

        def mod(c):
            c.update({"targetDeviceAliases": [self.alias], "targetDeviceAliasIds": [self.alias],
                      "targetDevice": {"type": "entity", "entityAliasId": self.alias},
                      "showTitle": False, "padding": "4px",
                      "backgroundColor": "#FFFFFF", "widgetCss": css})
            c["settings"].update({"requestTimeout": 8000, "oneWayElseTwoWay": False, "buttonText": texto,
                                  "methodName": metodo, "methodParams": "{}",
                                  "styleButton": {"isRaised": True, "isPrimary": primario,
                                                  "bgColor": ROJO if primario else None,
                                                  "textColor": "#FFFFFF" if primario else None}})
        return self.agregar("control_widgets.rpcbutton", x, y, w, h, mod)

    def tanque(self, x, y, w, h):
        rango = lambda a, b, cc: [{"from": None, "to": 15, "color": a}, {"from": 15, "to": 30, "color": b},
                                  {"from": 30, "to": None, "color": cc}]

        def mod(c):
            c.update({"datasources": self.ds([self.clave("nivel", "Nivel", AZUL_AGUA, "%", 0)]),
                      "title": "Nivel del tanque", "showTitleIcon": True, "titleIcon": "water_drop",
                      "iconColor": AZUL_AGUA})
            s = c["settings"]
            s.update({"volumeConstant": 1000, "volumeUnits": "L", "units": "%", "layout": "percentage"})
            s["liquidColor"] = {"type": "range", "color": AZUL_AGUA,
                                "rangeList": rango("#F07C82", "#F6C177", "#4FB3F0")}
            s["tankColor"] = {"type": "range", "color": AZUL_NOCHE,
                              "rangeList": rango(ROJO, AMBAR, AZUL_NOCHE)}
            s["valueColor"] = {"type": "range", "color": TINTA,
                               "rangeList": rango(ROJO, "#B7791F", AZUL_NOCHE)}
        return self.agregar("vertical_cylinder_tank", x, y, w, h, mod)

    def tarjeta(self, x, y, w, h, clave, titulo, unidades, dec, icono, color):
        def mod(c):
            c.update({"datasources": self.ds([self.clave(clave, titulo, color, unidades, dec)],
                                             latest=[self.clave(clave, titulo, color, unidades, dec)]),
                      "title": titulo, "units": unidades, "decimals": dec, "showTitleIcon": True,
                      "titleIcon": icono, "iconColor": color, "useDashboardTimewindow": True})
            c["settings"]["valueColor"] = {"type": "constant", "color": AZUL_NOCHE}
            c["settings"]["autoScale"] = True
            c["settings"]["valueFont"] = {"family": "Roboto", "size": 30, "sizeUnit": "px", "style": "normal",
                                          "weight": "700", "lineHeight": "34px"}
            c["settings"]["background"] = {"type": "color", "color": "#FFFFFF",
                                           "overlay": {"enabled": False, "color": "rgba(255,255,255,0.72)", "blur": 3}}
        return self.agregar("simple_value_and_chart_card", x, y, w, h, mod)

    def grafica(self, x, y, w, h, titulo, icono, claves, umbrales=None):
        def mod(c):
            c.update({"datasources": self.ds(claves), "title": titulo, "showTitleIcon": True,
                      "titleIcon": icono, "iconColor": AZUL_AGUA, "useDashboardTimewindow": True,
                      "enableFullscreen": True})
            s = c["settings"]
            s["legendConfig"].update({"showAvg": False, "showLatest": True, "showMin": True, "showMax": True})
            if umbrales:
                s["thresholds"] = umbrales
        return self.agregar("time_series_chart", x, y, w, h, mod)

    def alarmas(self, x, y, w, h):
        def mod(c):
            c["alarmSource"]["type"] = "entity"
            c["alarmSource"]["entityAliasId"] = self.alias
            etiquetas = {"createdTime": "Fecha", "originator": "Origen", "type": "Alarma",
                         "severity": "Severidad", "status": "Estado", "assignee": "Responsable"}
            for k in c["alarmSource"]["dataKeys"]:
                k["label"] = etiquetas.get(k["name"], k["label"])
            c.update({"title": "Alarmas", "showTitleIcon": True, "titleIcon": "notifications_active",
                      "iconColor": ROJO, "alarmSearchStatus": "ANY",
                      "timewindow": {"realtime": {"interval": 1000, "timewindowMs": 7 * 86400000},
                                     "aggregation": {"type": "NONE", "limit": 200}}})
            c["settings"]["alarmsTitle"] = "Alarmas"
        return self.agregar("alarm_widgets.alarms_table", x, y, w, h, mod)

    def eventos(self, x, y, w, h):
        def mod(c):
            c["datasources"] = self.ds([self.clave("evento", "Evento", AZUL_NOCHE,
                                                   settings={"useCellStyleFunction": False,
                                                             "useCellContentFunction": False})])
            c.update({"title": "Bitácora de eventos del nodo", "showTitleIcon": True, "titleIcon": "history",
                      "iconColor": AZUL_AGUA,
                      "timewindow": {"realtime": {"interval": 1000, "timewindowMs": 86400000},
                                     "aggregation": {"type": "NONE", "limit": 200}}})
            c["settings"].update({"showTimestamp": True, "displayPagination": True, "defaultPageSize": 10})
        return self.agregar("cards.timeseries_table", x, y, w, h, mod)


def construir_tablero(tb, device_id, titulo):
    k = Constructor(tb, device_id)
    # Fila 1: estado + IA + control de la alarma
    k.banner_estado(0, 0, 13, 4)
    k.tarjeta_ia(13, 0, 7, 4)
    k.boton_rpc(20, 0, 4, 2, "SILENCIAR ALARMA", "silenciarAlarma", True)
    k.boton_rpc(20, 2, 4, 2, "REACTIVAR ALARMA", "rearmarAlarma", False)
    # Fila 2: tanque + 9 variables (3 x 3)
    k.tanque(0, 4, 6, 9)
    tarjetas = [("t_amb", "Temperatura ambiente", "°C", 1, "thermostat", "#F97316"),
                ("t_agua", "Temperatura del agua", "°C", 1, "water", AZUL_AGUA),
                ("hum", "Humedad relativa", "%", 0, "water_drop", "#0EA5E9"),
                ("pres", "Presión atmosférica", "hPa", 1, "speed", "#8B5CF6"),
                ("lum", "Radiación solar (luz)", "%", 0, "wb_sunny", "#EAB308"),
                ("evap", "Evaporación potencial", "/100", 0, "air", TURQUESA),
                ("irh", "Riesgo hídrico (IRH)", "/100", 0, "warning", ROJO),
                ("desc", "Descenso del nivel", "%/min", 2, "trending_down", "#E8590C"),
                ("col_agua", "Columna de agua", "cm", 1, "straighten", AZUL_NOCHE)]
    for i, t in enumerate(tarjetas):
        k.tarjeta(6 + (i % 3) * 6, 4 + (i // 3) * 3, 6, 3, *t)
    # Fila 3: tendencia del nivel
    k.grafica(0, 13, 24, 6, "Nivel del tanque y riesgo hídrico", "show_chart", [
        k.clave("nivel", "Nivel (%)", AZUL_AGUA, "%", 1),
        k.clave("nivel_suave", "Nivel suavizado (gateway)", "#94A3B8", "%", 1),
        k.clave("irh", "IRH", ROJO, "/100", 0)])
    # Fila 4: clima y evaporación
    k.grafica(0, 19, 12, 6, "Condiciones meteorológicas", "partly_cloudy_day", [
        k.clave("t_amb", "Temp. ambiente (°C)", "#F97316", "°C", 1),
        k.clave("t_agua", "Temp. agua (°C)", AZUL_AGUA, "°C", 1),
        k.clave("hum", "Humedad (%)", "#0EA5E9", "%", 0)])
    k.grafica(12, 19, 12, 6, "Evaporación y radiación", "wb_sunny", [
        k.clave("evap", "Evaporación potencial", TURQUESA, "/100", 0),
        k.clave("lum", "Radiación (luz %)", "#EAB308", "%", 0)])
    # Fila 5: alarmas y bitácora
    k.alarmas(0, 25, 14, 7)
    k.eventos(14, 25, 10, 7)

    config = {
        "description": "Monitoreo hídrico en tiempo real · Sabana Centro (Cundinamarca)",
        "widgets": k.widgets,
        "states": {"default": {"name": titulo, "root": True, "layouts": {"main": {
            "widgets": k.layout,
            "gridSettings": {"backgroundColor": FONDO, "columns": 24, "margin": 12, "outerMargin": True,
                             "backgroundSizeMode": "100%", "autoFillHeight": False,
                             "mobileAutoFillHeight": False, "mobileRowHeight": 70, "rowHeight": 52,
                             "layoutType": "default"}}}}},
        "entityAliases": {k.alias: {"id": k.alias, "alias": "WaterGuard", "filter": {
            "type": "singleEntity", "resolveMultiple": False,
            "singleEntity": {"entityType": "DEVICE", "id": device_id}}}},
        "filters": {},
        "timewindow": {"displayValue": "", "hideInterval": False, "selectedTab": 0,
                       "realtime": {"realtimeType": 0, "interval": 5000, "timewindowMs": 3600000,
                                    "quickInterval": "CURRENT_DAY"},
                       "aggregation": {"type": "NONE", "limit": 25000}},
        "settings": {"stateControllerId": "entity", "showTitle": True, "showDashboardsSelect": False,
                     "showEntitiesSelect": False, "showDashboardTimewindow": True, "showDashboardExport": False,
                     "showUpdateDashboardImage": False, "toolbarAlwaysOpen": True, "titleColor": AZUL_NOCHE,
                     "showDashboardLogo": True, "dashboardLogoUrl": LOGO, "hideToolbar": False,
                     "showFilters": False, "dashboardCss": CSS_TABLERO},
    }
    return {"title": titulo, "configuration": config}
