# LeMarTek Cloud for IoT · WaterGuard

Plataforma IoT en la nube privada de LeMarTek: ThingsBoard CE 4.2.1 + puente
MQTT sobre WebSockets + túnel de Cloudflare. **No publica ningún puerto en el
servidor**: todo entra por el túnel saliente de `cloudflared`.

```
Raspberry (gateway) --wss://mqtt.lemartek.cloud--> Cloudflare --túnel--> mqtt-ws:9001 --(red docker)--> thingsboard:1883
Autoridades (navegador) --https://iot.lemartek.cloud--> Cloudflare --túnel--> thingsboard:9090
```

## Archivos
| Archivo | Para qué |
|---|---|
| `docker-compose.yml` | ThingsBoard, puente `mqtt-ws` y `cloudflared` (perfil `tunel`). Sin puertos publicados. |
| `provisionar.sh` / `provisionar.py` | Crea tenant, dispositivo, alarmas, cliente "Alcaldía", usuario de la autoridad, notificaciones, tablero y la config del puente. Idempotente. |
| `tablero.py` | Diseño del tablero "WaterGuard · Monitoreo hídrico". |
| `mqtt-ws/` | Config de Mosquitto (la genera `provisionar.py`, permisos 600). |
| `.env` | Secretos (600) que genera el aprovisionamiento + `PROVISIONADO=1`. **No se sube a git.** |
| `tunnel_token` | Token del túnel (600), montado como *secret*: no aparece en `docker inspect`. |
| `encender_tunel.sh` | Único modo de encender el túnel; exige aprovisionar antes. |
| `docker-compose.local.yml` | Solo para pruebas en un PC (publica 8080/9001 en 127.0.0.1). No usar en el servidor. |

## Montaje en el servidor (una sola vez)
> Antes de publicar: revisión de Inesita (ciberseguridad), regla para todo lo expuesto a internet.

1. Docker CE + plugin compose v2 instalados.
2. Cloudflare Zero Trust → Networks → Tunnels → crear túnel `lemartek-iot` (conector Docker).
   Public hostnames (zona **lemartek.cloud**, confirmar que esté en la cuenta):
   - `iot.lemartek.cloud`  → HTTP → `thingsboard:9090`
   - `mqtt.lemartek.cloud` → HTTP → `mqtt-ws:9001`
3. Copiar esta carpeta a `~/lemartek-cloud/` y guardar el token **en un archivo** (no en .env, no en chats):
   ```bash
   cd ~/lemartek-cloud
   read -rs -p "TUNNEL_TOKEN: " t && (umask 077; printf '%s' "$t" > tunnel_token) && unset t
   ```
4. Levantar ThingsBoard (la primera vez tarda 2-3 min en crear la base de datos):
   ```bash
   docker compose up -d thingsboard
   docker compose logs -f thingsboard   # esperar "Started ThingsboardServerApplication"
   ```
5. Aprovisionar. Genera credenciales en `.env`, cambia la clave del sysadmin por defecto,
   borra el tenant demo, fija la política de claves (mínimo 12, bloqueo tras 5 intentos),
   habilita 2FA y escribe `PROVISIONADO=1`:
   ```bash
   ./provisionar.sh
   ```
6. Encender el túnel. **Solo con este script**: se niega si falta `PROVISIONADO=1` o el archivo `tunnel_token`.
   ```bash
   ./encender_tunel.sh
   ```
   (No usar `docker compose --profile tunel up` directamente.)
7. Ver solo la credencial que se necesite:
   ```bash
   grep '^TB_ADMIN' .env        # administrador LeMarTek
   grep '^TB_AUTORIDAD' .env    # usuario de la Alcaldía
   grep '^MQTT_GW' .env         # para waterguard.env de la Raspberry (WG_NUBE_USUARIO / WG_NUBE_CLAVE)
   ```
8. **2FA obligatoria para administradores**: entrar a https://iot.lemartek.cloud con el sysadmin y con el
   admin del tenant → Perfil → Seguridad → Autenticación de dos factores → app autenticadora (TOTP),
   y guardar los códigos de respaldo.
9. El correo de la autoridad es `autoridad@lemartek.cloud` por defecto. Cuando la Alcaldía dé el correo
   real, cambiar `TB_AUTORIDAD_EMAIL` en `.env` y volver a correr `./provisionar.sh`.

### Opcional (recomendado): Cloudflare Access
- **Administradores**: aplicación de Access para `iot.lemartek.cloud` con política por correo
  (equipo LeMarTek) y otra que permita a la autoridad, o al menos proteger las rutas de administración.
- **Puente MQTT**: aplicación de Access para `mqtt.lemartek.cloud` con un *service token*; el gateway
  enviaría las cabeceras `CF-Access-Client-Id` / `CF-Access-Client-Secret`. Así el puente no es
  alcanzable sin el token (hoy lo protege usuario + clave de 24 caracteres).

## Operación
```bash
docker compose ps
docker compose logs -f mqtt-ws        # ver conexión del gateway y del puente
docker compose restart mqtt-ws        # tras volver a aprovisionar
./provisionar.sh                      # reaplica tablero/alarmas (no borra datos)
```
