#!/bin/bash
# =====================================================================
#  WaterGuard v9 - Instalador del Gateway IoT (Raspberry Pi OS Trixie)
#  Lo ejecuta cloud-init UNA vez, en el primer arranque (ver user-data).
#  Se puede repetir a mano:  sudo bash /boot/firmware/waterguard/instalar.sh
#
#  Deja instalado:
#   - Mosquitto (broker MQTT local, puerto 1883, solo con usuario/clave)
#   - El gateway en /opt/waterguard como servicio systemd "waterguard-gw"
#   - Base de datos SQLite en /var/lib/waterguard/waterguard.db
#   - Nombre en la red: waterguard-gw.local (Avahi / mDNS)
#  Bitácora: /boot/firmware/waterguard/instalacion.log (se lee desde un PC)
# =====================================================================
set -u
SRC=/boot/firmware/waterguard
ENV_BOOT=/boot/firmware/waterguard.env
ENV_SYS=/etc/waterguard/waterguard.env
OPT=/opt/waterguard
LOG=$SRC/instalacion.log

exec > >(tee -a "$LOG") 2>&1
echo "===== Instalación WaterGuard: $(date) ====="

paso() { echo; echo ">>> $*"; }
falla() { echo "!!! ERROR: $*"; echo "===== Instalación INCOMPLETA: $(date) ====="; exit 1; }

[ -f "$ENV_BOOT" ] || falla "no existe $ENV_BOOT"
# Lee una clave del waterguard.env (sin ejecutar el archivo)
leer() { grep -E "^$1=" "$ENV_BOOT" | tail -1 | cut -d= -f2- | sed -e 's/^["'\'']//' -e 's/["'\'']$//'; }

paso "Esperando internet (hotspot del celular)"
for i in $(seq 1 60); do
  if getent hosts deb.debian.org >/dev/null 2>&1 && ping -c1 -W2 deb.debian.org >/dev/null 2>&1; then
    echo "Conectado: $(hostname -I)"; break
  fi
  sleep 5
done

paso "Instalando paquetes del sistema (mosquitto, avahi, sqlite3, venv)"
export DEBIAN_FRONTEND=noninteractive
for intento in 1 2 3; do
  apt-get update && apt-get install -y mosquitto mosquitto-clients avahi-daemon sqlite3 python3-venv && break
  echo "apt falló (intento $intento); reintento en 20 s"; sleep 20
done
command -v mosquitto >/dev/null || falla "no se pudo instalar mosquitto (¿hay internet en el hotspot?)"

paso "Copiando el gateway a $OPT"
id waterguard-svc >/dev/null 2>&1 || useradd --system --home "$OPT" --shell /usr/sbin/nologin waterguard-svc
mkdir -p "$OPT" /var/lib/waterguard /etc/waterguard
cp -f "$SRC"/gateway/*.py "$OPT"/
cp -f "$SRC"/sincronizar_env.sh "$OPT"/ && chmod 755 "$OPT"/sincronizar_env.sh
chown -R waterguard-svc:waterguard-svc /var/lib/waterguard

paso "Entorno de Python con anthropic y paho-mqtt (sin internet, desde wheels/)"
[ -x "$OPT/venv/bin/python" ] || python3 -m venv "$OPT/venv"
"$OPT/venv/bin/pip" install --no-index --find-links "$SRC/wheels" anthropic paho-mqtt \
  || "$OPT/venv/bin/pip" install anthropic==2.6.0 paho-mqtt==2.2.0 \
  || falla "no se pudieron instalar las librerías de Python"

paso "Configurando Mosquitto (usuarios nodo1 y gateway)"
NODO_U=$(leer WG_MQTT_NODO_USUARIO); NODO_C=$(leer WG_MQTT_NODO_CLAVE)
GW_U=$(leer WG_MQTT_GW_USUARIO);     GW_C=$(leer WG_MQTT_GW_CLAVE)
[ -n "$NODO_C" ] && [ -n "$GW_C" ] || falla "faltan claves MQTT en waterguard.env"
cp -f "$SRC/mosquitto/waterguard.conf" /etc/mosquitto/conf.d/waterguard.conf
cp -f "$SRC/mosquitto/waterguard.acl"  /etc/mosquitto/waterguard.acl
rm -f /etc/mosquitto/waterguard.passwd
mosquitto_passwd -c -b /etc/mosquitto/waterguard.passwd "$NODO_U" "$NODO_C"
mosquitto_passwd -b    /etc/mosquitto/waterguard.passwd "$GW_U"   "$GW_C"
chown root:mosquitto /etc/mosquitto/waterguard.passwd /etc/mosquitto/waterguard.acl
chmod 640 /etc/mosquitto/waterguard.passwd /etc/mosquitto/waterguard.acl
systemctl enable mosquitto && systemctl restart mosquitto || falla "mosquitto no arrancó"

paso "Publicando el nombre waterguard-gw.local por mDNS"
hostnamectl set-hostname waterguard-gw
sed -i 's/^127\.0\.1\.1.*/127.0.1.1\twaterguard-gw/' /etc/hosts
grep -q waterguard-gw /etc/hosts || echo -e "127.0.1.1\twaterguard-gw" >> /etc/hosts
systemctl enable avahi-daemon && systemctl restart avahi-daemon

paso "Instalando el servicio waterguard-gw"
"$OPT"/sincronizar_env.sh
cp -f "$SRC/waterguard-gw.service" /etc/systemd/system/waterguard-gw.service
systemctl daemon-reload
systemctl enable waterguard-gw
systemctl restart waterguard-gw

sleep 8
paso "Estado final"
systemctl --no-pager --lines=0 status mosquitto avahi-daemon waterguard-gw | grep -E '●|Active:'
journalctl -u waterguard-gw --no-pager -n 15
echo "IP: $(hostname -I)"
echo "===== Instalación COMPLETA: $(date) ====="
