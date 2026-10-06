"""
mensajes.py - Textos del chatbot (tono amable, cercano y salvadoreño).

Tener los textos separados de la lógica es una buena práctica: si se quiere
cambiar la forma de hablar del bot, solo se edita este archivo.
"""
import random

MENU_PRINCIPAL = (
    "*¿Qué querés hacer?*\n"
    "1️⃣ Recomendame un destino\n"
    "2️⃣ Info de un lugar\n"
    "3️⃣ Armar un itinerario\n"
    "4️⃣ Calcular presupuesto\n"
    "5️⃣ Ver el clima\n"
    "6️⃣ Mis favoritos y planes 💾\n"
    "7️⃣ Sorprendeme 🎲\n"
    "8️⃣ Consejos de seguridad 🚨\n"
    "9️⃣ Privacidad 🔒\n\n"
    "✍️ Escribí el *número* o contame con tus palabras.\n"
    "📍 También podés mandarme tu *ubicación* y te digo qué hay cerca."
)


def bienvenida(nombre: str = "") -> str:
    saludo = f"¡Hola, {nombre}! 👋" if nombre else "¡Hola! 👋"
    return (
        f"{saludo} Soy *Guanaco Viajero* 🇸🇻, tu guía para descubrir lo mejor de El Salvador.\n"
        "Te ayudo a elegir destino y a ver hospedaje, cómo llegar, actividades, clima, "
        "itinerarios y presupuesto.\n\n" + MENU_PRINCIPAL
    )


AYUDA = (
    "🤖 *¿Cómo hablarme?*\n"
    "Podés usar el menú con números o escribirme normal, por ejemplo:\n"
    "• _Quiero ir a la playa con mis cheros_\n"
    "• _¿Cómo llego a Suchitoto?_\n"
    "• _Hoteles baratos en El Tunco_\n"
    "• _Armame un itinerario de 2 días en la Ruta de las Flores_\n"
    "• _¿Cuánto me sale ir a El Pital 2 días con 3 personas?_\n"
    "• _¿Cómo está el clima en Coatepeque?_\n"
    "• _guardar plan_ (después de un itinerario o presupuesto)\n"
    "• 📍 Mandame tu ubicación y te digo qué hay cerca\n\n"
    "Comandos: *menú* · *mis planes* · *reiniciar* · *privacidad* · *salir*"
)

PREGUNTA_TIPO = (
    "¡De una! 🙌 ¿Qué tipo de lugar te late más?\n"
    "1️⃣ Playa 🏖️\n"
    "2️⃣ Montaña ⛰️\n"
    "3️⃣ Ciudad y cultura 🏙️\n\n"
    "_Tip: podés darme más detalles, ej. \"montaña barata con mi familia\"._"
)

PREGUNTA_DESTINO = (
    "¿De qué lugar? 🤔 Escribime el nombre, por ejemplo:\n"
    "_Suchitoto, El Tunco, Ruta de las Flores, El Pital, Coatepeque..._\n"
    "O escribí *1* para que te recomiende uno."
)

PREGUNTA_DIAS = "¿Cuántos días vas a ir? 🗓️ Escribí un número (por ejemplo *2*)."
PREGUNTA_PERSONAS = "¿Cuántas personas van? 👥 Escribí un número (por ejemplo *3*)."
PREGUNTA_NIVEL = (
    "¿Qué nivel de gasto preferís? 💵\n"
    "1️⃣ Económico (bus, hostal)\n"
    "2️⃣ Medio (carro, hotel sencillo)\n"
    "3️⃣ Alto (hotel boutique o resort)"
)

FICHA_OPCIONES = (
    "*¿Qué querés saber?*\n"
    "1️⃣ Hospedaje 🏨\n"
    "2️⃣ Cómo llegar 🚌\n"
    "3️⃣ Actividades 🎯\n"
    "4️⃣ Clima ahora 🌤️\n"
    "5️⃣ Itinerario 🗓️\n"
    "6️⃣ Presupuesto 💵\n"
    "7️⃣ Guardar en favoritos ⭐\n"
    "8️⃣ Ver en el mapa 📍\n"
    "0️⃣ Menú principal"
)

GUARDAR_PLAN = "💾 Escribí *guardar plan* para guardarlo en tu historial."

PIE_FICHA = "↩️ Escribí otro número para ver más de *{nombre}*, *menú* para volver o *no, gracias* para salir."

SEGURIDAD = (
    "🚨 *Consejos para viajar seguro*\n"
    "• Emergencias: llamá al *911* (policía, emergencias médicas y bomberos).\n"
    "• Compartí tu itinerario y ubicación con alguien de confianza.\n"
    "• En la playa: respetá las banderas y no te metás al mar con corrientes fuertes ni de noche.\n"
    "• En volcanes y senderos: andá con guía autorizado y salí temprano.\n"
    "• Llevá agua, bloqueador y gorra; hidratate bien.\n"
    "• Cuidá tus pertenencias en lugares concurridos.\n"
    "• En época lluviosa (mayo a octubre) revisá el clima antes de salir.\n"
    "• Respetá la naturaleza y no dejés basura 🌱."
)

PRIVACIDAD = (
    "🔒 *Tu privacidad*\n"
    "• No guardo tu número ni tu nombre: los convierto en un código anónimo (hash SHA-256).\n"
    "• No guardo el texto de tus mensajes ni tu ubicación 📍.\n"
    "• En mi base de datos (SQLite) solo guardo tus favoritos y planes si me das permiso.\n"
    "• El contexto de la charla (de qué destino hablamos) se borra solo a los 30 minutos.\n"
    "• Mis respuestas vienen de una base de datos revisada, no de una IA que invente datos.\n"
    "• WhatsApp y Vonage (el servicio que me conecta) tienen sus propias políticas de privacidad.\n"
    "_Basado en la Ley para la Protección de Datos Personales de El Salvador (2024)._"
)

PEDIR_CONSENTIMIENTO = (
    "💾 Para guardar tus favoritos y planes necesito tu permiso para almacenar en mi base de datos:\n"
    "• un código anónimo (no tu número) y\n"
    "• los destinos y planes que guardés.\n"
    "Podés borrarlo cuando querás escribiendo *borrar mis datos*.\n\n"
    "¿Aceptás? Respondé *sí* o *no*."
)

CONFIRMAR_BORRADO = (
    "🗑️ ¿Seguro que querés borrar *todos* tus datos (favoritos, planes y permiso)? "
    "Esta acción no se puede deshacer.\nRespondé *sí* o *no*."
)

PEDIR_UBICACION = (
    "📍 ¡Va! Mandame tu ubicación así:\n"
    "Tocá el clip 📎 (o el +) → *Ubicación* → *Enviar mi ubicación actual*.\n"
    "Te digo qué destinos te quedan más cerca. No guardo tu ubicación 🔒"
)

MULTIMEDIA = (
    "📷 ¡Gracias! Por ahora solo entiendo *texto* y *ubicación* 📍.\n"
    "Escribime lo que buscás o escribí *menú*."
)

FUERA_DE_ALCANCE = (
    "🙏 Por ahora solo te ayudo con destinos *dentro de El Salvador* 🇸🇻 y no hago reservas, "
    "pagos ni venta de boletos.\nPara reservar, contactá directamente al hotel o a una agencia."
)

FUERA_CON_DESTINO = ("🙏 Solo manejo destinos *dentro de El Salvador* 🇸🇻 y no hago reservas ni pagos, "
                     "pero te dejo esta info 👇")

INSULTO = (
    "Entiendo que te frustres 😔. Estoy aprendiendo y quiero ayudarte.\n"
    "Contame qué buscás con otras palabras o escribí *menú* para ver las opciones."
)

AVISO_REFERENCIAL = "\nℹ️ _Datos referenciales: precios, horarios y rutas pueden cambiar. Verificá antes de viajar._"

NO_ENTENDI = [
    "¡Puchica! 😅 No te entendí bien. Probá con algo como: _quiero ir a la playa_, "
    "_hoteles en Suchitoto_ o escribí *menú*.",
    "Mmm, eso no lo capté 🤔. Puedo recomendarte destinos, decirte cómo llegar, dónde "
    "hospedarte, el clima y más. Escribí *ayuda* para ver ejemplos.",
    "Perdón, no logré entenderte 🙈. ¿Me lo decís de otra forma? Por ejemplo: "
    "_algo barato en la montaña_ o *menú*.",
]


def no_entendi() -> str:
    return random.choice(NO_ENTENDI)


def despedida(nombre: str = "") -> str:
    quien = f", {nombre}" if nombre else ""
    return (
        f"¡Que tengás un excelente viaje{quien}! 🇸🇻✈️\n"
        "Antes de irte, ¿me calificás del *1 al 5*? ⭐ (escribí solo el número)\n"
        "Cuando querás volver a planear, escribime *hola*."
    )


def gracias_calificacion(valor: int) -> str:
    if valor >= 4:
        return f"¡Qué chivo! 🙌 Gracias por tu calificación ({valor}/5). ¡Buen viaje!"
    if valor == 3:
        return f"¡Gracias por tu calificación ({valor}/5)! Voy a seguir mejorando 💪"
    return (f"Gracias por tu sinceridad ({valor}/5) 🙏. Tu opinión me ayuda a mejorar. "
            "Si querés, contame qué faltó.")
