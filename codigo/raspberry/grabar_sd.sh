#!/bin/bash
# =====================================================================
#  WaterGuard v9 - Graba la SD del Gateway (Raspberry Pi)
#  Uso:  bash grabar_sd.sh /dev/mmcblk0
#  1. Graba Raspberry Pi OS Lite 64-bit (Trixie, 2026-10-06) en la SD.
#  2. Copia a la partición de arranque la configuración de primer arranque
#     (usuario, WiFi del hotspot, instalador y gateway).
#  3. Rellena las claves (lo hace configurar_sd.sh) SIN mostrarlas:
#     - ANTHROPIC_API_KEY desde ../pruebas/claude.env
#     - Usuario/clave del puente MQTT de LeMarTek Cloud desde el servidor
#       (ssh lemartek-node1, archivo ~/lemartek-cloud/.env)
#  BORRA TODO lo que haya en la SD.
# =====================================================================
set -euo pipefail
cd "$(dirname "$0")"
DEV=${1:-}
IMG=trabajo/raspios.img
[ -n "$DEV" ] || { echo "Uso: bash grabar_sd.sh /dev/mmcblkX"; exit 1; }
[ -b "$DEV" ] || { echo "$DEV no es un disco"; exit 1; }
[ -f "$IMG" ] || { echo "Falta $IMG"; exit 1; }
case "$DEV" in /dev/nvme*) echo "Me niego a escribir en $DEV (es el disco del PC)"; exit 1;; esac
RM=$(lsblk -dno RM "$DEV" | tr -d ' '); TRAN=$(lsblk -dno TRAN "$DEV" | tr -d ' ')
[ "$RM" = "1" ] || [ "$TRAN" = "usb" ] || [[ "$DEV" == /dev/mmcblk* ]] || { echo "$DEV no es removible ni USB; no parece una SD. Aborto."; exit 1; }
if findmnt -rno SOURCE | grep -q "^$DEV"; then
  findmnt -rno SOURCE,TARGET | grep "^$DEV" | grep -qE ' (/|/boot|/home)$' && { echo "$DEV tiene montado el sistema; aborto."; exit 1; }
fi
[ "$(lsblk -dno RO "$DEV" | tr -d ' ')" = "0" ] || { echo "$DEV está protegida contra escritura (seguro LOCK)."; exit 1; }
TAM=$(lsblk -bdno SIZE "$DEV")
[ "$TAM" -lt 70000000000 ] || { echo "$DEV mide más de 64 GB; no parece una SD. Aborto."; exit 1; }
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINTS "$DEV"
read -rp "Se va a BORRAR $DEV ($((TAM/1000000000)) GB). Escribe SI para continuar: " ok
[ "$ok" = "SI" ] || { echo "Cancelado"; exit 1; }

echo ">>> Desmontando particiones de $DEV"
for p in $(lsblk -lno PATH "$DEV" | tail -n +1); do sudo umount "$p" 2>/dev/null || true; done

echo ">>> Grabando la imagen (3 GB, tarda unos minutos)"
sudo dd if="$IMG" of="$DEV" bs=4M conv=fsync status=progress
sync
sudo partprobe "$DEV" 2>/dev/null || true
sleep 3
BOOT=$(lsblk -lno PATH "$DEV" | sed -n 2p)
[ -b "$BOOT" ] || { echo "No veo la partición de arranque"; exit 1; }


# La copia de la configuración no necesita sudo (udisksctl)
exec bash ./configurar_sd.sh "$DEV"
