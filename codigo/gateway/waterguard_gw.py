#!/usr/bin/env python3
"""WaterGuard v9 - Gateway IoT (Raspberry Pi).

Flujo:
  ESP32 --MQTT--> Mosquitto (local) --> este programa
      1. valida y procesa cada muestra (media móvil, tasa de descenso),
      2. la guarda en SQLite,
      3. un hilo aparte la reenvía por MQTT a la nube (store-and-forward),
      4. otro hilo corre el módulo de IA y publica la predicción
         al ESP32 (topic .../ia) y a la nube.
  Las órdenes de la nube (silenciar/rearmar la alarma) bajan al ESP32
  por waterguard/<nodo>/cmd.

  Si una escritura en SQLite falla (disco lleno, base bloqueada, SD
  dañada), el gateway emite una ALERTA CRÍTICA (log, nube y OLED del
  ESP32 por .../ia) y retiene las escrituras en orden en una cola en
  memoria: no se procesa ningún dato nuevo hacia la base hasta que las
  pendientes se guarden. Como la nube solo recibe lo que ya está en
  SQLite, ningún dato llega a la nube sin quedar antes en el histórico.

Uso:  python3 waterguard_gw.py        (configuración en waterguard.env)
"""
import json
import logging
import signal
import sqlite3
import threading
import time
from collections import deque

import paho.mqtt.client as mqtt

import config
from basedatos import BaseDatos
from ia_claude import ModuloIA, regresion
from plataforma import Plataforma

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)-6s %(levelname)-7s %(message)s")
log = logging.getLogger("gw")

# Rangos físicos válidos: lo que cae fuera se guarda marcado como inválido
RANGOS = {"nivel": (-5, 105), "t_agua": (-5, 60), "t_amb": (-10, 60), "hum": (0, 100),
          "pres": (600, 1100), "lum": (0, 100)}
ALFA_EMA = 0.2              # media móvil exponencial del nivel
VENTANA_TASA_MS = 15 * 60_000
MAX_PENDIENTES_BD = 5000    # escrituras retenidas en RAM si SQLite falla (~7 h de telemetría a 5 s)


def ahora_ms():
    return int(time.time() * 1000)


class Gateway:
    def __init__(self):
        self.cfg = config.cargar()
        log.info("Configuración: %s | plataforma=%s | IA=%s (%s)", self.cfg["origen"], self.cfg["plataforma"],
                 "sí" if self.cfg["ia_activa"] else "no", self.cfg["ia_modelo"])
        self.db = BaseDatos(self.cfg["db"])
        self.nube = Plataforma(self.cfg, self.enviar_comando)
        self.ia = ModuloIA(self.cfg)
        self.parar = threading.Event()
        self.ema = {}                         # nodo -> nivel suavizado
        self.serie = {}                       # nodo -> deque[(ts, nivel)]
        self.estado_previo = {}
        self.disparar_ia = threading.Event()
        self.ultima_ia = 0.0
        # Alerta crítica por falla de la base de datos local
        self.pend_bd = deque()                # escrituras retenidas, en orden de llegada
        self.lock_bd = threading.RLock()
        self.alerta_bd = False
        self.alerta_bd_msg = ""
        self.alerta_bd_nube = None            # estado de la alerta aún no confirmado por la nube

        self.local = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="waterguard-gateway")
        if self.cfg["mqtt_clave"]:
            self.local.username_pw_set(self.cfg["mqtt_usuario"], self.cfg["mqtt_clave"])
        self.local.on_connect = self._on_connect
        self.local.on_message = self._on_message
        self.local.reconnect_delay_set(1, 15)

    # ------------------------------------------------------------ MQTT local
    def _on_connect(self, cli, ud, flags, rc, props=None):
        if rc != 0:
            log.error("Broker local rechazó la conexión (%s)", rc)
            return
        log.info("Conectado al broker local %s:%s", self.cfg["mqtt_host"], self.cfg["mqtt_puerto"])
        for t in ("telemetria", "estado", "eventos", "disponible"):
            cli.subscribe(f"waterguard/+/{t}", qos=1)

    def _on_message(self, cli, ud, msg):
        try:
            _, nodo, tipo = msg.topic.split("/", 2)
            texto = msg.payload.decode("utf-8", "replace")
            if tipo == "disponible":
                self._disponible(nodo, texto == "online")
                return
            d = json.loads(texto)
            if tipo == "telemetria":
                self._telemetria(nodo, d)
            elif tipo == "estado":
                self._estado(nodo, d)
            elif tipo == "eventos":
                ts = ahora_ms() - int(d.get("edad_ms", 0))
                self._guardar(self.db.guardar_evento, nodo, ts, int(d.get("tipo", 0)), d.get("msg", ""))
        except Exception as e:
            log.error("Mensaje inválido en %s: %s (%s)", msg.topic, msg.payload[:120], e)

    # ------------------------------------------------------------ procesamiento local
    def _telemetria(self, nodo, d):
        ts = ahora_ms() - int(d.get("edad_ms", 0))   # hora real de la medición
        valido = True
        for k, (lo, hi) in RANGOS.items():
            v = d.get(k)
            if v is not None and not lo <= v <= hi:
                log.warning("%s: %s=%s fuera de rango, muestra marcada inválida", nodo, k, v)
                valido = False

        nivel = d.get("nivel")
        suave, tasa = self.ema.get(nodo), None
        if valido and nivel is not None:
            suave = nivel if suave is None else round(ALFA_EMA * nivel + (1 - ALFA_EMA) * suave, 2)
            self.ema[nodo] = suave
            s = self.serie.setdefault(nodo, deque())
            s.append((ts, nivel))
            while s and s[0][0] < ts - VENTANA_TASA_MS:
                s.popleft()
            pend = regresion([(t / 3_600_000, v) for t, v in s])
            tasa = None if pend is None else round(pend, 2)

        self._guardar(self.db.guardar_telemetria, nodo, ts, d, suave, tasa, valido)

    def _estado(self, nodo, d):
        ts = ahora_ms()
        if self._guardar(self.db.guardar_estado, nodo, ts, d):   # a la nube solo lo que quedó guardado
            self.nube.enviar_estado(ts, d)
        nuevo = d.get("estado")
        if nuevo != self.estado_previo.get(nodo):
            log.info("%s: estado %s -> %s", nodo, self.estado_previo.get(nodo), nuevo)
            if nuevo in ("ALERTA", "CRITICO"):
                self.disparar_ia.set()        # análisis inmediato ante una alerta
            self.estado_previo[nodo] = nuevo

    def _disponible(self, nodo, online):
        ts = ahora_ms()
        msg = "Nodo en línea" if online else "Nodo desconectado del gateway (LWT)"
        log.info("%s: %s", nodo, msg)
        self._guardar(self.db.guardar_evento, nodo, ts, 0 if online else 2, msg)
        self.nube.enviar_disponible(ts, online)

    def enviar_comando(self, accion, origen):
        carga = json.dumps({"accion": accion, "origen": origen})
        info = self.local.publish(f"waterguard/{self.cfg['nodo']}/cmd", carga, qos=1)
        log.info("Comando '%s' desde %s -> ESP32", accion, origen)
        self._guardar(self.db.guardar_evento, self.cfg["nodo"], ahora_ms(), 3, f"Orden '{accion}' desde {origen}")
        return info.rc == mqtt.MQTT_ERR_SUCCESS

    # ------------------------------------------------------------ BD local: escritura verificada
    def _guardar(self, fn, *args):
        """Escribe en SQLite. Devuelve True si el dato quedó guardado.

        Si hay escrituras retenidas, la nueva se pone detrás de ellas
        (se respeta el orden) y se intenta vaciar la cola primero.
        """
        with self.lock_bd:
            if self.pend_bd:
                self._retener(fn, args)
                return self._vaciar_pendientes()
            try:
                fn(*args)
                return True
            except sqlite3.Error as e:
                self._retener(fn, args)
                self._activar_alerta_bd(f"{type(e).__name__}: {e}")
                return False

    def _retener(self, fn, args):
        if len(self.pend_bd) >= MAX_PENDIENTES_BD:
            self.pend_bd.popleft()
            log.critical("BD: cola de retención llena (%s); se descarta la escritura más antigua",
                         MAX_PENDIENTES_BD)
        self.pend_bd.append((fn, args))

    def _vaciar_pendientes(self):
        """Reintenta en orden. True si la cola quedó vacía."""
        with self.lock_bd:
            while self.pend_bd:
                fn, args = self.pend_bd[0]
                try:
                    fn(*args)
                except sqlite3.Error as e:
                    self.alerta_bd_msg = f"{type(e).__name__}: {e}"
                    return False
                self.pend_bd.popleft()
            if self.alerta_bd:
                self._desactivar_alerta_bd()
            return True

    def _activar_alerta_bd(self, detalle):
        if self.alerta_bd:
            return
        self.alerta_bd, self.alerta_bd_msg = True, detalle
        log.critical("ALERTA CRÍTICA: falla de escritura en la base de datos local (%s). "
                     "Los datos quedan retenidos en orden y no se envían a la nube hasta guardarse.", detalle)
        # In situ: la OLED y el tablero local del ESP32 muestran el mensaje de .../ia
        self.local.publish(f"waterguard/{self.cfg['nodo']}/ia", json.dumps(
            {"horas": None, "riesgo": "critico", "rec": "FALLA BD GATEWAY: datos retenidos, revisar la SD",
             "fuente": "gateway"}, ensure_ascii=False), qos=1, retain=True)
        self.alerta_bd_nube = True
        self._notificar_nube_bd()

    def _desactivar_alerta_bd(self):
        self.alerta_bd = False
        log.warning("BD local recuperada: se guardaron todas las escrituras retenidas")
        ultima = None
        try:
            ultima = self.db.ultima_ia(self.cfg["nodo"])
        except sqlite3.Error:
            pass
        carga = ({"horas": ultima["horas"], "riesgo": ultima["riesgo"], "rec": ultima["recomendacion"],
                  "fuente": ultima["fuente"]} if ultima else
                 {"horas": None, "riesgo": "bajo", "rec": "BD del gateway recuperada", "fuente": "gateway"})
        self.local.publish(f"waterguard/{self.cfg['nodo']}/ia", json.dumps(carga, ensure_ascii=False),
                           qos=1, retain=True)
        self.alerta_bd_nube = False
        self._notificar_nube_bd()

    def _notificar_nube_bd(self):
        """Envía el estado de la alerta a la nube en otro hilo (la publicación puede esperar hasta 10 s)."""
        estado, msg = self.alerta_bd_nube, self.alerta_bd_msg

        def enviar():
            if self.nube.enviar_alerta_bd(ahora_ms(), estado, msg) and self.alerta_bd_nube == estado:
                self.alerta_bd_nube = None        # confirmado; si no, lo reintenta hilo_reenvio
        threading.Thread(target=enviar, name="alerta-bd", daemon=True).start()

    # ------------------------------------------------------------ hilo: reenvío a la nube
    def hilo_reenvio(self):
        while not self.parar.is_set():
            try:
                if self.pend_bd:
                    self._vaciar_pendientes()     # reintento periódico aunque no lleguen datos nuevos
                if self.alerta_bd_nube is not None:
                    self._notificar_nube_bd()
                enviado_algo = False
                for tabla, fn in (("telemetria", self.nube.enviar_telemetria),
                                  ("eventos", self.nube.enviar_eventos),
                                  ("ia", self.nube.enviar_ia)):
                    filas = self.db.pendientes(tabla, 50)
                    if filas and fn(filas):
                        self.db.marcar_enviado(tabla, [f["id"] for f in filas])
                        enviado_algo = True
                if not enviado_algo:
                    self.parar.wait(2)
            except Exception as e:
                log.error("Reenvío: %s", e)
                self.parar.wait(5)

    # ------------------------------------------------------------ hilo: IA
    def hilo_ia(self):
        periodo = self.cfg["ia_periodo_min"] * 60
        self.parar.wait(60)                   # deja juntar datos al arrancar
        while not self.parar.is_set():
            disparo = self.disparar_ia.wait(timeout=max(5.0, periodo - (time.time() - self.ultima_ia)))
            if self.parar.is_set():
                break
            if disparo and time.time() - self.ultima_ia < 180:   # máximo 1 análisis extra cada 3 min
                self.disparar_ia.clear()
                self.parar.wait(5)
                continue
            self.disparar_ia.clear()
            self.ultima_ia = time.time()
            try:
                self.correr_ia()
            except Exception as e:
                log.error("IA: %s", e)

    def correr_ia(self):
        nodo = self.cfg["nodo"]
        resumen = self.db.resumen_por_minuto(nodo, 120)
        if not resumen:
            log.info("IA: sin datos todavía")
            return
        eventos = self.db.eventos_recientes(nodo, 120)
        fuente, r = self.ia.analizar(resumen, eventos)
        self._guardar(self.db.guardar_ia, nodo, ahora_ms(), fuente, r)
        if self.alerta_bd:                    # no tapar la alerta de BD en la OLED del ESP32
            log.info("IA [%s]: riesgo=%s (no se publica al ESP32 mientras dure la alerta de BD)",
                     fuente, r["riesgo"])
            return
        al_esp32 = {"horas": r["horas_hasta_critico"], "riesgo": r["riesgo"], "rec": r["recomendacion"],
                    "fuente": fuente}
        self.local.publish(f"waterguard/{nodo}/ia", json.dumps(al_esp32, ensure_ascii=False), qos=1, retain=True)
        log.info("IA [%s]: riesgo=%s horas=%s -> %s", fuente, r["riesgo"], r["horas_hasta_critico"],
                 r["recomendacion"])

    # ------------------------------------------------------------ arranque
    def correr(self):
        signal.signal(signal.SIGTERM, lambda *a: self.parar.set())
        signal.signal(signal.SIGINT, lambda *a: self.parar.set())
        self.local.connect_async(self.cfg["mqtt_host"], self.cfg["mqtt_puerto"], keepalive=30)
        self.local.loop_start()
        hilos = [threading.Thread(target=self.hilo_reenvio, name="reenvio", daemon=True),
                 threading.Thread(target=self.hilo_ia, name="ia", daemon=True)]
        for h in hilos:
            h.start()
        while not self.parar.wait(60):
            try:
                log.info("Pendientes por enviar a la nube: %s | retenidos por falla de BD: %s",
                         self.db.contar_pendientes(), len(self.pend_bd))
            except sqlite3.Error as e:
                log.error("No se pudo consultar la BD (%s); retenidos: %s", e, len(self.pend_bd))
        log.info("Deteniendo gateway")
        self.local.loop_stop()


if __name__ == "__main__":
    Gateway().correr()
