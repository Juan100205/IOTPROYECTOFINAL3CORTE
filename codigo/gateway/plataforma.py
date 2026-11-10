"""Conexión MQTT con la plataforma IoT en la nube.

Soporta:
  - thingsboard : LeMarTek Cloud for IoT (ThingsBoard autoalojado).
                  Telemetría en v1/devices/me/telemetry con el token del
                  dispositivo; comandos por RPC (botón del tablero).
  - ubidots     : alternativa recomendada por el enunciado.
  - ninguna     : solo guarda en SQLite (pruebas sin internet).
Para cambiar de plataforma solo se edita WG_PLATAFORMA en waterguard.env.
"""
import json
import logging
import ssl
import threading

import paho.mqtt.client as mqtt

log = logging.getLogger("nube")

# Variables numéricas que se envían a la nube
NUMERICAS = ["nivel", "nivel_us", "nivel_p", "col_agua", "t_agua", "t_amb", "hum", "pres",
             "lum", "evap", "dpv", "desc", "irh", "nivel_suave", "tasa_h", "sens"]
CODIGO_ESTADO = {"NORMAL": 0, "ALERTA": 1, "CRITICO": 2, "DEGRADADO": 3, "ERROR": 4}
CODIGO_RIESGO = {"bajo": 0, "medio": 1, "alto": 2, "critico": 3}


class Plataforma:
    """Interfaz común. al_comando(accion, origen) se llama al recibir una orden."""

    def __init__(self, cfg, al_comando):
        self.cfg = cfg
        self.al_comando = al_comando
        self.conectada = threading.Event()
        self.cli = None
        tipo = cfg["plataforma"]
        if tipo == "ninguna":
            return
        if not cfg["nube_host"] or not (cfg["nube_token"] or cfg["nube_usuario"]):
            log.warning("Nube sin WG_NUBE_HOST o credenciales: solo se guarda en SQLite")
            self.cfg["plataforma"] = "ninguna"
            return
        ws = cfg["nube_transporte"] == "websockets"
        self.cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                               client_id=f"waterguard-gw-{cfg['nodo']}",
                               transport="websockets" if ws else "tcp")
        if ws:
            cabeceras = None
            if cfg["cf_access_id"]:
                cabeceras = {"CF-Access-Client-Id": cfg["cf_access_id"],
                             "CF-Access-Client-Secret": cfg["cf_access_secret"]}
            self.cli.ws_set_options(path=cfg["nube_ruta_ws"], headers=cabeceras)
        if cfg["nube_usuario"]:
            # LeMarTek Cloud: usuario/clave del puente MQTT-WS (el token de
            # ThingsBoard queda guardado solo en el servidor)
            self.cli.username_pw_set(cfg["nube_usuario"], cfg["nube_clave"])
        elif tipo == "thingsboard":
            self.cli.username_pw_set(cfg["nube_token"])
        else:  # ubidots
            self.cli.username_pw_set(cfg["nube_token"], "")
        if cfg["nube_tls"]:
            self.cli.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        self.cli.on_connect = self._on_connect
        self.cli.on_disconnect = self._on_disconnect
        self.cli.on_message = self._on_message
        self.cli.reconnect_delay_set(2, 30)
        self.cli.connect_async(cfg["nube_host"], cfg["nube_puerto"], keepalive=30)
        self.cli.loop_start()

    # ---------------------------------------------------------- conexión
    def _on_connect(self, cli, ud, flags, rc, props=None):
        if rc != 0:
            log.error("Nube: conexión rechazada (%s). ¿Token correcto?", rc)
            return
        log.info("Nube conectada (%s en %s)", self.cfg["plataforma"], self.cfg["nube_host"])
        if self.cfg["plataforma"] == "thingsboard":
            cli.subscribe("v1/devices/me/rpc/request/+", qos=1)
        else:
            cli.subscribe(f"/v1.6/devices/{self.cfg['ubidots_dispositivo']}/silenciar/lv", qos=1)
        self.conectada.set()

    def _on_disconnect(self, cli, ud, flags, rc, props=None):
        self.conectada.clear()
        log.warning("Nube desconectada (%s); los datos quedan en SQLite", rc)

    def _on_message(self, cli, ud, msg):
        try:
            if self.cfg["plataforma"] == "thingsboard":
                # Topic: v1/devices/me/rpc/request/<id>  Payload: {"method": ..., "params": ...}
                req_id = msg.topic.rsplit("/", 1)[-1]
                d = json.loads(msg.payload)
                metodo = d.get("method", "")
                accion = {"silenciarAlarma": "silenciar", "rearmarAlarma": "rearmar"}.get(metodo)
                if metodo == "setAlarma":  # interruptor del tablero: params true = silenciada
                    accion = "silenciar" if d.get("params") in (True, "true", 1) else "rearmar"
                ok = False
                if accion:
                    ok = self.al_comando(accion, "LeMarTek Cloud")
                cli.publish(f"v1/devices/me/rpc/response/{req_id}", json.dumps({"ok": ok}), qos=1)
            else:
                valor = float(msg.payload)
                self.al_comando("silenciar" if valor >= 1 else "rearmar", "Ubidots")
        except Exception as e:
            log.error("Nube: comando inválido %s (%s)", msg.payload[:100], e)

    # ---------------------------------------------------------- envío
    def _publicar(self, topico, carga):
        info = self.cli.publish(topico, json.dumps(carga, ensure_ascii=False), qos=1)
        info.wait_for_publish(timeout=10)
        return info.is_published()

    def _topico(self):
        if self.cfg["plataforma"] == "thingsboard":
            return "v1/devices/me/telemetry"
        return f"/v1.6/devices/{self.cfg['ubidots_dispositivo']}"

    def enviar_telemetria(self, filas):
        """filas: registros de SQLite. Devuelve True si la nube confirmó (QoS 1)."""
        if self.cli is None or not self.conectada.is_set():
            return False
        if self.cfg["plataforma"] == "thingsboard":
            lote = []
            for f in filas:
                v = {k: f[k] for k in NUMERICAS if f.get(k) is not None}
                v["estado"] = f["estado"]
                v["estado_cod"] = CODIGO_ESTADO.get(f["estado"], -1)
                v["regla_descenso_calor"] = bool(f["r1"])
                v["regla_nivel_evap"] = bool(f["r2"])
                lote.append({"ts": f["ts"], "values": v})
            return self._publicar(self._topico(), lote)
        # Ubidots: un mensaje por fila, cada variable con su timestamp
        for f in filas:
            carga = {k: {"value": f[k], "timestamp": f["ts"]} for k in NUMERICAS if f.get(k) is not None}
            carga["estado"] = {"value": CODIGO_ESTADO.get(f["estado"], -1), "timestamp": f["ts"],
                               "context": {"texto": f["estado"]}}
            if not self._publicar(self._topico(), carga):
                return False
        return True

    def enviar_eventos(self, filas):
        if self.cli is None or not self.conectada.is_set():
            return False
        if self.cfg["plataforma"] == "thingsboard":
            lote = [{"ts": f["ts"], "values": {"evento": f["msg"], "evento_tipo": f["tipo"]}} for f in filas]
            return self._publicar(self._topico(), lote)
        for f in filas:
            if not self._publicar(self._topico(), {"evento": {"value": f["tipo"], "timestamp": f["ts"],
                                                              "context": {"msg": f["msg"]}}}):
                return False
        return True

    def enviar_estado(self, ts, d):
        """Estado de la alarma (para el interruptor y las alarmas del tablero)."""
        if self.cli is None or not self.conectada.is_set():
            return False
        if self.cfg["plataforma"] == "thingsboard":
            return self._publicar(self._topico(), {"ts": ts, "values": {
                "alarma_sonando": bool(d.get("sonando")), "alarma_silenciada": bool(d.get("silenciada")),
                "estado": d.get("estado"), "estado_cod": CODIGO_ESTADO.get(d.get("estado"), -1)}})
        return self._publicar(self._topico(), {
            "alarma_sonando": {"value": int(bool(d.get("sonando"))), "timestamp": ts},
            "silenciar": {"value": int(bool(d.get("silenciada"))), "timestamp": ts}})

    def enviar_disponible(self, ts, online):
        if self.cli is None or not self.conectada.is_set():
            return False
        if self.cfg["plataforma"] == "thingsboard":
            return self._publicar(self._topico(), {"ts": ts, "values": {"nodo_online": online}})
        return self._publicar(self._topico(), {"nodo_online": {"value": int(online), "timestamp": ts}})

    def enviar_alerta_bd(self, ts, activa, msg):
        """Alerta crítica del gateway: falla de escritura en la base de datos local.

        En ThingsBoard (LeMarTek Cloud) llega como telemetría `alerta_bd`; con una
        regla de alarma sobre esa clave el tablero notifica a las autoridades.
        """
        if self.cli is None or not self.conectada.is_set():
            return False
        if self.cfg["plataforma"] == "thingsboard":
            return self._publicar(self._topico(), {"ts": ts, "values": {
                "alerta_bd": bool(activa), "alerta_bd_msg": msg if activa else ""}})
        return self._publicar(self._topico(), {
            "alerta_bd": {"value": int(bool(activa)), "timestamp": ts, "context": {"msg": msg[:100]}}})

    def enviar_ia(self, filas):
        if self.cli is None or not self.conectada.is_set():
            return False
        for f in filas:
            if self.cfg["plataforma"] == "thingsboard":
                carga = {"ts": f["ts"], "values": {
                    "ia_riesgo": f["riesgo"], "ia_riesgo_cod": CODIGO_RIESGO.get(f["riesgo"], -1),
                    "ia_horas_critico": f["horas"], "ia_anomalia": bool(f["anomalia"]),
                    "ia_recomendacion": f["recomendacion"], "ia_explicacion": f["explicacion"],
                    "ia_fuente": f["fuente"]}}
            else:
                carga = {"ia_riesgo": {"value": CODIGO_RIESGO.get(f["riesgo"], -1), "timestamp": f["ts"],
                                       "context": {"rec": f["recomendacion"][:100], "fuente": f["fuente"]}},
                         "ia_anomalia": {"value": int(bool(f["anomalia"])), "timestamp": f["ts"]}}
                if f["horas"] is not None:
                    carga["ia_horas_critico"] = {"value": f["horas"], "timestamp": f["ts"]}
            if not self._publicar(self._topico(), carga):
                return False
        return True
