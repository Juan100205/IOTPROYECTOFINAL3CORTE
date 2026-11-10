"""Prueba P3 (TDD): alerta crítica por falla de escritura en SQLite.

No necesita broker ni nube. Simula un disco lleno durante 3 escrituras y
verifica que el gateway (1) active la alerta y la publique al ESP32,
(2) retenga las muestras en orden sin perder ninguna y (3) al recuperarse
la base guarde todo en orden y apague la alerta (también en la nube).

Uso:  python3 codigo/gateway/pruebas/prueba_alerta_bd.py
"""
import os, sqlite3, sys, tempfile, json

GW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tmp = tempfile.mkdtemp()
os.environ.update({"WG_DB": os.path.join(tmp, "wg.db"), "WG_PLATAFORMA": "ninguna", "WG_IA_ACTIVA": "0"})
sys.path.insert(0, GW)
import waterguard_gw as wg

gw = wg.Gateway()
publicados = []
gw.local.publish = lambda topico, carga, qos=0, retain=False: publicados.append((topico, json.loads(carga))) or type("I", (), {"rc": 0})()
nube = []
gw.nube.enviar_alerta_bd = lambda ts, activa, msg: nube.append(activa) or True

real = gw.db.guardar_telemetria
fallar = {"n": 0}
def guardar_que_falla(*a):
    if fallar["n"] > 0:
        fallar["n"] -= 1
        raise sqlite3.OperationalError("database or disk is full")
    return real(*a)
gw.db.guardar_telemetria = guardar_que_falla

def muestra(seq):
    gw._telemetria("nodo1", {"seq": seq, "nivel": 50 - seq * 0.1, "estado": "NORMAL", "edad_ms": 0})

def filas():
    return [r["seq"] for r in gw.db._q("SELECT seq FROM telemetria ORDER BY id")]

muestra(1)                                   # escritura normal
fallar["n"] = 3                              # el disco "se llena"
muestra(2); muestra(3)
assert gw.alerta_bd, "la alerta debía activarse"
assert len(gw.pend_bd) == 2 and filas() == [1], (len(gw.pend_bd), filas())
assert publicados[-1][0] == "waterguard/nodo1/ia" and publicados[-1][1]["riesgo"] == "critico"
print("1) falla -> alerta activa, 2 retenidas, OLED:", publicados[-1][1]["rec"])

muestra(4)                                   # sigue fallando (3.ª falla): se retiene detrás, en orden
assert len(gw.pend_bd) == 3 and filas() == [1]
print("2) nueva muestra durante la falla -> retenida en orden:", [a[2]["seq"] for _, a in gw.pend_bd])

muestra(5)                                   # la BD se recupera: se vacía la cola y luego entra la nueva
import time; time.sleep(0.2)
assert not gw.alerta_bd and not gw.pend_bd, (gw.alerta_bd, len(gw.pend_bd))
assert filas() == [1, 2, 3, 4, 5], filas()
assert nube[:2] == [True, False], nube
print("3) recuperación -> alerta apagada, orden en BD:", filas(), "| nube:", nube[:2],
      "| OLED:", publicados[-1][1]["rec"])
print("PRUEBA OK")
