#!/bin/bash
# =====================================================================
#  WaterGuard v9 - Copia la configuración de primer arranque a una SD
#  que YA tiene Raspberry Pi OS grabado (lo llama grabar_sd.sh, o se
#  usa solo si la grabación terminó pero la copia falló).
#  Uso:  bash configurar_sd.sh /dev/sdX      (el disco, no la partición)
#  No necesita sudo: monta la partición de arranque con udisksctl.
#  Rellena las claves en waterguard.env SIN mostrarlas en pantalla.
# =====================================================================
set -euo pipefail
cd "$(dirname "$0")"
DEV=${1:-}
[ -b "$DEV" ] || { echo "Uso: bash configurar_sd.sh /dev/sdX  ($DEV no es un disco)"; exit 1; }
BOOT=$(lsblk -lno PATH "$DEV" | sed -n 2p)
[ -b "$BOOT" ] || { echo "No veo la partición de arranque en $DEV"; exit 1; }
[ "$(lsblk -no LABEL "$BOOT")" = "bootfs" ] || { echo "$BOOT no es la partición bootfs de Raspberry Pi OS"; exit 1; }

for f in user-data network-config waterguard.env; do
  [ -f "sd/$f" ] || { echo "Falta sd/$f: copia sd/$f.ejemplo (o ../gateway/waterguard.env.ejemplo) y edítalo"; exit 1; }
done

echo ">>> Leyendo claves (no se muestran)"
ANTH=$(grep -E '^ANTHROPIC_API_KEY=' ../pruebas/claude.env 2>/dev/null | tail -1 | cut -d= -f2-) || true
NUBE=$(ssh -o ConnectTimeout=10 lemartek-node1 "grep -E '^MQTT_GW_(USUARIO|CLAVE)=' ~/lemartek-cloud/.env") || true
NUBE_U=$(printf '%s\n' "$NUBE" | grep '^MQTT_GW_USUARIO=' | cut -d= -f2-) || true
NUBE_C=$(printf '%s\n' "$NUBE" | grep '^MQTT_GW_CLAVE='   | cut -d= -f2-) || true
[ -n "$ANTH" ]   && echo "    API key de Claude: OK"    || echo "    !! Sin ANTHROPIC_API_KEY (la IA usará el modelo estadístico)"
[ -n "$NUBE_C" ] && echo "    Clave LeMarTek Cloud: OK" || echo "    !! Sin clave del servidor (rellena WG_NUBE_CLAVE a mano)"

if ! ls sd/waterguard/wheels/*.whl >/dev/null 2>&1; then
  echo ">>> Descargando librerías de Python para ARM64 (wheels)"
  mkdir -p sd/waterguard/wheels
  python3 -m pip download -q -d sd/waterguard/wheels --only-binary=:all: --implementation cp \
    --python-version 3.13 --abi cp313 --platform manylinux_2_17_aarch64 --platform manylinux2014_aarch64 \
    --platform manylinux_2_28_aarch64 --platform any "anthropic==2.6.0" "paho-mqtt==2.2.0" \
    || echo "    !! No se pudieron bajar; la Raspberry las instalará desde internet"
fi

echo ">>> Montando $BOOT"
MNT=$(findmnt -rno TARGET "$BOOT" || true)
MONTE_YO=0
if [ -z "$MNT" ]; then
  udisksctl mount -b "$BOOT" >/dev/null
  MNT=$(findmnt -rno TARGET "$BOOT"); MONTE_YO=1
fi
echo "    en $MNT"

echo ">>> Copiando configuración WaterGuard"
cp -f sd/user-data sd/network-config sd/waterguard.env "$MNT"/
rm -rf "$MNT/waterguard"; cp -r sd/waterguard "$MNT"/
mkdir -p "$MNT/waterguard/gateway" "$MNT/waterguard/mosquitto"
cp -f ../gateway/*.py "$MNT/waterguard/gateway/"
cp -f mosquitto/waterguard.conf mosquitto/waterguard.acl "$MNT/waterguard/mosquitto/"
export ANTH NUBE_U NUBE_C
python3 - "$MNT/waterguard.env" <<'PY'
import sys, os
ruta = sys.argv[1]
vals = {"ANTHROPIC_API_KEY": os.environ.get("ANTH", ""),
        "WG_NUBE_USUARIO":   os.environ.get("NUBE_U", ""),
        "WG_NUBE_CLAVE":     os.environ.get("NUBE_C", "")}
out = []
for l in open(ruta, encoding="utf-8").read().splitlines():
    k = l.split("=", 1)[0]
    if k in vals and vals[k]:
        l = f"{k}={vals[k]}"
    out.append(l)
open(ruta, "w", encoding="utf-8").write("\n".join(out) + "\n")
PY
sync
echo ">>> Verificando"
for f in user-data network-config waterguard.env waterguard/instalar.sh waterguard/wheels; do
  [ -e "$MNT/$f" ] && echo "    OK  $f" || { echo "    FALTA $f"; exit 1; }
done
grep -q '^ANTHROPIC_API_KEY=.\+' "$MNT/waterguard.env" && echo "    OK  API key de Claude escrita" || echo "    --  API key vacía"
grep -q '^WG_NUBE_CLAVE=.\+'     "$MNT/waterguard.env" && echo "    OK  clave LeMarTek Cloud escrita" || echo "    --  clave LeMarTek Cloud vacía"
[ "$MONTE_YO" = 1 ] && udisksctl unmount -b "$BOOT" >/dev/null
sync
echo
echo "===== SD LISTA ====="
echo "1. Enciende la red WiFi configurada en sd/network-config."
echo "2. Pon la SD en la Raspberry y conéctala a la corriente."
echo "3. Espera 5-10 minutos (el primer arranque instala todo)."
echo "4. Comprueba:  ssh waterguard@waterguard-gw.local   (clave en credenciales_raspberry.txt)"
echo "   o lee waterguard/instalacion.log metiendo la SD en un PC."
