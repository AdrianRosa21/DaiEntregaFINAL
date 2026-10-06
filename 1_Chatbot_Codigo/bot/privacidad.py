"""
privacidad.py - Anonimización de los números de WhatsApp.

El número de teléfono solo se usa en memoria para contestar; en la base de
datos se guarda un código anónimo calculado con SHA-256 + una "sal" secreta.
El hash no se puede revertir: nadie puede saber el número a partir del código.
"""
import hashlib

import config


def anonimizar(numero: str) -> str:
    """Convierte '50370000000' en un código anónimo de 16 caracteres."""
    texto = (config.SAL_PRIVACIDAD + (numero or "").lstrip("+")).encode("utf-8")
    return hashlib.sha256(texto).hexdigest()[:16]
