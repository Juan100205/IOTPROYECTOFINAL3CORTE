#!/usr/bin/env bash
# Publica la plataforma por el túnel de Cloudflare.
# Se niega si ThingsBoard no está aprovisionado: sin aprovisionar quedaría
# expuesto con las credenciales por defecto (sysadmin@thingsboard.org/sysadmin).
set -euo pipefail
cd "$(dirname "$0")"

if ! grep -qx 'PROVISIONADO=1' .env 2>/dev/null; then
  echo "ALTO: falta correr ./provisionar.sh (no hay PROVISIONADO=1 en .env). No se enciende el túnel." >&2
  exit 1
fi

# Migración: si el token quedó como TUNNEL_TOKEN en .env, se pasa a ./tunnel_token
if [ ! -s tunnel_token ] && grep -q '^TUNNEL_TOKEN=' .env; then
  umask 077
  grep '^TUNNEL_TOKEN=' .env | head -1 | cut -d= -f2- | tr -d '\n' > tunnel_token
  sed -i '/^TUNNEL_TOKEN=/d' .env
  echo "· token movido de .env a ./tunnel_token (600)"
fi
if [ ! -s tunnel_token ]; then
  echo "ALTO: falta ./tunnel_token. Guárdalo con:" >&2
  echo "  read -rs -p 'TUNNEL_TOKEN: ' t && (umask 077; printf '%s' \"\$t\" > tunnel_token) && unset t" >&2
  exit 1
fi
chmod 600 tunnel_token

UID_GID="$(stat -c '%u:%g' tunnel_token)" docker compose --profile tunel up -d cloudflared
docker compose --profile tunel ps
