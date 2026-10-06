"""
app.py - Servidor web (Flask) que conecta a Guanaco Viajero con WhatsApp usando Vonage.

Recorrido de un mensaje:
  1. El usuario escribe por WhatsApp al número del Sandbox de Vonage.
  2. Vonage manda el mensaje (JSON) al webhook  POST /webhooks/inbound
     a través del túnel de Cloudflare (https://xxxx.trycloudflare.com → localhost:5000).
  3. Este servidor contesta 200 al instante (si no, Vonage reintenta) y pone el
     mensaje en una cola.
  4. Un "trabajador" en segundo plano lo procesa con el PLN y el motor de diálogo
     (que guarda el contexto en SQLite) y envía la respuesta con la Messages API.
  5. Vonage avisa el estado del envío (entregado, leído...) en  POST /webhooks/status

Ejecutar:  python app.py      (y en otra ventana: el túnel de cloudflared)
"""
import logging
import queue
import sys
import threading
import time

from flask import Flask, jsonify, request

import config
from bot.motor import MotorConversacional
from bot.nlp import formato_guia
from bot.privacidad import anonimizar
from bot.vonage_api import enviar_whatsapp

# Mostrar emojis correctamente en la consola de Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("guanaco")
logging.getLogger("werkzeug").setLevel(logging.WARNING)   # menos "ruido" en la consola

app = Flask(__name__)
app.json.ensure_ascii = False      # mostrar tildes y ñ en /estadisticas
motor = MotorConversacional()      # crea (si no existe) la base de datos datos/guanaco.db
cola = queue.Queue()               # mensajes esperando ser procesados


# ----------------------------------------------------------------------
# Lectura del JSON que manda Vonage
# ----------------------------------------------------------------------
def _numero(valor) -> str:
    """Vonage v1 manda el número como texto; el formato viejo (v0.1) como {'number': ...}."""
    if isinstance(valor, dict):
        valor = valor.get("number", "")
    return "".join(c for c in str(valor or "") if c.isdigit())


def leer_mensaje(datos: dict) -> dict:
    """Extrae lo importante del webhook de Vonage (formato v1, y también el viejo v0.1)."""
    contenido = datos.get("message", {}).get("content", {}) if "message" in datos else datos
    tipo = contenido.get("type") or datos.get("message_type", "")
    texto = contenido.get("text", "") if tipo == "text" else ""
    if tipo == "reply":                                   # respuesta a botones interactivos
        texto = (contenido.get("reply") or {}).get("title", "")
    elif tipo == "button":                                # botón de una plantilla
        texto = (contenido.get("button") or {}).get("text", "")

    ubicacion = None
    if tipo == "location":
        lugar = contenido.get("location") or {}
        try:
            ubicacion = (float(lugar["lat"]), float(lugar["long"]))
        except (KeyError, TypeError, ValueError):
            ubicacion = None

    return {
        "uuid": datos.get("message_uuid", ""),
        "numero": _numero(datos.get("from")),             # quién escribe (solo en memoria)
        "para": _numero(datos.get("to")),                 # número del Sandbox
        "nombre": (datos.get("profile") or {}).get("name", ""),
        "tipo": tipo,
        "texto": (texto or "").strip(),
        "ubicacion": ubicacion,
        "multimedia": tipo in ("image", "audio", "video", "file", "sticker", "vcard"),
    }


def dividir_mensaje(texto: str, limite: int = config.LIMITE_CARACTERES) -> list:
    """WhatsApp acepta hasta 4096 caracteres por mensaje; si es más largo, se divide por líneas."""
    partes, actual = [], ""
    for linea in texto.split("\n"):
        while len(linea) > limite:                        # línea gigante (caso raro)
            partes.append(linea[:limite])
            linea = linea[limite:]
        if actual and len(actual) + len(linea) + 1 > limite:
            partes.append(actual.rstrip())
            actual = ""
        actual += linea + "\n"
    if actual.strip():
        partes.append(actual.rstrip())
    return partes or ["..."]


# ----------------------------------------------------------------------
# Procesamiento (corre en segundo plano)
# ----------------------------------------------------------------------
def procesar_mensaje(m: dict) -> str:
    """PLN + motor de diálogo + envío de la respuesta por Vonage. Devuelve la respuesta."""
    usuario = anonimizar(m["numero"])                     # el número nunca se guarda tal cual
    descripcion = m["texto"] or ("📍 ubicación" if m["ubicacion"] else f"({m['tipo'] or 'archivo'})")
    log.info("📩 Usuario %s: %s", usuario[:6], descripcion)
    try:
        if m["texto"]:
            log.info("🧠 PLN → %s", formato_guia(motor.analizar(m["texto"])))
        respuesta = motor.responder(usuario, m["texto"], nombre=m["nombre"],
                                    ubicacion=m["ubicacion"], tiene_multimedia=m["multimedia"])
    except Exception:                                     # el bot nunca debe "caerse"
        log.exception("Error al procesar el mensaje")
        respuesta = "¡Puchica! 😓 Tuve un problema técnico. Probá de nuevo o escribí *menú*."

    partes = dividir_mensaje(respuesta)
    for n, parte in enumerate(partes):
        if n:
            time.sleep(1.1)                               # Sandbox: máximo 1 mensaje por segundo
        enviado, detalle = enviar_whatsapp(m["numero"], parte, remitente=m["para"])
        if enviado:
            log.info("📤 Respuesta enviada por Vonage (%d caracteres) · id %s…", len(parte), detalle[:8])
    return respuesta


def trabajador() -> None:
    """Hilo que atiende la cola de mensajes, uno por uno y en orden de llegada."""
    while True:
        m = cola.get()
        try:
            procesar_mensaje(m)
        except Exception:
            log.exception("Error inesperado en el trabajador")
        finally:
            cola.task_done()


threading.Thread(target=trabajador, name="trabajador", daemon=True).start()


# ----------------------------------------------------------------------
# Rutas (endpoints)
# ----------------------------------------------------------------------
@app.route("/", methods=["GET"])
def inicio():
    """Página para comprobar en el navegador que el servidor (y el túnel) funcionan."""
    estado = ("✅ Credenciales de Vonage cargadas desde .env" if config.credenciales_listas()
              else "⚠️ Faltan credenciales en .env → el bot está en <b>modo simulación</b>")
    return ("<h2>✅ Guanaco Viajero está funcionando</h2>"
            f"<p>{estado} · Modo: {'Sandbox' if config.VONAGE_SANDBOX else 'Producción'}</p>"
            "<p>En <b>dashboard.vonage.com/messages/sandbox</b> pegá estas URL (con TU dirección del túnel):</p>"
            "<ul><li>Inbound: <code>https://TU-TUNEL.trycloudflare.com/webhooks/inbound</code></li>"
            "<li>Status: <code>https://TU-TUNEL.trycloudflare.com/webhooks/status</code></li></ul>"
            "<p>Métricas anónimas (SQLite): <a href='/estadisticas'>/estadisticas</a></p>")


@app.route("/webhooks/inbound", methods=["POST"])
@app.route("/inbound", methods=["POST"])
def webhook_inbound():
    """Webhook: Vonage llama aquí cada vez que llega un mensaje de WhatsApp."""
    datos = request.get_json(silent=True) or {}
    m = leer_mensaje(datos)
    if not m["numero"]:
        log.warning("⚠️ Llegó un POST sin número de WhatsApp (se ignora)")
        return "", 200
    if m["uuid"] and not motor.bd.marcar_mensaje(m["uuid"]):
        log.info("🔁 Mensaje repetido (reintento de Vonage): se ignora")
        return "", 200
    if config.PROCESAR_EN_SEGUNDO_PLANO:
        cola.put(m)                    # se contesta 200 YA y se procesa en el hilo trabajador
    else:
        procesar_mensaje(m)
    return "", 200


@app.route("/webhooks/status", methods=["POST"])
@app.route("/status", methods=["POST"])
def webhook_status():
    """Webhook de estado: Vonage avisa si el mensaje fue entregado, leído o rechazado."""
    datos = request.get_json(silent=True) or {}
    estado = datos.get("status", "?")
    iconos = {"submitted": "📨", "delivered": "✅", "read": "👀", "rejected": "❌", "undeliverable": "❌"}
    error = datos.get("error") or {}
    detalle = f" → {error.get('title', '')} {error.get('detail', '')}".rstrip() if error else ""
    log.info("%s Estado del mensaje: %s%s", iconos.get(estado, "ℹ️"), estado, detalle)
    return "", 200


@app.route("/webhooks/inbound", methods=["GET"])
@app.route("/webhooks/status", methods=["GET"])
def webhook_navegador():
    """Si abrís la URL del webhook en el navegador, te explica que es solo para Vonage."""
    return ("<p>✅ Esta dirección existe. Vonage la usa con el método <b>POST</b> "
            "(en el navegador es normal ver solo este mensaje).</p>")


@app.route("/estadisticas", methods=["GET"])
def estadisticas():
    """Métricas anónimas calculadas con SQL (no contiene datos personales)."""
    return jsonify(motor.bd.resumen())


if __name__ == "__main__":
    linea = "=" * 66
    print(linea)
    print("  🇸🇻  GUANACO VIAJERO - Chatbot de turismo para WhatsApp (Vonage)")
    print(linea)
    print(f"  Servidor local:   http://localhost:{config.PUERTO}")
    print(f"  Base de datos:    {config.ARCHIVO_BD}")
    if config.credenciales_listas():
        print("  Vonage:           ✅ credenciales cargadas desde .env")
    else:
        print("  Vonage:           ⚠️ credenciales incompletas en .env → MODO SIMULACIÓN")
        for problema in config.problemas_credenciales():
            print(f"                    ❌ {problema}")
        print("                    (abrí 0_configurar_credenciales.bat, corregí y guardá con Ctrl + S)")
    print(linea)
    print("  1) En otra ventana abrí el túnel:  4_abrir_tunel_cloudflared.bat")
    print("  2) Copiá la dirección https://xxxx.trycloudflare.com que aparece")
    print("  3) En dashboard.vonage.com/messages/sandbox pegá y guardá (Save webhooks):")
    print("       Inbound:  https://xxxx.trycloudflare.com/webhooks/inbound")
    print("       Status:   https://xxxx.trycloudflare.com/webhooks/status")
    print("  4) ¡Escribile 'hola' al número del Sandbox desde tu WhatsApp!")
    print("  Para detener el bot: Ctrl + C")
    print(linea)
    app.run(host="0.0.0.0", port=config.PUERTO, debug=False, threaded=True)
