"""
consola.py - Probar a Guanaco Viajero en la terminal, SIN WhatsApp.

Sirve para hacer pruebas rápidas sin gastar mensajes del Sandbox de Vonage
(son 100 al mes) y como plan B en la defensa si falla el internet.
Usa la misma base de datos SQLite que el bot de WhatsApp (datos/guanaco.db).

Comandos especiales:
  /pln                  muestra cómo el PLN entiende cada mensaje (#intención y @entidades)
  /ubicacion LAT LON    simula que compartís tu ubicación  (ej.: /ubicacion 13.67 -89.28)
  /bd                   muestra el resumen de la base de datos SQLite
  /salir                cerrar el programa
"""
import json
import sys

from bot.motor import MotorConversacional
from bot.nlp import formato_guia
from bot.privacidad import anonimizar


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")       # emojis en la consola de Windows
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    motor = MotorConversacional()
    usuario = anonimizar("consola-local")
    ver_pln = False

    print("=" * 64)
    print("  🇸🇻 GUANACO VIAJERO - modo consola (sin WhatsApp)")
    print("  Escribí 'hola' para empezar.  Comandos: /pln  /ubicacion  /bd  /salir")
    print("=" * 64)

    while True:
        try:
            texto = input("\n🧑 Vos: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        comando = texto.lower()
        if comando in ("/salir", "/exit"):
            break
        if comando == "/pln":
            ver_pln = not ver_pln
            print(f"   (Análisis del PLN {'ACTIVADO' if ver_pln else 'desactivado'})")
            continue
        if comando == "/bd":
            print(json.dumps(motor.bd.resumen(), ensure_ascii=False, indent=2))
            continue

        ubicacion = None
        if comando.startswith("/ubicacion"):
            partes = texto.split()
            try:
                ubicacion = (float(partes[1]), float(partes[2]))
                texto = ""
            except (IndexError, ValueError):
                print("   Uso: /ubicacion 13.67 -89.28")
                continue

        if ver_pln and texto:
            a = motor.analizar(texto)
            print(f"   🧠 PLN → texto limpio: '{a.normalizado}'")
            print(f"          {formato_guia(a)}   (puntos: {a.puntaje:g})")

        respuesta = motor.responder(usuario, texto, ubicacion=ubicacion)
        print("\n🤖 Guanaco Viajero:\n" + respuesta)

    print("\n👋 ¡Hasta pronto!")


if __name__ == "__main__":
    main()
