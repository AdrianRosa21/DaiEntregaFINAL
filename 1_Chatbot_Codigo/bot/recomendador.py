"""
recomendador.py - Algoritmo que elige los mejores destinos para cada usuario.

Funciona con un sistema de PUNTOS (puntuación por criterios):
  + coincide el tipo de lugar (playa / montaña / ciudad)
  + coincide con sus intereses (surf, historia, comida...)
  + es ideal para su compañía (familia, pareja, amigos, solo)
  + se ajusta a su nivel de gasto o presupuesto
  - queda muy lejos para un viaje de un solo día
Gana el destino con más puntos, y el bot explica POR QUÉ lo recomienda.
"""
from __future__ import annotations

import math

NIVELES = ["economico", "medio", "alto"]

NOMBRE_TIPO = {"playa": "playa", "montana": "montaña", "ciudad": "ciudad y cultura"}
EMOJI_TIPO = {"playa": "🏖️", "montana": "⛰️", "ciudad": "🏙️"}

NOMBRE_INTERES = {
    "surf": "surf", "senderismo": "senderismo", "historia": "historia", "gastronomia": "buena comida",
    "naturaleza": "naturaleza", "aventura": "aventura", "relax": "descanso", "fotografia": "lindas vistas",
    "vida_nocturna": "vida nocturna", "cultura": "cultura", "compras": "compras", "cafe": "café",
}
TEXTO_COMPANIA = {"familia": "en familia", "pareja": "en pareja", "amigos": "con amigos", "solo": "solo/a"}


def puntuar(destino: dict, perfil: dict):
    """Calcula los puntos de un destino para el perfil del usuario.

    Devuelve (puntos, razones) o None si el destino no es del tipo pedido.
    """
    puntos, razones = 0.0, []

    tipo = perfil.get("tipo")
    if tipo:
        if destino["tipos"][0] == tipo:
            puntos += 6
        elif tipo in destino["tipos"]:
            puntos += 4
        else:
            return None                      # no es del tipo que pidió: se descarta
        razones.append(f"{EMOJI_TIPO[tipo]} es de {NOMBRE_TIPO[tipo]}")

    for interes in perfil.get("intereses", []):
        if interes in destino["intereses"]:
            puntos += 3
            razones.append(f"tiene {NOMBRE_INTERES[interes]}")

    compania = perfil.get("compania")
    if compania and compania in destino["ideal_para"]:
        puntos += 2
        razones.append(f"ideal para ir {TEXTO_COMPANIA[compania]}")

    nivel = perfil.get("nivel")
    if nivel:
        diferencia = abs(NIVELES.index(nivel) - NIVELES.index(destino["nivel_costo"]))
        puntos += 2 - 2 * diferencia
        if diferencia == 0:
            razones.append("se ajusta a tu nivel de gasto")

    dias = perfil.get("dias")
    if dias == 1 and destino["horas"] > 2.5:
        puntos -= 3                          # muy lejos para ir y volver el mismo día
    elif dias and dias >= 2 and destino["horas"] >= 2.5:
        puntos += 1                          # vale la pena si hay más tiempo

    puntos += destino.get("prioridad", 1) * 0.5   # desempate: destinos más visitados
    return puntos, razones


def recomendar(destinos: list, perfil: dict, excluir=(), cantidad: int = 3) -> list:
    """Devuelve una lista ordenada de (destino, puntos, razones)."""
    resultados = []
    for destino in destinos:
        if destino["id"] in excluir:
            continue
        evaluacion = puntuar(destino, perfil)
        if evaluacion is not None:
            resultados.append((destino, evaluacion[0], evaluacion[1]))
    resultados.sort(key=lambda r: r[1], reverse=True)
    return resultados[:cantidad]


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en línea recta entre dos coordenadas (fórmula de Haversine)."""
    radio_tierra = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * radio_tierra * math.asin(math.sqrt(a))


def cercanos(destinos: list, lat: float, lon: float, cantidad: int = 3) -> list:
    """Devuelve [(destino, km)] ordenados del más cercano al más lejano."""
    lista = [(d, distancia_km(lat, lon, d["lat"], d["lon"])) for d in destinos]
    lista.sort(key=lambda par: par[1])
    return lista[:cantidad]
