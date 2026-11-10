#!/usr/bin/env python3
"""Simula el ESP32 de WaterGuard (para probar el gateway sin hardware).

Publica los mismos topics y JSON que el firmware v9: el tanque se va
vaciando y la temperatura sube, así que el estado pasa por NORMAL ->
ALERTA -> CRITICO. Atiende las órdenes de silenciar/rearmar.

  python3 simulador_nodo.py --host localhost --usuario nodo1 --clave WaterGuard-Nodo1 --rapido 10
"""
import argparse
import json
import math
import random
import time

import paho.mqtt.client as mqtt

ap = argparse.ArgumentParser()
ap.add_argument("--host", default="localhost")
ap.add_argument("--puerto", type=int, default=1883)
ap.add_argument("--usuario", default="nodo1")
ap.add_argument("--clave", default="WaterGuard-Nodo1")
ap.add_argument("--nodo", default="nodo1")
ap.add_argument("--rapido", type=float, default=1.0, help="factor de aceleración del vaciado")
ap.add_argument("--muestras", type=int, default=0, help="0 = infinito")
args = ap.parse_args()

base = f"waterguard/{args.nodo}"
silenciada = False
cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sim-{args.nodo}")
cli.username_pw_set(args.usuario, args.clave)
cli.will_set(f"{base}/disponible", "offline", qos=1, retain=True)


def al_mensaje(c, ud, msg):
    global silenciada
    d = json.loads(msg.payload)
    if msg.topic.endswith("/cmd"):
        silenciada = d.get("accion") == "silenciar"
        print(f"<- CMD {d}")
        evento(0, f"Alarma {'silenciada' if silenciada else 'reactivada'} por MQTT ({d.get('origen')})")
    else:
        print(f"<- IA  {d}")


cli.on_message = al_mensaje
cli.connect(args.host, args.puerto, 30)
cli.subscribe(f"{base}/cmd", 1)
cli.subscribe(f"{base}/ia", 1)
cli.loop_start()
cli.publish(f"{base}/disponible", "online", qos=1, retain=True)

ev_id = 0


def evento(tipo, msg):
    global ev_id
    ev_id += 1
    cli.publish(f"{base}/eventos", json.dumps({"id": ev_id, "tipo": tipo, "edad_ms": 0, "msg": msg}))


nivel, seq, estado_prev = 85.0, 0, None
evento(0, "Sistema iniciado (simulador)")
while True:
    seq += 1
    t_amb = 22 + 8 * (1 - nivel / 85) + random.uniform(-0.3, 0.3)
    hum = max(20, 60 - 30 * (1 - nivel / 85))
    lum = 50 + 40 * math.sin(seq / 40)
    evap = min(100, max(0, (t_amb - 15) * 3 + (100 - hum) * 0.4 + lum * 0.2))
    nivel = max(0, nivel - 0.05 * args.rapido * (1 + evap / 60) + random.uniform(-0.05, 0.05))
    irh = min(100, max(0, (60 - nivel) * 1.2 + evap * 0.3))
    estado = "CRITICO" if irh >= 70 else "ALERTA" if irh >= 30 else "NORMAL"
    d = {"seq": seq, "edad_ms": 0, "nivel": round(nivel, 1), "nivel_us": round(nivel + 0.4, 1),
         "nivel_p": round(nivel - 0.3, 1), "col_agua": round(nivel * 0.9, 1), "dist": round(100 - nivel, 1),
         "t_agua": round(t_amb - 2, 2), "t_amb": round(t_amb, 1), "hum": round(hum, 1), "pres": 752.3,
         "lum": round(lum, 1), "evap": round(evap, 1), "dpv": 1.2, "desc": round(0.05 * args.rapido * 12, 2),
         "irh": round(irh, 1), "estado": estado, "r1": int(irh > 50), "r2": int(nivel < 30), "sens": 5}
    cli.publish(f"{base}/telemetria", json.dumps(d))
    if estado != estado_prev:
        sonando = estado == "CRITICO" and not silenciada
        cli.publish(f"{base}/estado", json.dumps({"estado": estado, "irh": irh, "silenciada": silenciada,
                                                  "sonando": sonando, "ip": "simulador"}), retain=True)
        evento(2 if estado == "CRITICO" else 1 if estado == "ALERTA" else 0, f"Estado: {estado}")
        estado_prev = estado
    print(f"-> seq={seq} nivel={nivel:.1f}% irh={irh:.0f} {estado}")
    if args.muestras and seq >= args.muestras:
        break
    time.sleep(5 / max(1, args.rapido / 5))
cli.loop_stop()
