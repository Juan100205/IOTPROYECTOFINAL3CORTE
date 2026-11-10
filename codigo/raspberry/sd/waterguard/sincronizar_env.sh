#!/bin/bash
# Copia /boot/firmware/waterguard.env (editable desde cualquier PC) a
# /etc/waterguard/waterguard.env con permisos restringidos, para que la
# API key y las claves no queden legibles por cualquier usuario.
# Lo llama systemd antes de cada arranque del gateway.
set -e
ORIGEN=/boot/firmware/waterguard.env
DESTINO=/etc/waterguard/waterguard.env
mkdir -p /etc/waterguard
if [ -f "$ORIGEN" ]; then
  install -m 640 -o root -g waterguard-svc "$ORIGEN" "$DESTINO"
fi
