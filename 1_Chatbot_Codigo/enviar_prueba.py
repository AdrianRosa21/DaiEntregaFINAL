"""
enviar_prueba.py - Revisa tu archivo .env y comprueba que tus credenciales de Vonage funcionan.

Envía un WhatsApp desde el Sandbox de Vonage a TU número (MI_NUMERO_WHATSAPP en .env).
No necesita el servidor ni el túnel encendidos.

Antes: desde ese WhatsApp unite al Sandbox (escaneá el QR o mandá la frase de unión
que aparece en dashboard.vonage.com/messages/sandbox).

Uso:  python enviar_prueba.py              (revisa el .env y envía el mensaje de prueba)
      python enviar_prueba.py --verificar  (solo revisa el .env, no envía nada)
      python enviar_prueba.py 503XXXXXXXX  (envía a otro número que ya se unió al Sandbox)
"""
import logging
import sys

import config
from bot.vonage_api import enviar_whatsapp

MENSAJE = ("🇸🇻 ¡Hola! Soy *Guanaco Viajero*.\n"
           "Si te llegó este mensaje, tus credenciales de Vonage funcionan ✅\n"
           "Ahora encendé el bot y el túnel, y escribime *hola* 😉")


def revisar_env() -> bool:
    """Muestra el estado del .env SIN revelar las claves. Devuelve True si las credenciales sirven."""
    print("🔎 Revisando el archivo .env ...")
    print(f"   VONAGE_API_KEY ........ {config.ocultar(config.VONAGE_API_KEY) or '(vacío)'}")
    print(f"   VONAGE_API_SECRET ..... {'•' * len(config.VONAGE_API_SECRET) or '(vacío)'}"
          f" ({len(config.VONAGE_API_SECRET)} caracteres)")
    print(f"   VONAGE_WHATSAPP_NUMBER  {config.VONAGE_WHATSAPP_NUMBER}")
    print(f"   MI_NUMERO_WHATSAPP .... {config.ocultar(config.MI_NUMERO_WHATSAPP) or '(vacío)'}")
    problemas = config.problemas_credenciales()
    for problema in problemas:
        print(f"   ❌ {problema}")
    if config.credenciales_listas():
        print("   ✅ La API Key y el API Secret tienen el formato correcto.")
        return True
    print("   👉 Abrí 0_configurar_credenciales.bat, corregí, guardá con Ctrl + S y volvé a probar.")
    return False


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")       # emojis en la consola de Windows
    except (AttributeError, ValueError):
        pass
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not revisar_env():
        return 1
    if "--verificar" in sys.argv:
        return 0

    numero = argumentos[0] if argumentos else config.MI_NUMERO_WHATSAPP
    numero = "".join(c for c in numero if c.isdigit())
    if len(numero) < 8:
        print("⚠️ Falta tu número: en .env escribí MI_NUMERO_WHATSAPP=503 + tu número (sin + ni espacios)")
        return 1

    print(f"\n📤 Enviando mensaje de prueba a {config.ocultar(numero)} por el Sandbox de Vonage...")
    enviado, detalle = enviar_whatsapp(numero, MENSAJE)
    if enviado:
        print(f"✅ ¡Vonage aceptó el mensaje! (202 Accepted) · message_uuid: {detalle}")
        print("   Revisá tu WhatsApp: debería llegarte en unos segundos.")
        return 0
    print(f"❌ No se pudo enviar: {detalle}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
