"""
nlp.py - Procesamiento de Lenguaje Natural (PLN) de Guanaco Viajero.

Cada mensaje del usuario pasa por este "pipeline" (cadena de pasos):

  1. Normalización ........ minúsculas, sin tildes ni signos, emojis -> palabras
  2. Jerga y abreviaturas .. "cheros" -> amigos, "finde" -> fin de semana, "k" -> que
  3. Tokenización .......... separar el texto en palabras (tokens)
  4. Corrección ortográfica  "plaia" -> playa, "suchitotto" -> suchitoto (difflib)
  5. Intención ............. ¿QUÉ quiere el usuario? (recomendar, hospedaje, clima...)
  6. Entidades ............. ¿CON QUÉ DATOS? (destino, tipo, días, personas, presupuesto...)

No usa IA generativa: usa reglas, palabras clave con pesos y similitud de
texto. Así las respuestas son predecibles y no se "inventan" datos.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher, get_close_matches
from typing import Optional

# ---------------------------------------------------------------------------
# 1) Emojis que sí significan algo para el bot
# ---------------------------------------------------------------------------
EMOJIS = {
    "👍": " si ", "👌": " si ", "✅": " si ", "👎": " no ", "❌": " no ",
    "👋": " hola ", "🙏": " gracias ",
    "🏖": " playa ", "🏝": " playa ", "🌊": " playa ", "🏄": " surf ",
    "⛰": " montana ", "🏔": " montana ", "🌋": " volcan ", "🌲": " montana ",
    "🏙": " ciudad ", "🌆": " ciudad ", "🏛": " historia ",
}

# ---------------------------------------------------------------------------
# 2) Jerga salvadoreña y abreviaturas de chat -> español estándar
# ---------------------------------------------------------------------------
JERGA = {
    "cheros": "amigos", "chero": "amigo", "cheras": "amigas", "chera": "amiga",
    "compas": "amigos", "panas": "amigos",
    "bichos": "ninos", "bichas": "ninas", "bicho": "nino", "bicha": "nina",
    "cipotes": "ninos", "cipotas": "ninas", "cipote": "nino", "cipota": "nina",
    "pisto": "dinero", "chivo": "genial", "chiva": "genial", "chivisimo": "genial",
    "simon": "si", "sip": "si", "nel": "no", "nop": "no", "nones": "no",
    "finde": "fin de semana",
    "k": "que", "q": "que", "ke": "que", "xq": "porque", "pq": "porque",
    "x": "por", "d": "de", "pa": "para", "tmb": "tambien", "tb": "tambien",
    "porfa": "por favor", "porfis": "por favor", "plis": "por favor", "pls": "por favor",
    "kiero": "quiero", "qiero": "quiero", "kisiera": "quisiera", "salu2": "saludos",
    "camioneta": "bus", "busito": "bus",
}

# Palabras escritas con números -> número
NUMEROS_TEXTO = {
    "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
}

# ---------------------------------------------------------------------------
# 5) Intenciones: lista de patrones por intención
#    "palabra"      -> la palabra exacta
#    "raiz*"        -> cualquier palabra que empiece así (hosped* = hospedaje, hospedarme...)
#    "dos palabras" -> frase; pesa más (1 punto por cada palabra)
# ---------------------------------------------------------------------------
INTENCIONES = {
    "saludo": ["hola", "holis", "holi", "buenas", "buenos dias", "buen dia", "buenas tardes",
               "buenas noches", "que onda", "que ondas", "que tal", "hey", "saludos", "hello", "alo"],
    "despedida": ["adios", "chao", "chau", "bye", "nos vemos", "hasta luego", "hasta pronto",
                  "eso es todo", "es todo", "me voy", "salir del chat", "terminar la conversacion",
                  "no gracias"],
    "agradecimiento": ["gracias", "muchas gracias", "mil gracias", "te pasaste", "que amable", "thanks",
                       "gracias por la info", "gracias por la informacion", "gracias por la ayuda",
                       "gracias por todo"],
    "ayuda": ["ayuda", "ayudame", "help", "como funciona", "que podes hacer", "que puedes hacer",
              "que haces", "como te uso", "instrucciones", "ejemplos", "no se que hacer", "no entiendo",
              "comandos"],
    "menu": ["menu", "menu principal", "opciones", "inicio", "volver", "regresar"],
    "reiniciar": ["reiniciar", "reinicia", "empezar de nuevo", "comenzar de nuevo", "reset",
                  "cancelar", "cancela"],
    "recomendar": ["recomend*", "recomiend*", "suger*", "sugier*", "quiero ir", "quisiera ir",
                   "queremos ir", "me gustaria ir", "donde ir", "a donde", "adonde", "donde puedo ir",
                   "lugar", "lugares", "destino", "destinos", "viaj*", "pasear", "paseo", "paseito",
                   "vacaciones", "conocer", "turistear", "escapada", "salir de paseo", "a donde voy",
                   "algun lugar", "que me recomendas", "ideas", "idea", "para salir", "salir a"],
    "info_destino": ["info", "informacion", "contame", "cuentame", "hablame", "detalles", "como es",
                     "que tal es", "describi", "describe", "saber mas", "mas informacion", "mas info",
                     "que es"],
    "hospedaje": ["hotel", "hoteles", "hosped*", "aloj*", "dorm*", "quedarme", "quedarnos",
                  "donde me quedo", "donde nos quedamos", "hostal", "hostales", "hostel", "cabana",
                  "cabanas", "glamping", "airbnb", "posada", "acampar", "camping", "resort",
                  "donde duermo"],
    "transporte": ["como llego", "como llegar", "como llegamos", "como voy", "como me voy", "transporte",
                   "bus", "buses", "ruta de bus", "rutas de bus", "autobus", "carro", "vehiculo",
                   "manejar", "llegar", "distancia", "que tan lejos", "queda lejos", "lejos",
                   "cuanto tiempo", "cuanto se tarda", "cuanto tarda", "uber", "taxi", "terminal",
                   "en bus", "en carro"],
    "actividades": ["que hacer", "que hago", "que puedo hacer", "que se puede hacer", "actividad*",
                    "que hay", "atraccion*", "tour", "tours", "divertir*", "que visitar", "que ver",
                    "que conocer"],
    "clima": ["clima", "temperatura", "llov*", "lluv*", "llue*", "pronostico", "el tiempo",
              "como esta el tiempo", "que tiempo hace", "hace frio", "hace calor", "hace sol",
              "hara frio", "hara calor", "hara sol", "va a hacer frio", "va a hacer calor",
              "soleado", "nublado", "grados"],
    "itinerario": ["itinerario*", "planific*", "planea*", "organiz*", "agenda", "cronograma",
                   "plan de viaje", "plan de", "plan para", "un plan", "mi plan", "armame", "arma un",
                   "armar un", "hazme un plan", "haceme un plan", "programa", "dia por dia"],
    "presupuesto": ["presupuest*", "cuanto cuesta", "cuanto cuestan", "cuanto gasto", "cuanto gastaria",
                    "cuanto sale", "cuanto me sale", "cuanto nos sale", "cuanto necesito",
                    "cuanto dinero", "precio", "precios", "costo", "costos", "gastar", "dinero",
                    "calcul*", "cuanto vale", "cuanto cobran", "tarifa*"],
    "epoca": ["cuando ir", "cuando es mejor", "mejor epoca", "mejor mes", "temporada", "que mes",
              "en que mes", "cuando visitar", "cuando conviene"],
    "guardar_plan": ["guardar plan", "guarda el plan", "guardar el plan", "guardar este plan",
                     "guardar mi plan", "guardar itinerario", "guardar el itinerario",
                     "guardar presupuesto", "guardar el presupuesto", "guardar viaje", "guardar mi viaje"],
    "guardar_favorito": ["guardar", "guarda", "guardalo", "guardame", "guardar en favoritos",
                         "agregar a favoritos", "agrega*", "anadir", "anadelo", "me gusta este",
                         "me encanta este", "favorito"],
    "ver_favoritos": ["mis favoritos", "ver favoritos", "favoritos", "mis guardados", "guardados",
                      "mi lista", "lista de favoritos", "mis planes", "mis viajes", "planes guardados",
                      "historial", "mi historial"],
    "privacidad": ["privacidad", "mis datos", "que datos", "datos personales", "que guardas",
                   "que sabes de mi", "politica", "terminos", "proteccion de datos", "mi informacion"],
    "borrar_datos": ["borrar mis datos", "borra mis datos", "eliminar mis datos", "elimina mis datos",
                     "borrar datos", "eliminar datos", "olvidame", "borrar todo", "borra todo",
                     "eliminar todo", "borrar favoritos", "eliminar favoritos", "borr*", "elimin*"],
    "sorpresa": ["sorprend*", "sorpresa", "aleatorio", "al azar", "random", "cualquiera",
                 "lo que sea", "dado"],
    "seguridad": ["emergencia*", "segur*", "policia", "accidente", "robo", "robaron", "asalt*",
                  "perdido", "perdida", "peligro*", "consejos", "numero de emergencia", "911",
                  "auxilio", "socorro", "hospital", "me robaron", "me asaltaron", "estoy perdido",
                  "estoy perdida", "tuve un accidente"],
    "mapa": ["mapa", "ubicacion", "donde queda", "donde esta", "google maps", "maps",
             "localizacion", "como lo encuentro", "direccion"],
    "cercanos": ["cerca de mi", "cerca de aqui", "cercanos", "cercano", "mas cerca", "aqui cerca",
                 "por aqui", "mi ubicacion", "cerca de donde estoy", "tengo cerca", "hay cerca"],
    "mas_opciones": ["mas opciones", "ver mas", "otras opciones", "otros destinos", "otros lugares",
                     "otras", "otros", "siguiente", "mas"],
    "fuera_alcance": ["reservar", "reservame", "reservacion", "reservaciones", "hacer una reserva",
                      "pagar", "pago", "tarjeta", "comprar boleto", "comprar boletos", "boleto de avion",
                      "vuelo", "vuelos", "avion", "aerolinea", "visa", "pasaporte", "crucero"],
    "insulto": ["tonto", "tonta", "estupido", "estupida", "idiota", "inutil", "baboso", "babosa",
                "no servis", "no sirves", "sos malo", "eres malo"],
}

# Lugares fuera de El Salvador: si aparecen, la petición está fuera del alcance del bot
LUGARES_EXTRANJEROS = ["guatemala", "honduras", "nicaragua", "costa rica", "mexico", "cancun", "roatan",
                       "panama", "estados unidos", "europa", "miami", "disney", "espana", "colombia",
                       "peru", "nueva york"]

# Intenciones de cortesía: siempre pesan poco para no "tapar" la petición real.
# Ej.: "hola, ¿cómo llego a Suchitoto?" -> gana transporte, no saludo.
CORTESIA = {"saludo", "agradecimiento"}

# Si dos intenciones empatan, gana la que aparece primero en esta lista
PRIORIDAD = [
    "borrar_datos", "insulto", "fuera_alcance", "guardar_plan", "guardar_favorito", "ver_favoritos",
    "privacidad",
    "cercanos", "presupuesto", "itinerario", "clima", "epoca", "hospedaje", "transporte",
    "actividades", "mapa", "seguridad", "sorpresa", "mas_opciones", "info_destino", "recomendar",
    "reiniciar", "menu", "ayuda", "despedida", "agradecimiento", "saludo",
]

# ---------------------------------------------------------------------------
# 6) Diccionarios de entidades
# ---------------------------------------------------------------------------
TIPOS = {
    "playa": ["playa*", "mar", "costa", "surf*", "olas", "arena", "bronce*", "puerto", "malecon",
              "snorkel", "bucear", "buceo", "calor", "calorcito"],
    "montana": ["montan*", "volcan*", "cerro*", "frio", "fresco", "fresquito", "bosque*", "sender*",
                "caminata*", "pino*", "cafe", "cafetal*", "pueblo*", "cascada*", "lago*", "laguna*",
                "acampar", "camping", "naturaleza", "campo", "hiking"],
    "ciudad": ["ciudad*", "centro", "urbano", "museo*", "histori*", "cultur*", "colonial*", "compras",
               "mall", "centro comercial", "teatro*", "catedral*", "iglesia*", "arquitectura",
               "arqueolog*", "ruinas", "maya*"],
}

INTERESES = {
    "surf": ["surf*", "olas", "bodyboard"],
    "senderismo": ["sender*", "caminat*", "hiking", "escalar", "subir", "trekking"],
    "historia": ["histori*", "museo*", "arqueolog*", "ruinas", "maya*", "memoria"],
    "gastronomia": ["comida", "comer", "gastronom*", "pupusa*", "restaurante*", "marisco*", "comidita"],
    "naturaleza": ["naturaleza", "bosque*", "animales", "aves", "ecoturismo", "cascada*", "manglar*"],
    "aventura": ["aventura*", "canopy", "extremo", "adrenalina", "kayak", "bucear", "buceo", "snorkel"],
    "relax": ["relax*", "descans*", "tranquil*", "desconectar*", "paz", "calma"],
    "fotografia": ["foto*", "paisaje*", "vista*", "instagram"],
    "vida_nocturna": ["fiesta*", "bares", "bar", "antro*", "vida nocturna", "bailar", "parrandear"],
    "cultura": ["cultura*", "arte", "artesan*", "tradicion*", "murales", "colonial"],
    "compras": ["compras", "artesanias", "souvenir*", "recuerdos"],
    "cafe": ["cafe", "cafetal*", "finca*", "cafecito"],
}

COMPANIA = {
    "pareja": ["pareja", "novia", "novio", "esposa", "esposo", "mi amor", "mi mujer", "mi marido",
               "luna de miel", "aniversario", "romantico", "romantica"],
    "familia": ["familia", "hijos", "hijas", "ninos", "ninas", "nino", "nina", "papas", "mama", "papa",
                "padres", "abuel*", "sobrinos", "bebe", "bebes", "familiar"],
    "amigos": ["amigos", "amigas", "amigo", "amiga", "grupo", "companeros", "colegas", "excursion"],
    "solo": ["voy solo", "viajo solo", "ir solo", "yo solo", "solo yo", "sola", "voy sola", "viajo sola",
             "ir sola", "por mi cuenta", "mochilero", "mochilera"],
}

NIVELES = {
    "economico": ["barato", "barata", "baratos", "baratas", "economico", "economica", "economicos",
                  "bajo costo", "poco dinero", "poco presupuesto", "mochilero", "mochilera",
                  "sin gastar mucho", "no muy caro", "ahorrar", "low cost"],
    "alto": ["lujo", "lujoso", "lujosa", "premium", "exclusivo", "todo incluido", "cinco estrellas",
             "5 estrellas", "caro", "cara"],
    "medio": ["medio", "normal", "intermedio", "moderado", "regular"],
}

AFIRMACIONES = ["si", "va", "vaya", "dale", "sale", "ok", "okay", "oki", "claro", "obvio", "de una",
                "por supuesto", "acepto", "correcto", "listo", "bueno", "esta bien", "afirmativo",
                "yes", "seguro", "genial"]
NEGACIONES = ["no", "mejor no", "negativo", "para nada", "nunca", "nah", "no acepto", "no gracias"]

# Palabras importantes que el corrector ortográfico sí intenta "arreglar"
PALABRAS_CLAVE = [
    "playa", "playas", "montana", "montanas", "ciudad", "volcan", "lago", "laguna", "cascada", "museo",
    "hotel", "hoteles", "hospedaje", "hostal", "alojamiento", "transporte", "itinerario",
    "presupuesto", "clima", "temperatura", "lluvia", "actividades", "favoritos", "privacidad",
    "recomienda", "recomiendame", "recomendame", "recomendacion", "informacion", "vacaciones",
    "emergencia", "seguridad", "ubicacion", "surf", "senderismo", "gastronomia", "aventura",
    "naturaleza", "historia", "cultura", "fotografia", "sorprendeme", "guardar", "familia", "amigos",
    "pareja", "economico", "barato", "lujo", "personas", "semana", "gracias", "hola", "buenas",
    "adios", "ayuda", "menu", "reiniciar", "borrar", "mapa", "cercanos", "itinerarios", "destino",
    "destinos", "pupusas", "montaña",
]

# Palabras frecuentes que NO se corrigen (para no cambiarles el sentido)
STOPWORDS = {
    "a", "al", "algo", "con", "como", "cual", "de", "del", "donde", "el", "ella", "en", "es", "esta",
    "este", "esto", "hay", "la", "las", "lo", "los", "me", "mi", "mis", "muy", "nos", "o", "para",
    "pero", "por", "que", "quiero", "se", "sin", "su", "sus", "te", "tu", "un", "una", "unos", "y",
    "yo", "voy", "vamos", "puedo", "tengo", "tenemos", "quisiera", "seria", "llevar", "puede",
    "tiene", "hacer", "comer", "dormir", "estar", "saber", "ver", "ir", "dia", "dias", "noche",
    "noches", "cuanto", "cuantos", "cuando", "porque", "favor", "bien", "mejor", "mas", "menos",
}


@dataclass
class Analisis:
    """Resultado de analizar un mensaje."""
    original: str
    normalizado: str
    tokens: list
    intencion: str = "desconocida"
    puntaje: float = 0.0
    puntajes: dict = field(default_factory=dict)
    entidades: dict = field(default_factory=dict)
    numero: Optional[int] = None          # número suelto ("2", "la 2", "dos")
    es_solo_numero: bool = False          # el mensaje es solo un número (opción de menú)
    si_no: Optional[str] = None           # "si" / "no" si el mensaje es una confirmación
    sugerencia_destino: Optional[str] = None  # para "¿Quisiste decir...?"


# ---------------------------------------------------------------------------
# Funciones de preprocesamiento (pasos 1 a 4)
# ---------------------------------------------------------------------------
def normalizar(texto: str) -> str:
    """Paso 1: minúsculas, emojis -> palabras, sin tildes ni signos."""
    texto = (texto or "").lower()
    for emoji, palabra in EMOJIS.items():
        texto = texto.replace(emoji, palabra)
    # Quitar tildes: "montaña" -> "montana", "día" -> "dia"
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    # Dejar solo letras, números, espacios, "$" y el punto decimal
    texto = re.sub(r"[^a-z0-9$.\s]", " ", texto)
    texto = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", texto)
    # "holaaaa" -> "hola", "siiii" -> "si"
    texto = re.sub(r"([a-z])\1{2,}", r"\1", texto)
    return re.sub(r"\s+", " ", texto).strip()


def tokenizar(texto: str) -> list:
    """Paso 3: separar en palabras."""
    return texto.split()


def aplicar_jerga(tokens: list) -> list:
    """Paso 2: traducir jerga salvadoreña y abreviaturas de chat."""
    resultado = []
    for token in tokens:
        resultado.extend(JERGA.get(token, token).split())
    return resultado


def corregir_ortografia(tokens: list, vocabulario: set, protegidas: set = frozenset(),
                        prefijos: tuple = ()) -> list:
    """Paso 4: corregir palabras mal escritas usando similitud (difflib).

    Solo se corrige hacia palabras importantes (vocabulario) y nunca se tocan
    palabras que ya son correctas (protegidas), para no cambiarles el sentido.
    """
    corregidos = []
    for token in tokens:
        if (len(token) < 4 or token.isdigit() or token in vocabulario or token in protegidas
                or (prefijos and token.startswith(prefijos))):
            corregidos.append(token)
            continue
        parecidas = get_close_matches(token, vocabulario, n=1, cutoff=0.8)
        corregidos.append(parecidas[0] if parecidas else token)
    return corregidos


def contar_coincidencias(texto: str, tokens: list, patrones: list, peso_fijo: bool = False) -> float:
    """Suma puntos por cada patrón encontrado en el texto."""
    texto_con_espacios = f" {texto} "
    puntos = 0.0
    for patron in patrones:
        if patron.endswith("*"):                      # raíz de palabra
            raiz = patron[:-1]
            if any(t.startswith(raiz) for t in tokens):
                puntos += 1
        elif " " in patron:                           # frase
            if f" {patron} " in texto_con_espacios:
                puntos += 1 if peso_fijo else len(patron.split())
        elif patron in tokens:                        # palabra exacta
            puntos += 1
    return puntos


def mejor_categoria(texto: str, tokens: list, diccionario: dict) -> Optional[str]:
    """Devuelve la categoría con más coincidencias (o None si hay empate o ninguna)."""
    puntajes = {cat: contar_coincidencias(texto, tokens, pats) for cat, pats in diccionario.items()}
    maximo = max(puntajes.values()) if puntajes else 0
    if maximo == 0:
        return None
    ganadores = [cat for cat, p in puntajes.items() if p == maximo]
    return ganadores[0] if len(ganadores) == 1 else None


# ---------------------------------------------------------------------------
# Clase principal del PLN
# ---------------------------------------------------------------------------
class AnalizadorNLP:
    """Entiende los mensajes del usuario: intención + entidades."""

    def __init__(self, destinos: list):
        # alias -> id del destino (ej. "juayua" -> "ruta_flores")
        self.alias_a_id = {}
        for destino in destinos:
            for alias in destino["alias"]:
                self.alias_a_id[normalizar(alias)] = destino["id"]

        # Vocabulario hacia el que se corrigen las palabras mal escritas
        self.vocabulario = {normalizar(p) for p in PALABRAS_CLAVE}
        for alias in self.alias_a_id:
            self.vocabulario.update(p for p in alias.split() if len(p) >= 4)

        # Palabras ya correctas que el corrector nunca debe cambiar
        # (ej. "costo" no debe volverse "costa", ni "plan" volverse "planes")
        self.protegidas = set(STOPWORDS) | set(NUMEROS_TEXTO) | set(AFIRMACIONES) | set(NEGACIONES)
        prefijos = []
        for diccionario in (INTENCIONES, TIPOS, INTERESES, COMPANIA, NIVELES):
            for patrones in diccionario.values():
                for patron in patrones:
                    if patron.endswith("*"):
                        prefijos.append(patron[:-1])
                    else:
                        self.protegidas.update(patron.split())
        for valor in list(JERGA.values()) + LUGARES_EXTRANJEROS:
            self.protegidas.update(valor.split())
        self.prefijos = tuple(prefijos)

    # ------------------------------------------------------------------
    def analizar(self, texto: str) -> Analisis:
        normalizado = normalizar(texto)
        tokens = aplicar_jerga(tokenizar(normalizado))
        tokens = corregir_ortografia(tokens, self.vocabulario, self.protegidas, self.prefijos)
        limpio = " ".join(tokens)

        analisis = Analisis(original=texto, normalizado=limpio, tokens=tokens)
        self._detectar_intencion(analisis)
        self._extraer_entidades(analisis)
        return analisis

    # ------------------------------------------------------------------
    def _detectar_intencion(self, a: Analisis) -> None:
        """Paso 5: puntuar cada intención y escoger la mayor."""
        for intencion, patrones in INTENCIONES.items():
            puntos = contar_coincidencias(a.normalizado, a.tokens, patrones,
                                          peso_fijo=intencion in CORTESIA)
            if puntos > 0:
                a.puntajes[intencion] = puntos
        # Regla: "salir", "terminar" o "fin" escritos solos son comandos para despedirse
        if a.normalizado in ("salir", "terminar", "fin", "exit"):
            a.puntajes["despedida"] = a.puntajes.get("despedida", 0) + 3
        # Regla: "guardar" + plan/itinerario/presupuesto/viaje = guardar un plan (no un favorito)
        if (any(t.startswith("guard") for t in a.tokens)
                and {"plan", "itinerario", "presupuesto", "viaje"} & set(a.tokens)):
            a.puntajes["guardar_plan"] = a.puntajes.get("guardar_plan", 0) + 3
        # Regla: mencionar un país o lugar extranjero pesa más que cualquier otra intención
        extranjeros = contar_coincidencias(a.normalizado, a.tokens, LUGARES_EXTRANJEROS)
        if extranjeros:
            a.puntajes["fuera_alcance"] = a.puntajes.get("fuera_alcance", 0) + 3 * extranjeros
        if not a.puntajes:
            return
        maximo = max(a.puntajes.values())
        empatadas = [i for i in PRIORIDAD if a.puntajes.get(i) == maximo]
        a.intencion = empatadas[0]
        a.puntaje = maximo

    # ------------------------------------------------------------------
    def _extraer_entidades(self, a: Analisis) -> None:
        """Paso 6: sacar los datos concretos del mensaje."""
        texto, tokens, e = a.normalizado, a.tokens, a.entidades

        destino, sugerencia = self._buscar_destino(texto)
        if destino:
            e["destino"] = destino
        a.sugerencia_destino = sugerencia

        tipo = mejor_categoria(texto, tokens, TIPOS)
        if tipo:
            e["tipo"] = tipo

        intereses = [i for i, pats in INTERESES.items() if contar_coincidencias(texto, tokens, pats)]
        if intereses:
            e["intereses"] = intereses

        compania = mejor_categoria(texto, tokens, COMPANIA)
        if compania:
            e["compania"] = compania

        nivel = self._buscar_nivel(texto, tokens)
        if nivel:
            e["nivel"] = nivel

        for nombre, valor in (("dias", self._buscar_dias(texto)),
                              ("personas", self._buscar_personas(texto)),
                              ("presupuesto", self._buscar_presupuesto(texto))):
            if valor is not None:
                e[nombre] = valor

        a.numero, a.es_solo_numero = self._buscar_numero(texto, tokens)
        a.si_no = self._buscar_si_no(texto, tokens)

    # ------------------------------------------------------------------
    def _buscar_destino(self, texto: str):
        """Busca un destino por sus alias; si no, propone uno parecido."""
        relleno = f" {texto} "
        encontrados = []  # (es_origen, posicion, -largo_alias, id)
        for alias, destino_id in self.alias_a_id.items():
            pos = relleno.find(f" {alias} ")
            if pos >= 0:
                antes = relleno[:pos].split()
                despues = relleno[pos + len(alias) + 1:]
                # Es el lugar de ORIGEN si dice "desde X" o "de X a Y"
                es_origen = bool(antes) and (antes[-1] == "desde" or
                                             (antes[-1] == "de" and despues.startswith(" a ")))
                encontrados.append((es_origen, pos, -len(alias), destino_id))
        if encontrados:
            # Gana: el que no es origen, el que aparece primero y el alias más largo
            encontrados.sort()
            return encontrados[0][3], None

        # Sin coincidencia exacta: buscar el alias más parecido para sugerirlo
        palabras = texto.split()
        mejor_parecido, sugerido = 0.0, None
        for alias, destino_id in self.alias_a_id.items():
            if len(alias) < 5:
                continue
            n = len(alias.split())
            for i in range(len(palabras) - n + 1):
                fragmento = " ".join(palabras[i:i + n])
                parecido = SequenceMatcher(None, fragmento, alias).ratio()
                if parecido > mejor_parecido:
                    mejor_parecido, sugerido = parecido, destino_id
        return None, (sugerido if mejor_parecido >= 0.72 else None)

    @staticmethod
    def _buscar_nivel(texto: str, tokens: list) -> Optional[str]:
        for nivel in ("economico", "alto", "medio"):   # "no muy caro" se revisa antes que "caro"
            if contar_coincidencias(texto, tokens, NIVELES[nivel]):
                return nivel
        return None

    @staticmethod
    def _a_numero(palabra: str) -> Optional[int]:
        if palabra.isdigit():
            return int(palabra)
        return NUMEROS_TEXTO.get(palabra)

    def _buscar_dias(self, texto: str) -> Optional[int]:
        if "fin de semana" in texto:
            return 2
        if re.search(r"\b(una|1) semana\b", texto):
            return 7
        if re.search(r"\b(todo el dia|medio dia|un solo dia)\b", texto):
            return 1
        m = re.search(r"\b(\d+|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s*"
                      r"(dia|dias|noche|noches)\b", texto)
        if m:
            numero = self._a_numero(m.group(1))
            if numero:
                return numero + 1 if m.group(2).startswith("noche") else numero
        return None

    def _buscar_personas(self, texto: str) -> Optional[int]:
        patrones = [
            r"\b(\d+|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s*"
            r"(personas|persona|adultos|amigos|amigas|pax|gente|viajeros)\b",
            r"\bsomos\s+(\d+|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\b",
            r"\bfamilia de\s+(\d+|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\b",
            r"\bpara\s+(\d+|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s*(personas|persona)?\s*$",
        ]
        for patron in patrones:
            m = re.search(patron, texto)
            if m:
                return self._a_numero(m.group(1))
        return None

    @staticmethod
    def _buscar_presupuesto(texto: str) -> Optional[float]:
        m = re.search(r"\$\s*(\d+(?:\.\d+)?)", texto) or \
            re.search(r"(\d+(?:\.\d+)?)\s*(dolares|dolar|usd|\$)", texto)
        return float(m.group(1)) if m else None

    def _buscar_numero(self, texto: str, tokens: list):
        """Detecta si el mensaje es una opción: "2", "la 2", "opcion 3", "dos"."""
        m = re.fullmatch(r"(?:la|el|opcion|numero|num)?\s*(\d{1,2})", texto)
        if m:
            return int(m.group(1)), True
        if len(tokens) == 1 and tokens[0] in NUMEROS_TEXTO:
            return NUMEROS_TEXTO[tokens[0]], True
        numeros = re.findall(r"\b\d+\b", texto)
        return (int(numeros[0]), False) if numeros else (None, False)

    @staticmethod
    def _buscar_si_no(texto: str, tokens: list) -> Optional[str]:
        """Confirmaciones cortas: "si", "va pues", "simon", "nel", "no gracias"."""
        if not tokens or len(tokens) > 5:
            return None
        relleno = f" {texto} "
        if any(f" {n} " in relleno for n in NEGACIONES if " " in n) or tokens[0] in NEGACIONES:
            return "no"
        if any(f" {s} " in relleno for s in AFIRMACIONES if " " in s) or tokens[0] in AFIRMACIONES:
            return "si"
        return None


def formato_guia(a: Analisis) -> str:
    """Muestra el análisis con la notación de la guía de clase: #intención y @entidades."""
    intencion = "Ninguna intención detectada" if a.intencion == "desconocida" else f"#{a.intencion}"
    if a.entidades:
        entidades = ", ".join(f"@{clave}: {valor}" for clave, valor in a.entidades.items())
    else:
        entidades = "Sin entidades"
    return f"{intencion} | {entidades}"
