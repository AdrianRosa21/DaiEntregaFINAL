"""
planificador.py - Innovaciones: itinerario automático y calculadora de presupuesto.

IMPORTANTE (uso responsable): los costos son VALORES DE REFERENCIA aproximados
definidos por el autor con fines educativos. No son cotizaciones reales; el bot
siempre se lo aclara al usuario.
"""
from __future__ import annotations

# Costos de referencia en dólares (USD), por persona
COSTOS_REFERENCIA = {
    #              hospedaje x noche   comida x día   actividades x día
    "economico": {"hospedaje": 15, "comida": 12, "actividades": 5},
    "medio":     {"hospedaje": 35, "comida": 25, "actividades": 15},
    "alto":      {"hospedaje": 80, "comida": 45, "actividades": 35},
}
BUS_POR_HORA = 1.0    # pasaje aproximado de bus por cada hora de viaje (un sentido)
CARRO_POR_HORA = 10   # combustible aproximado por hora de viaje, ida y vuelta, por grupo

NOMBRE_NIVEL = {"economico": "económico", "medio": "medio", "alto": "alto"}


def generar_itinerario(destino: dict, dias: int, por_id: dict = None) -> str:
    """Arma un plan día por día con las actividades del destino."""
    dias = max(1, min(int(dias), 3))
    actividades = list(destino["actividades"])

    # Si faltan actividades para llenar los días, se agregan lugares cercanos
    for cercano_id in destino.get("cercanos", []):
        if por_id and cercano_id in por_id:
            actividades.append(f"Excursión a {por_id[cercano_id]['nombre']}")

    lineas = [f"🗓️ *Itinerario de {dias} día{'s' if dias > 1 else ''} en {destino['nombre']}*"]
    indice = 0
    for dia in range(1, dias + 1):
        lineas.append(f"\n*Día {dia}*")
        if dia == 1:
            lineas.append(f"🚗 Salida temprano desde San Salvador ({destino['tiempo']})")
        for momento in ("🌅 Mañana", "☀️ Tarde"):
            if indice < len(actividades):
                lineas.append(f"{momento}: {actividades[indice]}")
            else:
                lineas.append(f"{momento}: tiempo libre para descansar o repetir lo que más te gustó")
            indice += 1
        if dia < dias:
            lineas.append(f"🌙 Noche: {destino['noche']}")
        else:
            lineas.append("🏠 Regreso a casa con calma (mejor antes de que oscurezca)")
    lineas.append(f"\n💡 {destino['consejo']}")
    return "\n".join(lineas)


def estimar_presupuesto(destino: dict, dias: int, personas: int, nivel: str) -> dict:
    """Calcula un presupuesto aproximado y devuelve el detalle por rubro."""
    dias = max(1, int(dias))
    personas = max(1, int(personas))
    costos = COSTOS_REFERENCIA[nivel]
    noches = dias - 1

    hospedaje = costos["hospedaje"] * noches * personas
    comida = costos["comida"] * dias * personas
    actividades = costos["actividades"] * dias * personas
    if nivel == "economico":   # en bus: cada persona paga su pasaje de ida y vuelta
        transporte = round(BUS_POR_HORA * destino["horas"] * 2 * personas + personas, 2)
        medio_transporte = "bus"
    else:                      # en carro: el combustible se comparte
        transporte = round(CARRO_POR_HORA * max(destino["horas"], 0.5), 2)
        medio_transporte = "carro"

    total = hospedaje + comida + actividades + transporte
    return {
        "dias": dias, "noches": noches, "personas": personas, "nivel": nivel,
        "hospedaje": hospedaje, "comida": comida, "actividades": actividades,
        "transporte": transporte, "medio_transporte": medio_transporte,
        "total": round(total, 2), "por_persona": round(total / personas, 2),
    }


def texto_presupuesto(destino: dict, p: dict, presupuesto_usuario: float = None) -> str:
    """Convierte el cálculo en un mensaje claro para WhatsApp."""
    lineas = [
        f"💵 *Presupuesto estimado: {destino['nombre']}*",
        f"{p['dias']} día(s) · {p['personas']} persona(s) · nivel {NOMBRE_NIVEL[p['nivel']]}",
        "",
        f"🏨 Hospedaje ({p['noches']} noche/s): ${p['hospedaje']:,.2f}",
        f"🍽️ Comida: ${p['comida']:,.2f}",
        f"🎯 Actividades y entradas: ${p['actividades']:,.2f}",
        f"{'🚌' if p['medio_transporte'] == 'bus' else '🚗'} Transporte ({p['medio_transporte']}): "
        f"${p['transporte']:,.2f}",
        "",
        f"*Total ≈ ${p['total']:,.2f}* (≈ ${p['por_persona']:,.2f} por persona)",
    ]
    if presupuesto_usuario:
        diferencia = presupuesto_usuario - p["total"]
        if diferencia >= 0:
            lineas.append(f"✅ Tu presupuesto de ${presupuesto_usuario:,.0f} alcanza (te sobran ≈ ${diferencia:,.0f}).")
        else:
            lineas.append(f"⚠️ Con ${presupuesto_usuario:,.0f} te faltarían ≈ ${-diferencia:,.0f}. "
                          "Probá con nivel económico o menos días.")
    lineas.append("\nℹ️ _Cálculo aproximado con valores de referencia; los precios reales pueden variar._")
    return "\n".join(lineas)
