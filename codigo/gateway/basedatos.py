"""Base de datos local del gateway (SQLite).

Todo dato que llega del ESP32 se guarda AQUÍ primero y luego se envía
a la nube (patrón store-and-forward): la columna `enviado` marca lo
que ya llegó a la plataforma. Si internet se cae, nada se pierde.
"""
import json
import sqlite3
import threading
import time
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS telemetria (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    nodo      TEXT    NOT NULL,
    ts        INTEGER NOT NULL,          -- ms epoch de la MEDICIÓN
    seq       INTEGER,
    nivel     REAL, nivel_us REAL, nivel_p REAL, col_agua REAL, dist REAL,
    t_agua    REAL, t_amb REAL, hum REAL, pres REAL, lum REAL,
    evap      REAL, dpv REAL, desc REAL, irh REAL,
    estado    TEXT, r1 INTEGER, r2 INTEGER, sens INTEGER,
    -- calculado en el gateway (procesamiento local)
    nivel_suave REAL,                    -- media móvil exponencial
    tasa_h      REAL,                    -- %/hora por regresión (15 min)
    valido      INTEGER DEFAULT 1,       -- 0 = descartado por rango
    enviado     INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_tele_ts ON telemetria(nodo, ts);
CREATE INDEX IF NOT EXISTS ix_tele_env ON telemetria(enviado);

CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nodo TEXT, ts INTEGER, tipo INTEGER, msg TEXT, enviado INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS estados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nodo TEXT, ts INTEGER, estado TEXT, irh REAL, silenciada INTEGER, sonando INTEGER
);
CREATE TABLE IF NOT EXISTS ia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nodo TEXT, ts INTEGER, fuente TEXT, riesgo TEXT, horas REAL,
    anomalia INTEGER, explicacion TEXT, recomendacion TEXT, crudo TEXT,
    enviado INTEGER DEFAULT 0
);
"""

CAMPOS = ["nivel", "nivel_us", "nivel_p", "col_agua", "dist", "t_agua", "t_amb", "hum",
          "pres", "lum", "evap", "dpv", "desc", "irh", "estado", "r1", "r2", "sens"]


class BaseDatos:
    def __init__(self, ruta):
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(ruta, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.executescript(ESQUEMA)
        self.lock = threading.Lock()

    def _ej(self, sql, args=()):
        with self.lock:
            cur = self.con.execute(sql, args)
            self.con.commit()
            return cur

    def _q(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.con.execute(sql, args).fetchall()]

    # ---------------------------------------------------------- escritura
    def guardar_telemetria(self, nodo, ts, d, nivel_suave, tasa_h, valido):
        cols = ["nodo", "ts", "seq"] + CAMPOS + ["nivel_suave", "tasa_h", "valido"]
        vals = [nodo, ts, d.get("seq")] + [d.get(c) for c in CAMPOS] + [nivel_suave, tasa_h, int(valido)]
        sql = f"INSERT INTO telemetria ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"
        return self._ej(sql, vals).lastrowid

    def guardar_evento(self, nodo, ts, tipo, msg):
        self._ej("INSERT INTO eventos (nodo, ts, tipo, msg) VALUES (?,?,?,?)", (nodo, ts, tipo, msg))

    def guardar_estado(self, nodo, ts, d):
        self._ej("INSERT INTO estados (nodo, ts, estado, irh, silenciada, sonando) VALUES (?,?,?,?,?,?)",
                 (nodo, ts, d.get("estado"), d.get("irh"), int(bool(d.get("silenciada"))),
                  int(bool(d.get("sonando")))))

    def guardar_ia(self, nodo, ts, fuente, r):
        self._ej("INSERT INTO ia (nodo, ts, fuente, riesgo, horas, anomalia, explicacion, recomendacion, crudo)"
                 " VALUES (?,?,?,?,?,?,?,?,?)",
                 (nodo, ts, fuente, r["riesgo"], r.get("horas_hasta_critico"), int(bool(r.get("anomalia"))),
                  r.get("explicacion", ""), r.get("recomendacion", ""), json.dumps(r, ensure_ascii=False)))

    def marcar_enviado(self, tabla, ids):
        if ids:
            self._ej(f"UPDATE {tabla} SET enviado=1 WHERE id IN ({','.join('?' * len(ids))})", ids)

    # ---------------------------------------------------------- lectura
    def pendientes(self, tabla, limite=50):
        return self._q(f"SELECT * FROM {tabla} WHERE enviado=0 ORDER BY id LIMIT ?", (limite,))

    def contar_pendientes(self):
        return {t: self._q(f"SELECT COUNT(*) n FROM {t} WHERE enviado=0")[0]["n"]
                for t in ("telemetria", "eventos", "ia")}

    def ventana(self, nodo, desde_ms):
        return self._q("SELECT * FROM telemetria WHERE nodo=? AND ts>=? AND valido=1 ORDER BY ts",
                       (nodo, desde_ms))

    def resumen_por_minuto(self, nodo, minutos):
        """Promedio por minuto de las variables (para el módulo de IA)."""
        desde = int(time.time() * 1000) - minutos * 60_000
        return self._q(
            """SELECT (ts/60000)*60000 AS minuto,
                      ROUND(AVG(nivel),1) nivel, ROUND(AVG(t_agua),2) t_agua, ROUND(AVG(t_amb),1) t_amb,
                      ROUND(AVG(hum),1) hum, ROUND(AVG(pres),1) pres, ROUND(AVG(lum),1) lum,
                      ROUND(AVG(evap),1) evap, ROUND(AVG(irh),1) irh, MAX(estado) estado
               FROM telemetria WHERE nodo=? AND ts>=? AND valido=1
               GROUP BY minuto ORDER BY minuto""", (nodo, desde))

    def eventos_recientes(self, nodo, minutos, limite=15):
        desde = int(time.time() * 1000) - minutos * 60_000
        return self._q("SELECT ts, tipo, msg FROM eventos WHERE nodo=? AND ts>=? ORDER BY ts DESC LIMIT ?",
                       (nodo, desde, limite))

    def ultima_ia(self, nodo):
        r = self._q("SELECT * FROM ia WHERE nodo=? ORDER BY id DESC LIMIT 1", (nodo,))
        return r[0] if r else None
