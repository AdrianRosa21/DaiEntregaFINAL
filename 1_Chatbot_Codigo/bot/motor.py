"""
motor.py - Gestor del diálogo: el "cerebro" de la conversación.

Recibe el mensaje, le pide al PLN que lo entienda (intención + entidades) y
decide qué responder según el ESTADO de la conversación:

  * estado:     dónde está el usuario (inicio, menú, lista de destinos, ficha de un destino)
  * esperando:  qué dato le pidió el bot (tipo, destino, días, personas, nivel, sí/no...)
  * perfil:     lo que el bot va aprendiendo en la charla (compañía, gasto, días...)

Esto permite conversaciones de varios pasos ("llenado de espacios" o slot filling):
si falta un dato, el bot lo pregunta y luego continúa con lo que se estaba haciendo.

La sesión se guarda en SQLite (tabla "sesiones"), así el bot recuerda el contexto
aunque se reinicie el servidor. Se borra sola a los 30 minutos sin mensajes.
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import asdict, dataclass, field, fields
from typing import Optional

import config
from bot import mensajes as M
from bot.nlp import AnalizadorNLP, Analisis
from bot.planificador import NOMBRE_NIVEL, estimar_presupuesto, generar_itinerario, texto_presupuesto
from bot.base_datos import BaseDatos
from bot.recomendador import EMOJI_TIPO, NOMBRE_TIPO, cercanos, recomendar
from bot.servicios import enlace_mapa, obtener_clima, texto_clima

EMOJI_NUM = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
TIPOS_POR_NUMERO = {1: "playa", 2: "montana", 3: "ciudad"}
NIVELES_POR_NUMERO = {1: "economico", 2: "medio", 3: "alto"}

# Menú principal y menú de la ficha: número -> acción
OPCIONES_MENU = {1: "recomendar", 2: "info", 3: "itinerario", 4: "presupuesto", 5: "clima",
                 6: "ver_favoritos", 7: "sorpresa", 8: "seguridad", 9: "privacidad"}
OPCIONES_FICHA = {1: "hospedaje", 2: "transporte", 3: "actividades", 4: "clima",
                  5: "itinerario", 6: "presupuesto", 7: "guardar", 8: "mapa"}

# Intenciones que necesitan saber de qué destino se habla
ACCION_DE_INTENCION = {"info_destino": "info", "hospedaje": "hospedaje", "transporte": "transporte",
                       "actividades": "actividades", "clima": "clima", "mapa": "mapa",
                       "itinerario": "itinerario", "presupuesto": "presupuesto",
                       "guardar_favorito": "guardar"}


# Preguntas que se contestan con sí/no: ahí "no, gracias" es una respuesta, no una despedida
PREGUNTAS_SI_NO = ("confirmar_sugerencia", "consentimiento", "borrado")


@dataclass
class Sesion:
    """Memoria de corto plazo de UNA conversación (se guarda en SQLite, sin el nombre)."""
    nombre: str = ""                         # solo en memoria: NO se guarda en la base
    estado: str = "inicio"                  # inicio | menu | lista | ficha
    esperando: Optional[str] = None          # dato que el bot pidió
    accion_pendiente: Optional[str] = None   # acción a terminar cuando llegue el dato
    destino_actual: Optional[str] = None     # destino del que se está hablando (contexto)
    sugerencia: Optional[str] = None         # destino sugerido en "¿Quisiste decir...?"
    favorito_pendiente: Optional[str] = None
    plan_pendiente: Optional[dict] = None    # plan esperando permiso para guardarse
    ultimo_plan: Optional[dict] = None       # último itinerario o presupuesto mostrado
    opciones: list = field(default_factory=list)  # destinos de la última lista mostrada
    vistos: list = field(default_factory=list)    # destinos ya recomendados (para "ver más")
    perfil: dict = field(default_factory=dict)    # tipo, intereses, compañía, nivel, días...
    fallos: int = 0                          # mensajes seguidos sin entender
    aviso_mostrado: bool = False
    mensajes: int = 0
    ultima_actividad: float = field(default_factory=time.time)


class MotorConversacional:
    """Coordina el PLN, el recomendador, los servicios y la privacidad."""

    def __init__(self, ruta_destinos=None, bd=None, servicio_clima=None):
        with open(ruta_destinos or config.ARCHIVO_DESTINOS, encoding="utf-8") as archivo:
            self.destinos = json.load(archivo)["destinos"]
        self.por_id = {d["id"]: d for d in self.destinos}
        self.nlp = AnalizadorNLP(self.destinos)
        self.bd = bd or BaseDatos()                    # persistencia SQLite
        self.obtener_clima = servicio_clima or obtener_clima

        # Intención -> función que la atiende
        self.manejadores = {
            "saludo": self._saludo,
            "agradecimiento": self._agradecimiento,
            "recomendar": self._recomendar,
            "mas_opciones": self._mas_opciones,
            "epoca": self._epoca,
            "ver_favoritos": self._ver_favoritos,
            "guardar_plan": self._guardar_plan,
            "privacidad": self._privacidad,
            "sorpresa": self._sorpresa,
            "seguridad": self._seguridad,
            "cercanos": lambda s, a, uid: M.PEDIR_UBICACION,
            "fuera_alcance": self._fuera_de_alcance,
        }

    # =====================================================================
    # Punto de entrada
    # =====================================================================
    def responder(self, usuario_id: str, texto: str, nombre: str = "",
                  ubicacion: Optional[tuple] = None, tiene_multimedia: bool = False) -> str:
        """Recibe un mensaje y devuelve la respuesta del bot."""
        s = self._obtener_sesion(usuario_id)
        if nombre:
            s.nombre = nombre.strip().split()[0][:20]   # solo el primer nombre, en memoria
        primera_vez = s.mensajes == 0
        s.mensajes += 1

        if ubicacion:                                   # el usuario compartió su ubicación 📍
            self.bd.registrar_interaccion("ubicacion", True)
            respuesta = self._cercanos(s, *ubicacion)
        elif not (texto or "").strip():                 # foto, audio, sticker...
            self.bd.registrar_interaccion("multimedia", True)
            respuesta = M.MULTIMEDIA if tiene_multimedia else M.AYUDA
        else:
            analisis = self.nlp.analizar(texto)
            respuesta, entendido = self._procesar(s, analisis, usuario_id)
            etiqueta = analisis.intencion
            if etiqueta == "desconocida" and entendido:      # "1", "sí", "3 días"... según el contexto
                etiqueta = "respuesta_por_contexto"
            self.bd.registrar_interaccion(etiqueta, entendido)
            if primera_vez and analisis.intencion != "saludo":
                saludo = f"¡Hola, {s.nombre}!" if s.nombre else "¡Hola!"
                respuesta = f"{saludo} 👋 Soy *Guanaco Viajero* 🇸🇻\n\n{respuesta}"

        self._guardar_sesion(usuario_id, s)             # persistencia del contexto (SQLite)
        return respuesta

    def analizar(self, texto: str) -> Analisis:
        """Permite ver cómo el PLN entiende un texto (útil para pruebas y la defensa)."""
        return self.nlp.analizar(texto)

    # =====================================================================
    # Lógica principal
    # =====================================================================
    def _procesar(self, s: Sesion, a: Analisis, uid: str):
        """Devuelve (respuesta, entendido)."""
        i, e = a.intencion, a.entidades
        self._actualizar_perfil(s, e)

        # 0) Calificación al despedirse: "4" o "⭐⭐⭐⭐"
        if s.esperando == "calificacion":
            valor = a.original.count("⭐") or (a.numero if a.es_solo_numero else None)
            s.esperando = None
            if valor and 1 <= valor <= 5:
                self.bd.calificar(valor)
                return M.gracias_calificacion(valor), True

        # 1) Comandos globales: funcionan en cualquier momento
        if i == "reiniciar":
            self._limpiar(s, todo=True)
            return "🔄 Listo, empezamos de nuevo.\n\n" + M.bienvenida(s.nombre), True
        if i == "menu" or (a.es_solo_numero and a.numero == 0):
            self._limpiar(s)
            return M.MENU_PRINCIPAL, True
        if i == "borrar_datos":
            self._limpiar(s)
            s.esperando = "borrado"
            return M.CONFIRMAR_BORRADO, True
        if i == "despedida" and not (s.esperando in PREGUNTAS_SI_NO and a.si_no):
            self._limpiar(s, todo=True)
            s.esperando = "calificacion"
            return M.despedida(s.nombre), True
        if i == "insulto":
            return M.INSULTO, True
        if i == "ayuda":
            if s.esperando:
                return "💡 " + self._repreguntar(s) + "\n_(Escribí *menú* para salir de esta pregunta.)_", True
            return M.AYUDA, True

        # 2) El bot estaba esperando un dato: intentamos completarlo
        if s.esperando:
            respuesta = self._resolver_espera(s, a, uid)
            if respuesta is not None:
                s.fallos = 0
                return respuesta, True
            cambio_de_tema = i != "desconocida" or "destino" in e or "tipo" in e
            if not cambio_de_tema:
                s.fallos += 1
                extra = "\n_(Si querés salir de esta pregunta, escribí *menú*.)_" if s.fallos >= 2 else ""
                return self._repreguntar(s, a) + extra, False
            self._limpiar_espera(s)                    # el usuario cambió de tema

        # 3) Solo un número: es una opción del menú que está a la vista
        if a.es_solo_numero:
            return self._opcion_numerica(s, a.numero, uid)

        # 4) Intención reconocida
        if i in ACCION_DE_INTENCION:
            s.fallos = 0
            return self._ejecutar_accion(s, ACCION_DE_INTENCION[i], uid, a), True
        if i in self.manejadores:
            s.fallos = 0
            return self.manejadores[i](s, a, uid), True

        # 5) Sin intención clara, pero con datos útiles ("Suchitoto", "playa")
        if "destino" in e:
            s.fallos = 0
            return self._ficha(s, e["destino"]), True
        if any(k in e for k in ("tipo", "intereses", "compania")):
            s.fallos = 0
            return self._recomendar(s, a, uid), True
        if a.si_no == "si":
            return "¡Va! 😄 ¿En qué te ayudo? Escribí *menú* para ver las opciones.", True
        if a.si_no == "no":
            return "Está bien 👍. Si necesitás algo, aquí estoy. Escribí *menú* cuando querás.", True

        # 6) No se entendió
        return self._no_entendido(s, a), False

    # ---------------------------------------------------------------------
    def _resolver_espera(self, s: Sesion, a: Analisis, uid: str) -> Optional[str]:
        """Intenta usar el mensaje como respuesta a lo que el bot preguntó."""
        e, esperando = a.entidades, s.esperando

        if esperando == "tipo":
            tipo = e.get("tipo") or (TIPOS_POR_NUMERO.get(a.numero) if a.es_solo_numero else None)
            if tipo:
                s.esperando = None
                s.perfil["tipo"] = tipo
                return self._lista_recomendaciones(s, nueva=True)

        elif esperando == "destino":
            if "destino" in e:
                return self._continuar_con_destino(s, e["destino"], uid)
            if a.es_solo_numero and a.numero == 1:
                s.esperando, s.accion_pendiente = "tipo", None
                return M.PREGUNTA_TIPO
            if a.sugerencia_destino:
                s.esperando, s.sugerencia = "confirmar_sugerencia", a.sugerencia_destino
                return f"🤔 ¿Quisiste decir *{self.por_id[a.sugerencia_destino]['nombre']}*? Respondé *sí* o *no*."

        elif esperando == "confirmar_sugerencia":
            if "destino" in e:
                return self._continuar_con_destino(s, e["destino"], uid)
            if a.si_no == "si":
                return self._continuar_con_destino(s, s.sugerencia, uid)
            if a.si_no == "no":
                s.esperando, s.sugerencia = "destino", None
                return "Va 👍. Escribime el nombre del lugar que buscás."

        elif esperando == "dias":
            dias = e.get("dias") or (a.numero if a.numero and 1 <= a.numero <= 30 else None)
            if dias:
                s.perfil["dias"] = dias
                s.esperando = None
                return self._ejecutar_accion(s, s.accion_pendiente or "itinerario", uid)

        elif esperando == "personas":
            personas = e.get("personas") or (a.numero if a.numero and 1 <= a.numero <= 50 else None)
            personas = personas or {"solo": 1, "pareja": 2}.get(e.get("compania"))
            if personas:
                s.perfil["personas"] = personas
                s.esperando = None
                return self._ejecutar_accion(s, "presupuesto", uid)

        elif esperando == "nivel":
            nivel = e.get("nivel") or (NIVELES_POR_NUMERO.get(a.numero) if a.es_solo_numero else None)
            if nivel:
                s.perfil["nivel"] = nivel
                s.esperando = None
                return self._ejecutar_accion(s, "presupuesto", uid)

        elif esperando == "consentimiento":
            if a.si_no == "si":
                self.bd.dar_consentimiento(uid)
                s.esperando = None
                if s.plan_pendiente:
                    plan, s.plan_pendiente = s.plan_pendiente, None
                    self.bd.guardar_plan(uid, plan)
                    if s.ultimo_plan:
                        s.ultimo_plan["guardado"] = True
                    return ("✅ ¡Gracias por tu permiso! Guardé tu plan para "
                            f"*{self.por_id[plan['destino']]['nombre']}* 💾\nEscribí *mis planes* para verlo.")
                destino_id, s.favorito_pendiente = s.favorito_pendiente, None
                self.bd.agregar_favorito(uid, destino_id)
                return (f"✅ ¡Gracias por tu permiso! Guardé *{self.por_id[destino_id]['nombre']}* "
                        "en tus favoritos ⭐\nEscribí *mis favoritos* para verlos.")
            if a.si_no == "no":
                s.esperando, s.favorito_pendiente, s.plan_pendiente = None, None, None
                return "👍 Entendido, no guardé nada. Podés seguir usando todas las demás funciones."

        elif esperando == "borrado":
            if a.si_no == "si":
                s.esperando = None
                if self.bd.borrar_usuario(uid):
                    return ("🗑️ Listo, borré todos tus datos de mi base (favoritos, planes y permiso). "
                            "¡Tu privacidad es primero!")
                return "🗑️ No tenía ningún dato guardado de vos 🙂."
            if a.si_no == "no":
                s.esperando = None
                return "👍 Perfecto, no borré nada."
        return None

    def _repreguntar(self, s: Sesion, a: Analisis = None) -> str:
        """Vuelve a pedir el dato que falta, de forma amable."""
        if s.esperando == "tipo":
            return "Decime *playa*, *montaña* o *ciudad* (o el número 1, 2 o 3) 🙂"
        if s.esperando == "destino":
            return ("No reconocí ese lugar 🤔. Escribí el nombre de un destino de El Salvador, "
                    "por ejemplo _Suchitoto_, _El Tunco_ o _Ruta de las Flores_.")
        if s.esperando == "dias":
            return M.PREGUNTA_DIAS
        if s.esperando == "personas":
            return M.PREGUNTA_PERSONAS
        if s.esperando == "nivel":
            return M.PREGUNTA_NIVEL
        return "Respondé *sí* o *no*, porfa 🙂"

    # =====================================================================
    # Acciones sobre un destino
    # =====================================================================
    def _ejecutar_accion(self, s: Sesion, accion: str, uid: str, a: Analisis = None) -> str:
        e = a.entidades if a else {}
        if e.get("destino"):
            s.destino_actual = e["destino"]
        if not s.destino_actual:
            return self._preguntar_destino(s, accion, a.sugerencia_destino if a else None)

        if accion == "info":
            return self._ficha(s, s.destino_actual)
        if accion == "itinerario":
            return self._itinerario(s)
        if accion == "presupuesto":
            return self._presupuesto(s)
        if accion == "guardar":
            return self._guardar(s, uid)
        s.estado, s.esperando, s.accion_pendiente = "ficha", None, None
        return self._texto_accion(s, accion)

    def _preguntar_destino(self, s: Sesion, accion: str, sugerencia: Optional[str] = None) -> str:
        s.accion_pendiente = accion
        if sugerencia:
            s.esperando, s.sugerencia = "confirmar_sugerencia", sugerencia
            return f"🤔 ¿Quisiste decir *{self.por_id[sugerencia]['nombre']}*? Respondé *sí* o *no*."
        s.esperando = "destino"
        return M.PREGUNTA_DESTINO

    def _continuar_con_destino(self, s: Sesion, destino_id: str, uid: str) -> str:
        s.destino_actual = destino_id
        s.esperando, s.sugerencia = None, None
        accion, s.accion_pendiente = s.accion_pendiente or "info", None
        return self._ejecutar_accion(s, accion, uid)

    def _ficha(self, s: Sesion, destino_id: str) -> str:
        d = self.por_id[destino_id]
        s.destino_actual, s.estado = destino_id, "ficha"
        s.esperando, s.accion_pendiente = None, None
        return "\n".join([
            f"📍 *{d['nombre']}* ({d['departamento']})",
            d["descripcion"], "",
            f"🚗 Desde San Salvador: {d['tiempo']}",
            f"💲 Nivel de costo: {NOMBRE_NIVEL[d['nivel_costo']]}",
            f"🗓️ Mejor época: {d['mejor_epoca']}", "",
            M.FICHA_OPCIONES,
        ])

    def _texto_accion(self, s: Sesion, accion: str) -> str:
        d = self.por_id[s.destino_actual]
        if accion == "hospedaje":
            texto = (f"🏨 *Hospedaje en {d['nombre']}*\n{d['hospedaje']}\n\n"
                     "💲 Rangos de referencia por noche:\n"
                     "• Económico (hostal/camping): $10–25 por persona\n"
                     "• Medio (hotel/cabaña): $30–70 por habitación\n"
                     "• Alto (boutique/resort): $80 o más" + self._aviso(s))
        elif accion == "transporte":
            texto = (f"🚌 *Cómo llegar a {d['nombre']}*\n"
                     f"🚗 *En carro:* {d['como_llegar']['carro']}\n"
                     f"🚌 *En bus:* {d['como_llegar']['bus']}" + self._aviso(s))
        elif accion == "actividades":
            lista = "\n".join(f"• {act}" for act in d["actividades"])
            texto = f"🎯 *Qué hacer en {d['nombre']}*\n{lista}\n\n💡 {d['consejo']}"
        elif accion == "clima":
            datos = self.obtener_clima(d)
            if datos:
                texto = texto_clima(d, datos)
            else:
                texto = ("😓 No pude consultar el clima en este momento (el servicio no respondió).\n"
                         f"Como referencia, la mejor época para ir es: {d['mejor_epoca']}\n"
                         "Probá de nuevo en un ratito.")
        elif accion == "mapa":
            texto = f"📍 *{d['nombre']}* en Google Maps:\n{enlace_mapa(d)}"
        else:
            return self._ficha(s, d["id"])
        return f"{texto}\n\n{M.PIE_FICHA.format(nombre=d['nombre'])}"

    def _itinerario(self, s: Sesion) -> str:
        d = self.por_id[s.destino_actual]
        dias = s.perfil.get("dias")
        if not dias:
            s.esperando, s.accion_pendiente = "dias", "itinerario"
            return f"🗓️ ¡Va! Te armo el itinerario para *{d['nombre']}*.\n{M.PREGUNTA_DIAS}"
        s.estado, s.esperando, s.accion_pendiente = "ficha", None, None
        s.ultimo_plan = {"destino": d["id"], "tipo": "itinerario", "dias": min(dias, 3)}
        nota = ("\n_(Te armé los primeros 3 días; para más tiempo combiná con otro destino 😉)_"
                if dias > 3 else "")
        return (generar_itinerario(d, dias, self.por_id) + nota + "\n\n" + M.GUARDAR_PLAN + "\n"
                + M.PIE_FICHA.format(nombre=d["nombre"]))

    def _presupuesto(self, s: Sesion) -> str:
        d = self.por_id[s.destino_actual]
        p = s.perfil
        personas = p.get("personas") or {"solo": 1, "pareja": 2}.get(p.get("compania"))
        intro = f"💵 Calculemos el presupuesto para *{d['nombre']}*.\n"
        s.accion_pendiente = "presupuesto"
        if not p.get("dias"):
            s.esperando = "dias"
            return intro + M.PREGUNTA_DIAS
        if not personas:
            s.esperando = "personas"
            return intro + M.PREGUNTA_PERSONAS
        if not p.get("nivel"):
            s.esperando = "nivel"
            return intro + M.PREGUNTA_NIVEL
        s.estado, s.esperando, s.accion_pendiente = "ficha", None, None
        calculo = estimar_presupuesto(d, p["dias"], personas, p["nivel"])
        s.ultimo_plan = {"destino": d["id"], "tipo": "presupuesto", "dias": calculo["dias"],
                         "personas": calculo["personas"], "nivel": calculo["nivel"], "total": calculo["total"]}
        return (texto_presupuesto(d, calculo, p.get("presupuesto")) + "\n\n" + M.GUARDAR_PLAN + "\n"
                + M.PIE_FICHA.format(nombre=d["nombre"]))

    def _guardar(self, s: Sesion, uid: str) -> str:
        d = self.por_id[s.destino_actual]
        if not self.bd.tiene_consentimiento(uid):
            s.esperando, s.favorito_pendiente = "consentimiento", d["id"]
            return M.PEDIR_CONSENTIMIENTO
        s.estado = "ficha"
        if self.bd.agregar_favorito(uid, d["id"]):
            texto = f"⭐ ¡Listo! Guardé *{d['nombre']}* en tus favoritos."
        else:
            texto = f"⭐ *{d['nombre']}* ya estaba en tus favoritos."
        return f"{texto}\nEscribí *mis favoritos* para verlos.\n\n{M.PIE_FICHA.format(nombre=d['nombre'])}"

    # =====================================================================
    # Recomendaciones y listas
    # =====================================================================
    def _recomendar(self, s: Sesion, a: Analisis, uid: str) -> str:
        e = a.entidades
        if "destino" in e:                      # "quiero ir a Suchitoto"
            return self._ficha(s, e["destino"])
        if "tipo" not in e:
            s.esperando = "tipo"
            return M.PREGUNTA_TIPO
        s.perfil["tipo"] = e["tipo"]
        return self._lista_recomendaciones(s, nueva=True)

    def _mas_opciones(self, s: Sesion, a: Analisis, uid: str) -> str:
        e = a.entidades
        if "tipo" in e:
            s.perfil["tipo"] = e["tipo"]
        hay_filtro_nuevo = any(k in e for k in ("tipo", "nivel", "compania", "intereses"))
        if s.perfil.get("tipo") and (hay_filtro_nuevo or s.vistos):
            return self._lista_recomendaciones(s, nueva=hay_filtro_nuevo)
        return self._recomendar(s, a, uid)

    def _lista_recomendaciones(self, s: Sesion, nueva: bool = True) -> str:
        if nueva:
            s.vistos = []
        resultados = recomendar(self.destinos, s.perfil, excluir=s.vistos, cantidad=3)
        if not resultados:
            return ("Ya te mostré todas las opciones de ese tipo 🙌. Escribí el número de alguna, "
                    "probá otro tipo de lugar o escribí *menú*.")
        s.vistos.extend(d["id"] for d, _, _ in resultados)
        s.opciones = [d["id"] for d, _, _ in resultados]
        s.estado = "lista"

        tipo = s.perfil.get("tipo")
        lineas = [f"{EMOJI_TIPO[tipo]} ¡Qué chivo! Estos destinos de *{NOMBRE_TIPO[tipo]}* te pueden gustar:", ""]
        for n, (d, _puntos, razones) in enumerate(resultados, start=1):
            lineas.append(f"{EMOJI_NUM[n]} *{d['nombre']}* ({d['departamento']}) — {d['tiempo']}")
            lineas.append(f"      {d['resumen']}")
            extra = [r for r in razones if not r.startswith(EMOJI_TIPO[tipo])]
            if extra:
                lineas.append("      ✅ " + " · ".join(extra[:3]))
        lineas += ["", "Escribí el *número* para ver detalles, o *más* para ver otras opciones."]
        return "\n".join(lineas)

    def _cercanos(self, s: Sesion, lat: float, lon: float) -> str:
        lista = cercanos(self.destinos, lat, lon, cantidad=3)
        self._limpiar_espera(s)
        s.opciones, s.estado = [d["id"] for d, _ in lista], "lista"
        lineas = ["📍 ¡Gracias! Estos destinos te quedan más cerca (en línea recta):", ""]
        for n, (d, km) in enumerate(lista, start=1):
            lineas.append(f"{EMOJI_NUM[n]} *{d['nombre']}* — a {km:.0f} km")
        lineas += ["", "Escribí el *número* para ver detalles.", "🔒 No guardé tu ubicación."]
        return "\n".join(lineas)

    def _opcion_numerica(self, s: Sesion, n: int, uid: str):
        """Interpreta un número según lo que el usuario tiene a la vista."""
        if s.estado == "lista" and s.opciones:
            if 1 <= n <= len(s.opciones):
                return self._ficha(s, s.opciones[n - 1]), True
            return f"Elegí un número del 1 al {len(s.opciones)} 🙂 (o escribí *menú*).", False
        if s.estado == "ficha" and s.destino_actual:
            if n in OPCIONES_FICHA:
                return self._ejecutar_accion(s, OPCIONES_FICHA[n], uid), True
            return "Elegí una opción del 1 al 8, o *0* para el menú principal 🙂", False
        if n in OPCIONES_MENU:
            return self._opcion_menu(s, OPCIONES_MENU[n], uid), True
        return "Esa opción no existe 🤔. Elegí un número del 1 al 9 o escribí *menú*.", False

    def _opcion_menu(self, s: Sesion, opcion: str, uid: str) -> str:
        if opcion == "recomendar":
            s.esperando = "tipo"
            return M.PREGUNTA_TIPO
        if opcion in ("info", "itinerario", "presupuesto", "clima"):
            s.destino_actual = None              # desde el menú se pregunta el destino
            return self._preguntar_destino(s, opcion)
        return self.manejadores[opcion](s, None, uid)

    # =====================================================================
    # Otras intenciones
    # =====================================================================
    def _saludo(self, s: Sesion, a: Analisis, uid: str) -> str:
        hola = f"¡Hola, {s.nombre}! 👋\n\n" if s.nombre else "¡Hola! 👋\n\n"
        if "destino" in a.entidades:
            return hola + self._ficha(s, a.entidades["destino"])
        if "tipo" in a.entidades:
            return hola + self._recomendar(s, a, uid)
        self._limpiar(s)
        return M.bienvenida(s.nombre)

    def _agradecimiento(self, s: Sesion, a: Analisis, uid: str) -> str:
        return "¡Con mucho gusto! 😊 ¿Te ayudo con algo más? Escribí *menú* para ver opciones o *salir* para terminar."

    def _epoca(self, s: Sesion, a: Analisis, uid: str) -> str:
        destino_id = a.entidades.get("destino") or s.destino_actual
        general = ("☀️ En El Salvador la época seca va de noviembre a abril (ideal para playa y volcanes) "
                   "y la lluviosa de mayo a octubre (todo más verde y cascadas con más agua 🌿).")
        if not destino_id:
            return general + "\n\nEscribime un destino y te digo su mejor época 😉"
        d = self.por_id[destino_id]
        s.destino_actual, s.estado = destino_id, "ficha"
        return (f"🗓️ *Mejor época para {d['nombre']}:*\n{d['mejor_epoca']}\n\n{general}\n\n"
                + M.PIE_FICHA.format(nombre=d["nombre"]))

    def _ver_favoritos(self, s: Sesion, a: Analisis, uid: str) -> str:
        favoritos = [f for f in self.bd.favoritos(uid) if f in self.por_id][:9]
        planes = [p for p in self.bd.planes(uid, limite=5) if p["destino_id"] in self.por_id]
        if not favoritos and not planes:
            return ("⭐ Todavía no tenés favoritos ni planes guardados.\n"
                    "Cuando veas un destino que te guste escribí *guardar*, y después de un "
                    "itinerario o presupuesto escribí *guardar plan*.")
        lineas = []
        if favoritos:
            s.opciones, s.estado = favoritos, "lista"
            lineas.append("⭐ *Tus favoritos*")
            lineas += [f"{EMOJI_NUM[n]} {self.por_id[f]['nombre']}" for n, f in enumerate(favoritos, start=1)]
            lineas.append("_Escribí el número para ver el destino._")
        if planes:
            lineas += ["", "💾 *Tus planes guardados*"]
            lineas += ["• " + self._texto_plan(p) for p in planes]
        lineas += ["", "Escribí *borrar mis datos* si querés eliminar todo."]
        return "\n".join(lineas)

    def _texto_plan(self, p: dict) -> str:
        nombre = self.por_id[p["destino_id"]]["nombre"]
        fecha = p["fecha"][:10]
        if p["tipo"] == "presupuesto":
            return (f"{nombre}: {p['dias']} día(s), {p['personas']} persona(s), nivel "
                    f"{NOMBRE_NIVEL.get(p['nivel'], p['nivel'])} ≈ ${p['total']:,.2f} ({fecha})")
        return f"{nombre}: itinerario de {p['dias']} día(s) ({fecha})"

    def _guardar_plan(self, s: Sesion, a: Analisis, uid: str) -> str:
        if not s.ultimo_plan:
            return ("💾 Primero armá un *itinerario* o un *presupuesto* y después escribí *guardar plan* 😉\n"
                    "Ejemplo: _armame un itinerario de 2 días en Suchitoto_.")
        nombre = self.por_id[s.ultimo_plan["destino"]]["nombre"]
        pedido = a.entidades.get("destino")
        if pedido and pedido != s.ultimo_plan["destino"]:      # pidió guardar otro destino
            return (f"🤔 El último plan que armamos es para *{nombre}*.\n"
                    f"Primero armá el de *{self.por_id[pedido]['nombre']}* (ej.: _itinerario de 2 días_) "
                    "y después escribí *guardar plan*.")
        if s.ultimo_plan.get("guardado"):
            return f"✅ Tu plan para *{nombre}* ya está guardado. Escribí *mis planes* para verlo."
        if not self.bd.tiene_consentimiento(uid):
            s.esperando, s.plan_pendiente = "consentimiento", dict(s.ultimo_plan)
            return M.PEDIR_CONSENTIMIENTO
        self.bd.guardar_plan(uid, s.ultimo_plan)
        s.ultimo_plan["guardado"] = True
        return (f"💾 ¡Listo! Guardé tu plan para *{nombre}* en mi base de datos.\n"
                "Escribí *mis planes* para verlo cuando querás.")

    def _privacidad(self, s: Sesion, a: Analisis, uid: str) -> str:
        datos = self.bd.datos_de(uid)
        if datos:
            nombres = [self.por_id[f]["nombre"] for f in datos.get("favoritos", []) if f in self.por_id]
            guardado = (f"• Permiso dado el: {datos.get('consentimiento') or 'no'}\n"
                        f"• Favoritos: {', '.join(nombres) or 'ninguno'}\n"
                        f"• Planes guardados: {len(datos.get('planes', []))}")
        else:
            guardado = "• Nada 🙂"
        return (f"{M.PRIVACIDAD}\n\n📂 *Lo que tengo guardado de vos:*\n{guardado}\n\n"
                "Escribí *borrar mis datos* para eliminar todo.")

    def _sorpresa(self, s: Sesion, a: Analisis, uid: str) -> str:
        opciones = [d for d in self.destinos if d["id"] != s.destino_actual]
        elegido = random.choice(opciones)
        return "🎲 ¡Sorpresa! ¿Qué tal este lugar?\n\n" + self._ficha(s, elegido["id"])

    def _seguridad(self, s: Sesion, a: Analisis, uid: str) -> str:
        destino_id = (a.entidades.get("destino") if a else None) or s.destino_actual
        texto = M.SEGURIDAD
        if destino_id:
            d = self.por_id[destino_id]
            texto += f"\n\n💡 Para *{d['nombre']}*: {d['consejo']}"
        return texto

    def _fuera_de_alcance(self, s: Sesion, a: Analisis, uid: str) -> str:
        if "destino" in a.entidades:              # "reservame un hotel en El Tunco"
            s.destino_actual = a.entidades["destino"]
            accion = "hospedaje" if "hospedaje" in a.puntajes else "info"
            return M.FUERA_CON_DESTINO + "\n\n" + self._ejecutar_accion(s, accion, uid)
        return M.FUERA_DE_ALCANCE + "\n\nEscribí *menú* para ver todo lo que sí puedo hacer 😉"

    def _no_entendido(self, s: Sesion, a: Analisis) -> str:
        s.fallos += 1
        if a.sugerencia_destino:
            return self._preguntar_destino(s, "info", a.sugerencia_destino)
        texto = M.no_entendi()
        if s.fallos >= 2:
            s.fallos = 0
            self._limpiar(s)
            texto += "\n\nTe dejo el menú para que sea más fácil 👇\n\n" + M.MENU_PRINCIPAL
        return texto

    # =====================================================================
    # Utilidades de sesión
    # =====================================================================
    def _obtener_sesion(self, usuario_id: str) -> Sesion:
        """Carga el contexto desde SQLite (si no venció) o crea una sesión nueva."""
        datos = self.bd.cargar_sesion(usuario_id, config.MINUTOS_SESION * 60)
        validos = {f.name for f in fields(Sesion)}
        s = Sesion(**{k: v for k, v in datos.items() if k in validos}) if datos else Sesion()
        s.ultima_actividad = time.time()
        return s

    def _guardar_sesion(self, usuario_id: str, s: Sesion) -> None:
        """Guarda el contexto en SQLite, SIN el nombre del usuario (privacidad)."""
        estado = asdict(s)
        estado.pop("nombre", None)
        self.bd.guardar_sesion(usuario_id, estado)

    @staticmethod
    def _actualizar_perfil(s: Sesion, e: dict) -> None:
        """Guarda en la sesión los datos que el usuario va mencionando."""
        for clave in ("compania", "nivel", "dias", "personas", "presupuesto", "intereses"):
            if clave in e:
                s.perfil[clave] = e[clave]

    def _aviso(self, s: Sesion) -> str:
        """Aviso de datos referenciales (se muestra una vez por conversación)."""
        if s.aviso_mostrado:
            return ""
        s.aviso_mostrado = True
        return "\n" + M.AVISO_REFERENCIAL

    @staticmethod
    def _limpiar_espera(s: Sesion) -> None:
        s.esperando = s.accion_pendiente = s.sugerencia = s.favorito_pendiente = s.plan_pendiente = None

    def _limpiar(self, s: Sesion, todo: bool = False) -> None:
        self._limpiar_espera(s)
        s.estado, s.opciones = "menu", []
        if todo:
            s.destino_actual, s.perfil, s.vistos, s.fallos = None, {}, [], 0
            s.ultimo_plan = None
