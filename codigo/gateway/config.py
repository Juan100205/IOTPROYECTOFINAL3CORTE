"""Configuración del gateway WaterGuard.

Lee un archivo KEY=VALOR. Se busca, en orden:
  1. La ruta en la variable de entorno WG_ENV.
  2. /boot/firmware/waterguard.env  (partición FAT de la SD de la Raspberry:
     se puede editar desde cualquier PC antes de prender la Pi).
  3. /etc/waterguard/waterguard.env
  4. waterguard.env junto a este archivo.
Las variables de entorno ya definidas tienen prioridad sobre el archivo.
"""
import os
from pathlib import Path

RUTAS = [
    os.environ.get("WG_ENV", ""),
    "/boot/firmware/waterguard.env",
    "/etc/waterguard/waterguard.env",
    str(Path(__file__).with_name("waterguard.env")),
]


def _leer_env(ruta):
    datos = {}
    for linea in Path(ruta).read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        datos[k.strip()] = v.strip().strip('"').strip("'")
    return datos


def cargar():
    archivo = {}
    origen = None
    for r in RUTAS:
        if r and Path(r).is_file():
            archivo = _leer_env(r)
            origen = r
            break
    valores = {**archivo, **{k: v for k, v in os.environ.items() if k.startswith(("WG_", "ANTHROPIC_"))}}

    def g(k, defecto=""):
        return valores.get(k, defecto)

    cfg = {
        "origen": origen,
        # Broker local (Mosquitto en la Raspberry)
        "mqtt_host": g("WG_MQTT_HOST", "localhost"),
        "mqtt_puerto": int(g("WG_MQTT_PUERTO", "1883")),
        "mqtt_usuario": g("WG_MQTT_GW_USUARIO", "gateway"),
        "mqtt_clave": g("WG_MQTT_GW_CLAVE", ""),
        # Base de datos local
        "db": g("WG_DB", "/var/lib/waterguard/waterguard.db"),
        # Plataforma IoT en la nube: thingsboard | ubidots | ninguna
        "plataforma": g("WG_PLATAFORMA", "thingsboard").lower(),
        "nube_host": g("WG_NUBE_HOST", ""),
        "nube_puerto": int(g("WG_NUBE_PUERTO", "1883")),
        "nube_tls": g("WG_NUBE_TLS", "0") == "1",
        "nube_token": g("WG_NUBE_TOKEN", ""),          # token del dispositivo
        "nube_usuario": g("WG_NUBE_USUARIO", ""),      # si hay usuario se usa en vez del token
        "nube_clave": g("WG_NUBE_CLAVE", ""),
        "nube_transporte": g("WG_NUBE_TRANSPORTE", "tcp"),   # tcp | websockets
        "nube_ruta_ws": g("WG_NUBE_RUTA_WS", "/"),
        # Opcional: service token de Cloudflare Access para el puente MQTT-WS
        "cf_access_id": g("WG_CF_ACCESS_CLIENT_ID", ""),
        "cf_access_secret": g("WG_CF_ACCESS_CLIENT_SECRET", ""),
        "ubidots_dispositivo": g("WG_UBIDOTS_DISPOSITIVO", "waterguard-nodo1"),
        # Módulo de IA (Claude)
        "ia_activa": g("WG_IA_ACTIVA", "1") == "1",
        "ia_modelo": g("WG_IA_MODELO", "claude-opus-5-5"),
        "ia_periodo_min": float(g("WG_IA_PERIODO_MIN", "15")),
        "anthropic_key": g("ANTHROPIC_API_KEY", ""),
        # Tanque (para pasar de % a litros en la IA)
        "tanque_litros": float(g("WG_TANQUE_LITROS", "1000")),
        "nivel_critico": float(g("WG_NIVEL_CRITICO", "15")),
        "nodo": g("WG_NODO", "nodo1"),
    }
    return cfg
