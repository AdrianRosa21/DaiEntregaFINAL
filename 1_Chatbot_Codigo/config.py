"""
config.py - Configuración general del chatbot "Guanaco Viajero".

Las credenciales de Vonage NO se escriben en el código: se leen del archivo
.env (que no se comparte ni se sube en el ZIP).
Plantilla: credenciales_ejemplo.txt (0_configurar_credenciales.bat crea el .env).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

CARPETA_BASE = Path(__file__).resolve().parent
load_dotenv(CARPETA_BASE / ".env")          # carga las variables del archivo .env

# --- Archivos ---
CARPETA_DATOS = CARPETA_BASE / "datos"
ARCHIVO_DESTINOS = CARPETA_DATOS / "destinos.json"      # base de conocimiento (solo lectura)
ARCHIVO_BD = Path(os.environ.get("ARCHIVO_BD", CARPETA_DATOS / "guanaco.db"))  # base de datos SQLite

# --- Vonage (Messages API) ---
VONAGE_API_KEY = os.environ.get("VONAGE_API_KEY", "").strip()
VONAGE_API_SECRET = os.environ.get("VONAGE_API_SECRET", "").strip()
VONAGE_WHATSAPP_NUMBER = os.environ.get("VONAGE_WHATSAPP_NUMBER", "14157386102").strip()
VONAGE_SANDBOX = os.environ.get("VONAGE_SANDBOX", "1").strip() == "1"
URL_MENSAJES = ("https://messages-sandbox.nexmo.com/v1/messages" if VONAGE_SANDBOX
                else "https://api.nexmo.com/v1/messages")
MI_NUMERO_WHATSAPP = os.environ.get("MI_NUMERO_WHATSAPP", "").strip().lstrip("+")

# --- Servidor ---
NOMBRE_BOT = "Guanaco Viajero"
PUERTO = int(os.environ.get("PUERTO", "5000"))
PROCESAR_EN_SEGUNDO_PLANO = True   # responde 200 a Vonage al instante y procesa aparte

# "Sal" secreta que se mezcla con el número antes de calcular el hash (anonimizar)
SAL_PRIVACIDAD = os.environ.get("SAL_PRIVACIDAD", "guanaco-viajero-sv-2026")

# --- Comportamiento ---
MINUTOS_SESION = 30          # el contexto de la conversación se borra tras 30 min sin mensajes
LIMITE_CARACTERES = 4000     # WhatsApp acepta hasta 4096 caracteres por mensaje
SEGUNDOS_API_CLIMA = 4       # tiempo máximo de espera al servicio del clima
MINUTOS_CACHE_CLIMA = 10     # se reutiliza el clima consultado durante 10 minutos
SEGUNDOS_API_VONAGE = 10     # tiempo máximo de espera al enviar un mensaje


MARCADORES = ("", "tu_api_key", "tu_api_secret", "TU_API_KEY_AQUI", "TU_API_SECRET_AQUI")


def problemas_credenciales() -> list:
    """Revisa el .env y devuelve los problemas encontrados (nunca muestra las claves)."""
    problemas = []
    for nombre, valor in (("VONAGE_API_KEY", VONAGE_API_KEY), ("VONAGE_API_SECRET", VONAGE_API_SECRET)):
        if valor in MARCADORES:
            problemas.append(f"{nombre} está vacío: pegá el valor después del = y guardá con Ctrl + S")
        elif " " in valor or "=" in valor:
            problemas.append(f"{nombre} tiene espacios o un '=': parece que todo quedó en UNA sola línea. "
                             "Cada variable va en su propia línea.")
    if problemas and not (CARPETA_BASE / ".env").exists():
        return ["No existe el archivo .env → abrí 0_configurar_credenciales.bat"]
    if MI_NUMERO_WHATSAPP and not MI_NUMERO_WHATSAPP.isdigit():
        problemas.append("MI_NUMERO_WHATSAPP solo lleva números: 503 + tus 8 dígitos (ej.: 50370123456)")
    return problemas


def credenciales_listas() -> bool:
    """True si el archivo .env ya tiene una API Key y un API Secret con formato válido."""
    return not any(p.startswith(("No existe", "VONAGE_API")) for p in problemas_credenciales())


def ocultar(valor: str) -> str:
    """Muestra solo el inicio y el final de un dato (para no exponer claves en pantalla)."""
    if len(valor) <= 4:
        return "•" * len(valor)
    return f"{valor[:2]}{'•' * min(len(valor) - 4, 8)}{valor[-2:]}"
