"""
vonage_api.py - Envía mensajes de WhatsApp con la Messages API de Vonage.

Cómo funciona:
  * Se hace una petición HTTP POST (con la librería requests) a la Messages API.
  * La autenticación es "Basic": API Key + API Secret de tu cuenta de Vonage.
  * En pruebas se usa el Sandbox: https://messages-sandbox.nexmo.com/v1/messages
  * Vonage contesta 202 (Accepted) y un message_uuid si recibió el mensaje.

Si todavía no pegaste tus credenciales en el archivo .env, el bot trabaja en
"modo simulación": muestra en la consola lo que habría enviado.
"""
import logging
import time

import requests

import config

log = logging.getLogger("guanaco")


def enviar_whatsapp(destino: str, texto: str, remitente: str = ""):
    """Envía un texto por WhatsApp. Devuelve (exito, detalle)."""
    destino = (destino or "").lstrip("+")
    if not config.credenciales_listas():
        log.warning("🧪 MODO SIMULACIÓN (faltan credenciales en .env). Respuesta que se enviaría:\n%s",
                    texto)
        return False, "simulacion"

    cuerpo = {
        "from": remitente or config.VONAGE_WHATSAPP_NUMBER,   # número del Sandbox de WhatsApp
        "to": destino,                                       # número del usuario (503XXXXXXXX)
        "channel": "whatsapp",
        "message_type": "text",
        "text": texto,
    }
    for intento in (1, 2):
        try:
            respuesta = requests.post(
                config.URL_MENSAJES,
                json=cuerpo,
                auth=(config.VONAGE_API_KEY, config.VONAGE_API_SECRET),   # autenticación Basic
                headers={"Accept": "application/json"},
                timeout=config.SEGUNDOS_API_VONAGE,
            )
        except requests.RequestException as error:
            log.error("❌ No se pudo conectar con Vonage: %s", error)
            return False, str(error)

        if respuesta.status_code == 429 and intento == 1:   # muy rápido: esperar y reintentar
            time.sleep(1.5)
            continue
        if respuesta.status_code == 202:
            return True, respuesta.json().get("message_uuid", "")
        break

    detalle = f"{respuesta.status_code}: {respuesta.text[:300]}"
    if respuesta.status_code == 401:
        detalle += " (revisá VONAGE_API_KEY y VONAGE_API_SECRET en el archivo .env)"
    elif respuesta.status_code == 429:
        detalle += " (límite del Sandbox: 1 mensaje por segundo y 100 al mes)"
    elif respuesta.status_code in (400, 403, 422):
        detalle += (" (¿tu número ya se unió al Sandbox? ¿pasaron más de 24 h desde tu último "
                    "mensaje? Volvé a escribirle al bot o unite de nuevo con el QR)")
    log.error("❌ Vonage rechazó el mensaje → %s", detalle)
    return False, detalle
