"""
servicios.py - Integración con servicios externos.

  * Clima en tiempo real: API pública y gratuita de Open-Meteo (no necesita clave).
  * Mapas: enlace de búsqueda de Google Maps (formato oficial "Maps URLs").

Si no hay internet o el servicio falla, el bot NO se cae: devuelve None y el
motor de conversación muestra un mensaje amable.
"""
from __future__ import annotations

import time
from datetime import date
from urllib.parse import quote_plus

import requests

import config

URL_CLIMA = "https://api.open-meteo.com/v1/forecast"

# Códigos de clima WMO que usa Open-Meteo -> texto en español
CODIGOS_CLIMA = {
    0: "Despejado ☀️", 1: "Mayormente despejado 🌤️", 2: "Parcialmente nublado ⛅", 3: "Nublado ☁️",
    45: "Neblina 🌫️", 48: "Neblina 🌫️", 51: "Llovizna ligera 🌦️", 53: "Llovizna 🌦️",
    55: "Llovizna fuerte 🌦️", 56: "Llovizna helada", 57: "Llovizna helada", 61: "Lluvia ligera 🌧️",
    63: "Lluvia 🌧️", 65: "Lluvia fuerte 🌧️", 66: "Lluvia helada", 67: "Lluvia helada",
    80: "Chubascos 🌦️", 81: "Chubascos 🌧️", 82: "Chubascos fuertes ⛈️", 95: "Tormenta ⛈️",
    96: "Tormenta con granizo ⛈️", 99: "Tormenta con granizo ⛈️",
}
DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

_cache_clima = {}   # destino_id -> (momento_de_consulta, datos)


def describir_codigo(codigo) -> str:
    return CODIGOS_CLIMA.get(codigo, "Variable 🌥️")


def obtener_clima(destino: dict):
    """Consulta el clima actual y el pronóstico de 3 días. Devuelve dict o None."""
    guardado = _cache_clima.get(destino["id"])
    if guardado and time.time() - guardado[0] < config.MINUTOS_CACHE_CLIMA * 60:
        return guardado[1]

    parametros = {
        "latitude": destino["lat"],
        "longitude": destino["lon"],
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "forecast_days": 3,
        "timezone": "America/El_Salvador",
    }
    try:
        respuesta = requests.get(URL_CLIMA, params=parametros, timeout=config.SEGUNDOS_API_CLIMA)
        respuesta.raise_for_status()
        datos = respuesta.json()
        datos["current"]["temperature_2m"]          # valida que vengan los campos esperados
        datos["daily"]["time"]
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None

    _cache_clima[destino["id"]] = (time.time(), datos)
    return datos


def texto_clima(destino: dict, datos: dict) -> str:
    """Convierte la respuesta de la API en un mensaje para WhatsApp."""
    actual = datos["current"]
    diario = datos["daily"]
    lineas = [
        f"🌤️ *Clima en {destino['nombre']}* (ahora)",
        f"🌡️ {actual['temperature_2m']:.0f} °C (sensación {actual['apparent_temperature']:.0f} °C) · "
        f"{describir_codigo(actual['weather_code'])}",
        f"💧 Humedad {actual['relative_humidity_2m']:.0f} % · 💨 Viento {actual['wind_speed_10m']:.0f} km/h",
        "",
        "📅 *Próximos días:*",
    ]
    lluvia_alta = False
    for i, fecha_texto in enumerate(diario["time"]):
        fecha = date.fromisoformat(fecha_texto)
        nombre_dia = "Hoy" if i == 0 else f"{DIAS_SEMANA[fecha.weekday()].capitalize()} {fecha.day}"
        prob = diario["precipitation_probability_max"][i]
        prob_texto = f"{prob:.0f} %" if prob is not None else "s/d"
        if prob is not None and prob >= 50:
            lluvia_alta = True
        lineas.append(f"• {nombre_dia}: {diario['temperature_2m_max'][i]:.0f}° / "
                      f"{diario['temperature_2m_min'][i]:.0f}° · lluvia {prob_texto}")

    if lluvia_alta:
        lineas.append("\n💡 Llevá sombrilla o capa: hay buena probabilidad de lluvia.")
    elif actual["temperature_2m"] >= 30:
        lineas.append("\n💡 Hace calor: llevá agua, gorra y bloqueador.")
    elif actual["temperature_2m"] <= 18:
        lineas.append("\n💡 Está fresco: llevá suéter o chumpa.")
    lineas.append("_Fuente: Open-Meteo (datos en tiempo real)_")
    return "\n".join(lineas)


def enlace_mapa(destino: dict) -> str:
    """Enlace de Google Maps para buscar el destino (no requiere clave)."""
    return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(destino["mapa"])
