#!/usr/bin/env python3
"""LeMarTek Cloud for IoT - aprovisionamiento de WaterGuard en ThingsBoard.

Idempotente: se puede correr varias veces. Solo usa la librería estándar.

Hace:
  1. Asegura el tenant "LeMarTek Cloud" y su administrador; cambia la clave
     del sysadmin por defecto y borra el tenant de demostración.
  2. Perfil de dispositivo "WaterGuard" con reglas de alarma.
  3. Dispositivo "WaterGuard · Nodo 1" y su token.
  4. Cliente "Alcaldía · Sabana Centro" con el usuario de la autoridad
     (acceso restringido: solo ve su tablero y su dispositivo).
  5. Notificaciones de alarma (campana web; correo si hay SMTP).
  6. Tablero "WaterGuard · Monitoreo hídrico" (por defecto y a pantalla
     completa para la autoridad).
  7. Configuración del puente MQTT-WebSocket (mqtt-ws/): el gateway entra
     con usuario/clave y el puente usa el token del dispositivo.

Uso (en el servidor, dentro de la red de docker):
  ./provisionar.sh
Credenciales: se leen de .env; las que falten se generan y se agregan a .env.
"""
import base64
import hashlib
import json
import os
import secrets
import string
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parent
ENV = BASE / ".env"
URL = os.environ.get("TB_URL", "http://thingsboard:9090")

TENANT = "LeMarTek Cloud"
DISPOSITIVO = "WaterGuard · Nodo 1"
PERFIL = "WaterGuard"
CLIENTE = "Alcaldía · Sabana Centro"
TABLERO = "WaterGuard · Monitoreo hídrico"


# ------------------------------------------------------------------ .env
def leer_env():
    d = {}
    if ENV.exists():
        for l in ENV.read_text().splitlines():
            if "=" in l and not l.strip().startswith("#"):
                k, v = l.split("=", 1)
                d[k.strip()] = v.strip()
    return d


def clave_aleatoria(n=18):
    abc = string.ascii_letters + string.digits
    return "".join(secrets.choice(abc) for _ in range(n)) + "-Wg7"


def asegurar_env():
    env = leer_env()
    defectos = {
        "TB_SYSADMIN_EMAIL": "sysadmin@lemartek.cloud",
        "TB_SYSADMIN_PASSWORD": clave_aleatoria(),
        "TB_ADMIN_EMAIL": "admin@lemartek.cloud",
        "TB_ADMIN_PASSWORD": clave_aleatoria(),
        "TB_AUTORIDAD_EMAIL": "autoridad@lemartek.cloud",   # cambiar por el correo real que dé la Alcaldía
        "TB_AUTORIDAD_PASSWORD": clave_aleatoria(),
        "MQTT_GW_USUARIO": "gateway-nodo1",
        "MQTT_GW_CLAVE": clave_aleatoria(24),
    }
    nuevas = {k: v for k, v in defectos.items() if not env.get(k)}
    if nuevas:
        with ENV.open("a") as f:
            f.write("\n# --- generado por provisionar.py ---\n")
            for k, v in nuevas.items():
                f.write(f"{k}={v}\n")
        os.chmod(ENV, 0o600)
        env.update(nuevas)
    return env


# ------------------------------------------------------------------ REST
class TB:
    def __init__(self, url):
        self.url = url.rstrip("/")
        self.token = None

    def req(self, metodo, ruta, cuerpo=None, ok404=False):
        datos = None if cuerpo is None else json.dumps(cuerpo).encode()
        r = urllib.request.Request(self.url + ruta, data=datos, method=metodo)
        r.add_header("Content-Type", "application/json")
        if self.token:
            r.add_header("X-Authorization", "Bearer " + self.token)
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                txt = resp.read().decode()
                return json.loads(txt) if txt else None
        except urllib.error.HTTPError as e:
            if ok404 and e.code == 404:
                return None
            raise RuntimeError(f"{metodo} {ruta} -> {e.code}: {e.read().decode()[:400]}")

    def login(self, usuario, clave):
        self.token = None
        try:
            self.token = self.req("POST", "/api/auth/login", {"username": usuario, "password": clave})["token"]
            return True
        except RuntimeError:
            return False

    def buscar(self, ruta, nombre, campo="name"):
        sep = "&" if "?" in ruta else "?"
        res = self.req("GET", f"{ruta}{sep}pageSize=100&page=0&textSearch={urllib.parse.quote(nombre)}")
        for x in res.get("data", []):
            if x.get(campo) == nombre:
                return x
        return None


import urllib.parse  # noqa: E402


def esperar(tb):
    for i in range(90):
        try:
            urllib.request.urlopen(tb.url + "/login", timeout=5)
            return
        except Exception:
            time.sleep(5)
    sys.exit("ThingsBoard no responde en " + tb.url)


def activar_usuario(tb, usuario, clave):
    link = tb.req("GET", f"/api/user/{usuario['id']['id']}/activationLink")
    token = link.split("activateToken=")[1] if isinstance(link, str) else None
    if token is None:  # algunas versiones devuelven texto plano
        raise RuntimeError("no se obtuvo el link de activación")
    tb2 = TB(tb.url)
    tb2.req("POST", "/api/noauth/activate?sendActivationMail=false", {"activateToken": token, "password": clave})


def obtener_link_texto(tb, ruta):
    r = urllib.request.Request(tb.url + ruta, method="GET")
    r.add_header("X-Authorization", "Bearer " + tb.token)
    with urllib.request.urlopen(r, timeout=30) as resp:
        return resp.read().decode()


# ------------------------------------------------------------------ 1. tenant
def paso_tenant(tb, env):
    if tb.login(env["TB_SYSADMIN_EMAIL"], env["TB_SYSADMIN_PASSWORD"]):
        print("· sysadmin ya configurado")
    elif tb.login("sysadmin@thingsboard.org", "sysadmin"):
        print("· sysadmin por defecto: cambiando correo y clave")
        yo = tb.req("GET", "/api/auth/user")
        yo["email"] = env["TB_SYSADMIN_EMAIL"]
        yo["firstName"], yo["lastName"] = "LeMarTek", "Sysadmin"
        tb.req("POST", "/api/user?sendActivationMail=false", yo)
        tb.req("POST", "/api/auth/changePassword",
               {"currentPassword": "sysadmin", "newPassword": env["TB_SYSADMIN_PASSWORD"]})
        tb.login(env["TB_SYSADMIN_EMAIL"], env["TB_SYSADMIN_PASSWORD"])
    else:
        sys.exit("No se pudo entrar como sysadmin (revisa TB_SYSADMIN_* en .env)")

    tenants = tb.req("GET", "/api/tenants?pageSize=100&page=0")["data"]
    for t in tenants:  # tenant de demostración (credenciales públicas)
        if t["title"] == "Tenant":
            print("· borrando tenant de demostración")
            tb.req("DELETE", f"/api/tenant/{t['id']['id']}")
    tenant = next((t for t in tenants if t["title"] == TENANT), None)
    if not tenant:
        tenant = tb.req("POST", "/api/tenant", {"title": TENANT, "country": "Colombia", "city": "Chía",
                                                "email": env["TB_ADMIN_EMAIL"]})
        print("· tenant creado")
    tid = tenant["id"]["id"]

    admins = tb.req("GET", f"/api/tenant/{tid}/users?pageSize=100&page=0")["data"]
    admin = next((u for u in admins if u["email"] == env["TB_ADMIN_EMAIL"]), None)
    if not admin:
        admin = tb.req("POST", "/api/user?sendActivationMail=false", {
            "email": env["TB_ADMIN_EMAIL"], "authority": "TENANT_ADMIN", "tenantId": tenant["id"],
            "firstName": "Administrador", "lastName": "LeMarTek"})
        link = obtener_link_texto(tb, f"/api/user/{admin['id']['id']}/activationLink")
        TB(tb.url).req("POST", "/api/noauth/activate?sendActivationMail=false",
                       {"activateToken": link.split("activateToken=")[1].strip('"'),
                        "password": env["TB_ADMIN_PASSWORD"]})
        print("· administrador del tenant creado")

    # Política de seguridad del login (expuesto a internet por el túnel)
    tb.req("POST", "/api/admin/securitySettings", {
        "passwordPolicy": {"minimumLength": 12, "maximumLength": 72, "minimumUppercaseLetters": 1,
                           "minimumLowercaseLetters": 1, "minimumDigits": 1, "minimumSpecialCharacters": 0,
                           "allowWhitespaces": False, "forceUserToResetPasswordIfNotValid": True,
                           "passwordExpirationPeriodDays": None, "passwordReuseFrequencyDays": 5},
        "maxFailedLoginAttempts": 5,
        "userLockoutNotificationEmail": env.get("TB_ALERTA_SEGURIDAD_EMAIL") or None,
        "mobileSecretKeyLength": 64, "userActivationTokenTtl": 24, "passwordResetTokenTtl": 24})
    print("· política de claves y bloqueo tras 5 intentos fallidos")

    # 2FA por TOTP (app autenticadora) + códigos de respaldo, disponible para todos.
    # No se fuerza desde aquí porque este script entra por la API; cada
    # administrador la activa en su perfil (ver LEEME).
    tb.req("POST", "/api/2fa/settings", {
        "providers": [{"providerType": "TOTP", "issuerName": "LeMarTek Cloud"},
                      {"providerType": "BACKUP_CODE", "codesQuantity": 10}],
        "minVerificationCodeSendPeriod": 30, "verificationCodeCheckRateLimit": "3:900",
        "maxVerificationFailuresBeforeUserLockout": 10, "totalAllowedTimeForVerification": 600})
    print("· 2FA (TOTP) habilitada")

    # Correo opcional (para notificaciones por email)
    if env.get("SMTP_HOST"):
        tb.req("POST", "/api/admin/settings", {"key": "mail", "jsonValue": {
            "mailFrom": env.get("SMTP_FROM", env.get("SMTP_USER", "")), "smtpProtocol": "smtp",
            "smtpHost": env["SMTP_HOST"], "smtpPort": env.get("SMTP_PORT", "587"), "timeout": "10000",
            "enableTls": True, "tlsVersion": "TLSv1.2", "username": env.get("SMTP_USER", ""),
            "password": env.get("SMTP_PASSWORD", ""), "changePassword": True, "enableProxy": False}})
        print("· SMTP configurado")


# ------------------------------------------------------------------ 2-4. entidades
def condicion(clave, operacion, valor, tipo="NUMERIC"):
    pred = {"type": tipo, "operation": operacion, "value": {"defaultValue": valor}}
    if tipo == "BOOLEAN":
        pred = {"type": "BOOLEAN", "operation": operacion, "value": {"defaultValue": valor}}
    return {"condition": [{"key": {"type": "TIME_SERIES", "key": clave}, "valueType": tipo, "predicate": pred}],
            "spec": {"type": "SIMPLE"}}


def alarma(tipo, severidad, crear, limpiar, detalles):
    return {"id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "wg-" + tipo)), "alarmType": tipo,
            "createRules": {severidad: {"condition": crear, "alarmDetails": detalles}},
            "clearRule": {"condition": limpiar}, "propagate": False}


ALARMAS = [
    alarma("Nivel crítico del tanque", "CRITICAL", condicion("nivel", "LESS", 15),
           condicion("nivel", "GREATER_OR_EQUAL", 20), "Nivel en ${nivel}% (umbral 15%)"),
    alarma("Riesgo hídrico crítico (fusión)", "MAJOR", condicion("estado_cod", "EQUAL", 2),
           condicion("estado_cod", "NOT_EQUAL", 2), "El nodo reporta estado CRÍTICO. IRH ${irh}/100"),
    alarma("Descenso anómalo con calor", "MAJOR", condicion("regla_descenso_calor", "EQUAL", True, "BOOLEAN"),
           condicion("regla_descenso_calor", "EQUAL", False, "BOOLEAN"),
           "Descenso de ${desc} %/min con temperatura ${t_amb} °C"),
    alarma("Nodo sin conexión", "WARNING", condicion("nodo_online", "EQUAL", False, "BOOLEAN"),
           condicion("nodo_online", "EQUAL", True, "BOOLEAN"), "El ESP32 perdió conexión con el gateway"),
    alarma("IA: riesgo alto", "WARNING", condicion("ia_riesgo_cod", "GREATER_OR_EQUAL", 2),
           condicion("ia_riesgo_cod", "LESS", 2), "${ia_recomendacion}"),
]


def paso_entidades(tb, env):
    tb.login(env["TB_ADMIN_EMAIL"], env["TB_ADMIN_PASSWORD"])

    perfil = tb.buscar("/api/deviceProfiles", PERFIL)
    cuerpo_perfil = {
        "name": PERFIL, "type": "DEFAULT", "transportType": "DEFAULT", "provisionType": "DISABLED",
        "description": "Nodo WaterGuard (ESP32) vía gateway Raspberry Pi",
        "profileData": {"configuration": {"type": "DEFAULT"}, "transportConfiguration": {"type": "DEFAULT"},
                        "provisionConfiguration": {"type": "DISABLED"}, "alarms": ALARMAS}}
    if perfil:
        perfil = tb.req("GET", f"/api/deviceProfile/{perfil['id']['id']}")
        perfil["profileData"]["alarms"] = ALARMAS
        perfil = tb.req("POST", "/api/deviceProfile", perfil)
    else:
        perfil = tb.req("POST", "/api/deviceProfile", cuerpo_perfil)
    print("· perfil de dispositivo con", len(ALARMAS), "reglas de alarma")

    disp = tb.req("GET", f"/api/tenant/devices?deviceName={urllib.parse.quote(DISPOSITIVO)}", ok404=True)
    if not disp:
        disp = tb.req("POST", "/api/device", {"name": DISPOSITIVO, "label": "Tanque · Sabana Centro",
                                              "deviceProfileId": perfil["id"]})
        print("· dispositivo creado")
    cred = tb.req("GET", f"/api/device/{disp['id']['id']}/credentials")
    token = cred["credentialsId"]
    tb.req("POST", f"/api/plugins/telemetry/DEVICE/{disp['id']['id']}/attributes/SERVER_SCOPE",
           {"capacidad_litros": 1000, "umbral_critico": 15, "ubicacion": "Sabana Centro, Cundinamarca"})

    cliente = tb.buscar("/api/customers", CLIENTE, "title")
    if not cliente:
        cliente = tb.req("POST", "/api/customer", {"title": CLIENTE, "country": "Colombia",
                                                   "state": "Cundinamarca", "city": "Chía"})
        print("· cliente creado")
    cid = cliente["id"]["id"]
    tb.req("POST", f"/api/customer/{cid}/device/{disp['id']['id']}")

    usuarios = tb.req("GET", f"/api/customer/{cid}/users?pageSize=100&page=0")["data"]
    autoridad = next((u for u in usuarios if u["email"] == env["TB_AUTORIDAD_EMAIL"]), None)
    if not autoridad:
        autoridad = tb.req("POST", "/api/user?sendActivationMail=false", {
            "email": env["TB_AUTORIDAD_EMAIL"], "authority": "CUSTOMER_USER", "customerId": cliente["id"],
            "firstName": "Autoridad", "lastName": "Sabana Centro"})
        link = obtener_link_texto(tb, f"/api/user/{autoridad['id']['id']}/activationLink")
        TB(tb.url).req("POST", "/api/noauth/activate?sendActivationMail=false",
                       {"activateToken": link.split("activateToken=")[1].strip('"'),
                        "password": env["TB_AUTORIDAD_PASSWORD"]})
        autoridad = tb.req("GET", f"/api/user/{autoridad['id']['id']}")
        print("· usuario de la autoridad creado")
    return disp, token, cliente, autoridad


# ------------------------------------------------------------------ 5. notificaciones
def paso_notificaciones(tb, cliente):
    try:
        def destino(nombre, filtro):
            x = tb.buscar("/api/notification/targets", nombre)
            return x or tb.req("POST", "/api/notification/target", {
                "name": nombre, "configuration": {"type": "PLATFORM_USERS", "usersFilter": filtro,
                                                  "description": nombre}})
        t1 = destino("Administradores LeMarTek", {"type": "TENANT_ADMINISTRATORS"})
        t2 = destino("Autoridades Sabana Centro", {"type": "CUSTOMER_USERS", "customerId": cliente["id"]["id"]})
        plantilla = tb.buscar("/api/notification/templates?notificationTypes=ALARM", "WaterGuard · Alarma")
        if not plantilla:
            plantilla = tb.req("POST", "/api/notification/template", {
                "name": "WaterGuard · Alarma", "notificationType": "ALARM",
                "configuration": {"deliveryMethodsTemplates": {
                    "WEB": {"enabled": True, "method": "WEB",
                            "subject": "${alarmSeverity:capitalize}: ${alarmType}",
                            "body": "${alarmOriginatorName} · ${alarmStatus:lowerCase}. ${alarmDetails}",
                            "additionalConfig": {"icon": {"enabled": True, "icon": "water_drop", "color": "#E5484D"},
                                                 "actionButtonConfig": {"enabled": False}}},
                    "EMAIL": {"enabled": True, "method": "EMAIL",
                              "subject": "[WaterGuard] ${alarmSeverity:capitalize}: ${alarmType}",
                              "body": "<p><b>${alarmType}</b> en ${alarmOriginatorName}</p>"
                                      "<p>Estado: ${alarmStatus}. ${alarmDetails}</p>"
                                      "<p>LeMarTek Cloud for IoT</p>"}}}})
        if not tb.buscar("/api/notification/rules", "WaterGuard · Alarmas"):
            tb.req("POST", "/api/notification/rule", {
                "name": "WaterGuard · Alarmas", "enabled": True, "templateId": plantilla["id"],
                "triggerType": "ALARM",
                "triggerConfig": {"triggerType": "ALARM", "alarmTypes": None, "alarmSeverities": None,
                                  "notifyOn": ["CREATED", "SEVERITY_CHANGED", "CLEARED"], "clearRule": None},
                "recipientsConfig": {"triggerType": "ALARM",
                                     "escalationTable": {"0": [t1["id"]["id"], t2["id"]["id"]]}}})
        print("· notificaciones de alarma configuradas")
    except RuntimeError as e:
        print("! notificaciones no configuradas:", e)


# ------------------------------------------------------------------ 6. tablero
from tablero import construir_tablero  # noqa: E402


def paso_tablero(tb, disp, cliente, autoridad):
    cuerpo = construir_tablero(tb, disp["id"]["id"], TABLERO)
    existente = tb.buscar("/api/tenant/dashboards", TABLERO, "title")
    if existente:
        cuerpo["id"] = existente["id"]
        actual = tb.req("GET", f"/api/dashboard/{existente['id']['id']}")
        cuerpo["version"] = actual.get("version")
    tablero = tb.req("POST", "/api/dashboard", cuerpo)
    did = tablero["id"]["id"]
    tb.req("POST", f"/api/customer/{cliente['id']['id']}/dashboard/{did}")
    info = autoridad.get("additionalInfo") or {}
    info.update({"defaultDashboardId": did, "defaultDashboardFullscreen": True,
                 "homeDashboardId": did, "homeDashboardHideToolbar": False})
    autoridad["additionalInfo"] = info
    tb.req("POST", "/api/user?sendActivationMail=false", autoridad)
    print("· tablero publicado:", did)
    return did


# ------------------------------------------------------------------ 7. puente MQTT
def hash_mosquitto(clave):
    """Formato $7$ de mosquitto_passwd (PBKDF2-SHA512, 101 iteraciones)."""
    sal = os.urandom(12)
    h = hashlib.pbkdf2_hmac("sha512", clave.encode(), sal, 101)
    return f"$7$101${base64.b64encode(sal).decode()}${base64.b64encode(h).decode()}"


def paso_puente(env, token):
    d = BASE / "mqtt-ws"
    d.mkdir(exist_ok=True)
    (d / "mosquitto.conf").write_text(f"""# Generado por provisionar.py - no editar a mano
# Mosquitto con WebSockets: recibe al gateway (usuario/clave) y reenvía a
# ThingsBoard por la red interna de docker usando el token del dispositivo.
per_listener_settings true
persistence true
persistence_location /mosquitto/data/
log_dest stdout

listener 9001
protocol websockets
allow_anonymous false
password_file /mosquitto/config/passwd
acl_file /mosquitto/config/acl

connection thingsboard
address thingsboard:1883
bridge_protocol_version mqttv311
try_private false
notifications false
cleansession true
restart_timeout 5 30
remote_clientid lemartek-puente-nodo1
remote_username {token}
topic v1/devices/me/telemetry out 1
topic v1/devices/me/rpc/response/+ out 1
topic v1/devices/me/rpc/request/+ in 1
""")
    (d / "acl").write_text(f"user {env['MQTT_GW_USUARIO']}\ntopic readwrite v1/devices/me/#\n")
    (d / "passwd").write_text(f"{env['MQTT_GW_USUARIO']}:{hash_mosquitto(env['MQTT_GW_CLAVE'])}\n")
    for f in ("mosquitto.conf", "acl", "passwd"):
        os.chmod(d / f, 0o600)
    print("· puente MQTT-WS configurado (usuario del gateway:", env["MQTT_GW_USUARIO"] + ")")


def main():
    env = asegurar_env()
    tb = TB(URL)
    esperar(tb)
    paso_tenant(tb, env)
    disp, token, cliente, autoridad = paso_entidades(tb, env)
    paso_notificaciones(tb, cliente)
    paso_tablero(tb, disp, cliente, autoridad)
    paso_puente(env, token)
    # Candado: encender_tunel.sh solo publica el túnel si existe esta línea
    if leer_env().get("PROVISIONADO") != "1":
        with ENV.open("a") as f:
            f.write("PROVISIONADO=1\n")
    print("\nListo. Credenciales en .env (permisos 600). Siguiente: ./encender_tunel.sh")


if __name__ == "__main__":
    main()
