#!/usr/bin/env bash
# Aprovisiona ThingsBoard (corre dentro de la red de docker; no necesita puertos publicados)
set -euo pipefail
cd "$(dirname "$0")"
touch .env && chmod 600 .env
RED="$(docker compose ps -q thingsboard | xargs docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}')"
docker run --rm --network "$RED" --user "$(id -u):$(id -g)" -v "$PWD":/w -w /w \
  -e TB_URL=http://thingsboard:9090 python:3.12-alpine python provisionar.py
docker compose up -d mqtt-ws
docker compose restart mqtt-ws
