"""
evaluar_nlp.py - Evaluación del reconocimiento de intenciones y entidades.

Se le pasan frases de prueba con la respuesta correcta ya conocida (datos
etiquetados) y se mide qué porcentaje entiende bien el chatbot (exactitud).
Incluye frases con jerga salvadoreña, emojis y errores de ortografía.

Ejecutar desde la carpeta del proyecto:   python pruebas/evaluar_nlp.py
"""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import json  # noqa: E402

import config  # noqa: E402
from bot.nlp import AnalizadorNLP  # noqa: E402

# (frase del usuario, intención esperada)
FRASES_INTENCION = [
    ("hola", "saludo"), ("buenas tardes", "saludo"), ("qué onda", "saludo"), ("holaaa", "saludo"),
    ("buenos días guanaco", "saludo"),
    ("adiós", "despedida"), ("chao, nos vemos", "despedida"), ("eso es todo", "despedida"), ("bye", "despedida"),
    ("gracias", "agradecimiento"), ("muchas gracias, te pasaste", "agradecimiento"), ("mil gracias 🙏", "agradecimiento"),
    ("ayuda", "ayuda"), ("¿qué podés hacer?", "ayuda"), ("no sé qué hacer", "ayuda"), ("¿cómo funciona esto?", "ayuda"),
    ("menú", "menu"), ("volver al inicio", "menu"), ("opciones", "menu"),
    ("reiniciar", "reiniciar"), ("empezar de nuevo", "reiniciar"), ("cancelar", "reiniciar"),
    ("más opciones", "mas_opciones"), ("ver otros destinos", "mas_opciones"), ("siguiente", "mas_opciones"),
    ("recomiéndame un lugar", "recomendar"), ("quiero ir a la playa", "recomendar"),
    ("¿a dónde puedo ir este finde?", "recomendar"), ("quiero viajar con mi familia", "recomendar"),
    ("sugerime algo barato", "recomendar"), ("dónde puedo ir con mis cheros", "recomendar"),
    ("busco un destino tranquilo", "recomendar"), ("me gustaría ir a la montaña", "recomendar"),
    ("quiero conocer algo nuevo", "recomendar"), ("algún lugar para vacaciones", "recomendar"),
    ("info de Suchitoto", "info_destino"), ("contame del Tunco", "info_destino"),
    ("háblame de la Ruta de las Flores", "info_destino"), ("¿qué es Joya de Cerén?", "info_destino"),
    ("más información de El Pital", "info_destino"), ("detalles de Coatepeque", "info_destino"),
    ("¿dónde me puedo hospedar?", "hospedaje"), ("hoteles en El Tunco", "hospedaje"),
    ("hotles baratos", "hospedaje"), ("¿hay hostales en Suchitoto?", "hospedaje"),
    ("dónde dormimos en El Pital", "hospedaje"), ("quiero acampar", "hospedaje"),
    ("cabañas en la Ruta de las Flores", "hospedaje"),
    ("¿cómo llego a Suchitoto?", "transporte"), ("¿qué bus me lleva al Tunco?", "transporte"),
    ("¿cuánto tiempo se tarda a Perquín?", "transporte"), ("¿queda lejos El Cuco?", "transporte"),
    ("cómo llegar en carro", "transporte"), ("¿hay camioneta para La Palma?", "transporte"),
    ("transporte para el volcán", "transporte"),
    ("¿qué hacer en Ataco?", "actividades"), ("actividades en el Lago de Coatepeque", "actividades"),
    ("¿qué se puede hacer en El Zonte?", "actividades"), ("tours en Los Cóbanos", "actividades"),
    ("¿qué hay en Santa Tecla?", "actividades"), ("¿qué visitar en el centro histórico?", "actividades"),
    ("¿cómo está el clima en El Tunco?", "clima"), ("¿va a llover en Suchitoto?", "clima"),
    ("temperatura en El Pital", "clima"), ("¿hace frío en Alegría?", "clima"),
    ("pronóstico para el fin de semana", "clima"), ("¿está lloviendo en la playa?", "clima"),
    ("armame un itinerario", "itinerario"), ("planificá mi viaje de 3 días", "itinerario"),
    ("quiero un plan de 2 días en Santa Ana", "itinerario"), ("organizá mi fin de semana en el Boquerón", "itinerario"),
    ("itinerareo para Perquín", "itinerario"),
    ("¿cuánto cuesta ir a El Pital?", "presupuesto"), ("¿cuánto me sale un fin de semana en Coatepeque?", "presupuesto"),
    ("presupuesto para 4 personas", "presupuesto"), ("¿cuánto dinero necesito?", "presupuesto"),
    ("calculá mis gastos", "presupuesto"), ("¿cuánto pisto necesito para ir al Tunco?", "presupuesto"),
    ("¿cuándo es mejor ir a la playa?", "epoca"), ("mejor época para el volcán", "epoca"),
    ("¿en qué mes conviene ir a Suchitoto?", "epoca"),
    ("guardalo", "guardar_favorito"), ("guardar en favoritos", "guardar_favorito"),
    ("agregá este a favoritos", "guardar_favorito"),
    ("mis favoritos", "ver_favoritos"), ("ver mis guardados", "ver_favoritos"), ("¿qué tengo en favoritos?", "ver_favoritos"),
    ("mis planes", "ver_favoritos"), ("ver mi historial", "ver_favoritos"),
    ("guardar plan", "guardar_plan"), ("guardá el itinerario", "guardar_plan"), ("guardar mi viaje", "guardar_plan"),
    ("guardar este presupuesto", "guardar_plan"),
    ("privacidad", "privacidad"), ("¿qué datos guardás de mí?", "privacidad"), ("¿qué sabes de mí?", "privacidad"),
    ("borrar mis datos", "borrar_datos"), ("eliminá mis datos", "borrar_datos"), ("olvidame", "borrar_datos"),
    ("sorprendeme", "sorpresa"), ("elegí uno al azar", "sorpresa"), ("cualquiera, lo que sea", "sorpresa"),
    ("¿es seguro El Tunco?", "seguridad"), ("número de emergencia", "seguridad"),
    ("me robaron, ¿qué hago?", "seguridad"), ("consejos de seguridad", "seguridad"),
    ("¿dónde queda Juayúa?", "mapa"), ("mandame el mapa", "mapa"), ("ubicación de Tazumal", "mapa"),
    ("¿qué hay cerca de mí?", "cercanos"), ("lugares cercanos", "cercanos"), ("lo más cerca de aquí", "cercanos"),
    ("reservame un hotel", "fuera_alcance"), ("vuelos a Cancún", "fuera_alcance"),
    ("quiero ir a Guatemala", "fuera_alcance"), ("¿puedo pagar con tarjeta?", "fuera_alcance"),
    ("sos un inútil", "insulto"), ("qué bot más tonto", "insulto"),
]

# PRUEBA CIEGA: frases nuevas escritas DESPUÉS de programar el PLN (no se usaron para
# ajustarlo al inicio). Ronda 1: 24/30 = 80 %. Se analizaron los 6 errores, se mejoraron
# los patrones (ver documentación) y se volvió a medir (ronda 2).
FRASES_PRUEBA_CIEGA = [
    ("Buenas noches, ¿cómo estás?", "saludo"), ("Necesito ideas para salir el sábado", "recomendar"),
    ("¿Qué lugares bonitos hay para ir con niños?", "recomendar"), ("Quiero saber más sobre Perquín", "info_destino"),
    ("¿Dónde puedo quedarme en Juayúa?", "hospedaje"), ("¿Hay buses hacia Los Cóbanos?", "transporte"),
    ("¿Qué tan lejos está El Pital de San Salvador?", "transporte"), ("¿Qué actividades hay en Suchitoto?", "actividades"),
    ("¿Hará calor en Costa del Sol mañana?", "clima"), ("¿Cuánto gastaría en un viaje a Alegría?", "presupuesto"),
    ("Hazme un plan para 2 días", "itinerario"), ("¿Cuál es la mejor temporada para ir al Tunco?", "epoca"),
    ("Me encanta este lugar, guárdalo", "guardar_favorito"), ("Muéstrame mis lugares guardados", "ver_favoritos"),
    ("¿Cómo usan mi información?", "privacidad"), ("Quiero que borres todo lo mío", "borrar_datos"),
    ("Dame cualquier destino al azar", "sorpresa"), ("¿Es peligroso ir a la Puerta del Diablo?", "seguridad"),
    ("¿Me pasás la ubicación de Suchitoto en el mapa?", "mapa"), ("¿Qué destinos tengo cerca?", "cercanos"),
    ("¿Me podés reservar una habitación?", "fuera_alcance"), ("Quiero ir a Roatán", "fuera_alcance"),
    ("Gracias por la info", "agradecimiento"), ("Hasta luego", "despedida"), ("No entiendo cómo usarte", "ayuda"),
    ("Llevame al menú principal", "menu"), ("¿Qué me recomendás para un fin de semana romántico?", "recomendar"),
    ("¿Se puede acampar en El Pital?", "hospedaje"), ("¿Qué hay para comer en Juayúa?", "actividades"),
    ("Necesito el número de la policía", "seguridad"),
]

# (frase, entidades que deben aparecer)
FRASES_ENTIDADES = [
    ("quiero ir a la playa con mis cheros", {"tipo": "playa", "compania": "amigos"}),
    ("algo barato en la montaña con mi familia", {"tipo": "montana", "nivel": "economico", "compania": "familia"}),
    ("plan de 3 días para 4 personas", {"dias": 3, "personas": 4}),
    ("un finde en el Tunco", {"dias": 2, "destino": "el_tunco"}),
    ("tengo $150 para ir a Suchitoto", {"presupuesto": 150.0, "destino": "suchitoto"}),
    ("quiero subir al volcán de Santa Ana", {"destino": "volcan_santa_ana"}),
    ("hoteles en Santa Ana", {"destino": "santa_ana_ciudad"}),
    ("cómo llego a Juayúa", {"destino": "ruta_flores"}),
    ("info de suchitotto", {"destino": "suchitoto"}),
    ("de la capital a coatepeqe", {"destino": "lago_coatepeque"}),
    ("2 noches en El Pital", {"dias": 3, "destino": "el_pital"}),
    ("viaje romántico con mi novia", {"compania": "pareja"}),
    ("algo de lujo", {"nivel": "alto"}),
    ("me gusta el surf y la vida nocturna", {"intereses": ["surf", "vida_nocturna"]}),
    ("🏖️ con mis bichos", {"tipo": "playa", "compania": "familia"}),
    ("somos 5 cipotes", {"personas": 5, "compania": "familia"}),
]


def evaluar() -> float:
    with open(config.ARCHIVO_DESTINOS, encoding="utf-8") as archivo:
        nlp = AnalizadorNLP(json.load(archivo)["destinos"])

    print("=" * 70)
    print("  EVALUACIÓN DEL PLN - Guanaco Viajero")
    print("=" * 70)

    aciertos, por_intencion, errores = 0, defaultdict(lambda: [0, 0]), []
    for frase, esperada in FRASES_INTENCION:
        obtenida = nlp.analizar(frase).intencion
        por_intencion[esperada][1] += 1
        if obtenida == esperada:
            aciertos += 1
            por_intencion[esperada][0] += 1
        else:
            errores.append((frase, esperada, obtenida))

    print(f"\n1) INTENCIONES  ({len(FRASES_INTENCION)} frases de prueba)\n")
    print(f"   {'#Intención':<19}{'Aciertos':>10}{'Exactitud':>12}")
    for intencion, (bien, total) in sorted(por_intencion.items()):
        print(f"   {'#' + intencion:<19}{f'{bien}/{total}':>10}{100 * bien / total:>11.0f}%")
    exactitud = 100 * aciertos / len(FRASES_INTENCION)
    print(f"\n   ➜ EXACTITUD GENERAL: {aciertos}/{len(FRASES_INTENCION)} = {exactitud:.1f} %")
    if errores:
        print("\n   Frases no reconocidas correctamente:")
        for frase, esperada, obtenida in errores:
            print(f"   ✗ \"{frase}\" → esperaba {esperada}, obtuvo {obtenida}")

    bien_ciega = 0
    print(f"\n2) PRUEBA CIEGA  ({len(FRASES_PRUEBA_CIEGA)} frases nuevas)\n")
    for frase, esperada in FRASES_PRUEBA_CIEGA:
        obtenida = nlp.analizar(frase).intencion
        bien_ciega += obtenida == esperada
        if obtenida != esperada:
            print(f"   ✗ \"{frase}\" → esperaba {esperada}, obtuvo {obtenida}")
    print(f"   Ronda 1 (antes de mejorar): 24/30 = 80.0 %")
    print(f"   ➜ Ronda actual: {bien_ciega}/{len(FRASES_PRUEBA_CIEGA)} = "
          f"{100 * bien_ciega / len(FRASES_PRUEBA_CIEGA):.1f} %")

    bien_entidades = 0
    print(f"\n3) ENTIDADES  ({len(FRASES_ENTIDADES)} frases de prueba)\n")
    for frase, esperadas in FRASES_ENTIDADES:
        obtenidas = nlp.analizar(frase).entidades
        correcto = all(obtenidas.get(clave) == valor for clave, valor in esperadas.items())
        bien_entidades += correcto
        marca = "✓" if correcto else "✗"
        print(f"   {marca} \"{frase}\" → {', '.join(f'@{k}: {obtenidas.get(k)}' for k in esperadas)}")
    print(f"\n   ➜ EXACTITUD DE ENTIDADES: {bien_entidades}/{len(FRASES_ENTIDADES)} = "
          f"{100 * bien_entidades / len(FRASES_ENTIDADES):.1f} %")
    print("=" * 70)
    return exactitud


if __name__ == "__main__":
    evaluar()
