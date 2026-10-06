"""
test_chatbot.py - Pruebas automáticas (unittest) de Guanaco Viajero.

Verifican el PLN, los flujos de conversación, la persistencia en SQLite, la
privacidad y la integración con WhatsApp por Vonage (webhooks y envío),
SIN internet y SIN gastar mensajes reales: Vonage se simula.

Ejecutar desde la carpeta del proyecto:
    python -m unittest discover -s pruebas -v
"""
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

# Las pruebas usan una base de datos temporal: NUNCA tocan datos/guanaco.db
os.environ["ARCHIVO_BD"] = str(Path(tempfile.mkdtemp()) / "pruebas.db")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from bot import mensajes  # noqa: E402
from bot import vonage_api  # noqa: E402
from bot.base_datos import BaseDatos  # noqa: E402
from bot.motor import MotorConversacional  # noqa: E402
from bot.nlp import formato_guia, normalizar  # noqa: E402
from bot.planificador import estimar_presupuesto  # noqa: E402
from bot.privacidad import anonimizar  # noqa: E402
from bot.recomendador import distancia_km  # noqa: E402

# Respuesta falsa de Open-Meteo (mismo formato que la API real) para probar sin internet
CLIMA_FALSO = {
    "current": {"temperature_2m": 29.4, "apparent_temperature": 33.1, "relative_humidity_2m": 74,
                "weather_code": 2, "wind_speed_10m": 9.0},
    "daily": {"time": ["2026-10-05", "2026-10-06", "2026-10-07"], "weather_code": [95, 80, 3],
              "temperature_2m_max": [31.2, 30.8, 31.0], "temperature_2m_min": [24.1, 23.9, 24.3],
              "precipitation_probability_max": [85, 60, 30]},
}


def nueva_bd():
    """Base de datos SQLite vacía en una carpeta temporal."""
    return BaseDatos(Path(tempfile.mkdtemp()) / "guanaco_prueba.db")


def sql(bd, consulta, parametros=()):
    """Ejecuta una consulta directa en la base de prueba y cierra la conexión."""
    con = sqlite3.connect(bd.ruta)
    try:
        filas = con.execute(consulta, parametros).fetchall()
        con.commit()
        return filas
    finally:
        con.close()


def crear_motor(clima=None, bd=None):
    """Motor con base de datos temporal (las pruebas no tocan los datos reales)."""
    return MotorConversacional(bd=bd or nueva_bd(), servicio_clima=clima or (lambda destino: None))


class RespuestaFalsa:
    """Imita la respuesta de requests.post para probar el envío sin internet."""

    def __init__(self, codigo, datos=None):
        self.status_code, self._datos = codigo, datos or {}
        self.text = str(self._datos)

    def json(self):
        return self._datos


# ======================================================================
class PruebasPLN(unittest.TestCase):
    """Procesamiento de lenguaje natural."""

    @classmethod
    def setUpClass(cls):
        cls.nlp = crear_motor().nlp

    def test_normalizacion(self):
        self.assertEqual(normalizar("¡¡HÓLAAA, Montaña!!"), "hola montana")

    def test_jerga_salvadorena(self):
        a = self.nlp.analizar("quiero ir a la playa con mis cheros, tengo poco pisto")
        self.assertEqual(a.entidades["compania"], "amigos")
        self.assertEqual(a.entidades["tipo"], "playa")

    def test_correccion_ortografica(self):
        a = self.nlp.analizar("hotles en suchitotto")
        self.assertEqual(a.intencion, "hospedaje")
        self.assertEqual(a.entidades["destino"], "suchitoto")

    def test_intenciones_principales(self):
        casos = {
            "hola": "saludo", "¿cómo llego a Suchitoto?": "transporte",
            "hoteles baratos en El Tunco": "hospedaje", "¿qué hacer en Ataco?": "actividades",
            "¿va a llover en El Pital?": "clima", "armame un itinerario": "itinerario",
            "¿cuánto me sale ir a Coatepeque?": "presupuesto", "borrar mis datos": "borrar_datos",
            "reservame un vuelo a Cancún": "fuera_alcance", "sorprendeme": "sorpresa",
            "guardar plan": "guardar_plan", "mis planes": "ver_favoritos",
        }
        for frase, esperada in casos.items():
            with self.subTest(frase=frase):
                self.assertEqual(self.nlp.analizar(frase).intencion, esperada)

    def test_entidades_numericas(self):
        e = self.nlp.analizar("plan de 3 días para 4 personas con $200").entidades
        self.assertEqual((e["dias"], e["personas"], e["presupuesto"]), (3, 4, 200.0))

    def test_fin_de_semana_y_emoji(self):
        e = self.nlp.analizar("un finde 🏖️").entidades
        self.assertEqual((e["dias"], e["tipo"]), (2, "playa"))

    def test_origen_no_se_confunde_con_destino(self):
        e = self.nlp.analizar("¿cuánto tiempo desde la capital a Suchitoto?").entidades
        self.assertEqual(e["destino"], "suchitoto")

    def test_formato_de_la_guia(self):
        """Notación de la guía de clase: #intención y @entidad."""
        self.assertEqual(formato_guia(self.nlp.analizar("quiero ir a la playa con mis cheros")),
                         "#recomendar | @tipo: playa, @compania: amigos")
        self.assertEqual(formato_guia(self.nlp.analizar("xyzzy")),
                         "Ninguna intención detectada | Sin entidades")


# ======================================================================
class PruebasConversacion(unittest.TestCase):
    """Flujos completos de conversación."""

    def setUp(self):
        self.motor = crear_motor()

    def decir(self, texto, **extra):
        return self.motor.responder("usuario-prueba", texto, **extra)

    def test_saludo_muestra_menu(self):
        respuesta = self.decir("hola", nombre="Ana López")
        self.assertIn("Hola, Ana", respuesta)
        self.assertIn("Recomendame un destino", respuesta)

    def test_flujo_por_numeros(self):
        self.decir("hola")
        self.assertIn("Playa", self.decir("1"))               # menú -> recomendar
        self.assertIn("montaña", self.decir("2"))             # tipo -> montaña
        self.assertIn("¿Qué querés saber?", self.decir("1"))  # lista -> ficha
        self.assertIn("Cómo llegar", self.decir("2"))         # ficha -> transporte

    def test_recuerda_el_destino_en_contexto(self):
        self.decir("info de Suchitoto")
        self.assertIn("Hospedaje en Suchitoto", self.decir("¿y dónde me puedo hospedar?"))

    def test_datos_incompletos_itinerario(self):
        self.assertIn("¿De qué lugar?", self.decir("quiero un itinerario"))
        self.assertIn("¿Cuántos días", self.decir("El Pital"))
        self.assertIn("Día 2", self.decir("2"))

    def test_presupuesto_pide_lo_que_falta(self):
        self.assertIn("¿Cuántos días", self.decir("¿cuánto cuesta ir a Coatepeque?"))
        self.assertIn("¿Cuántas personas", self.decir("3"))
        self.assertIn("nivel de gasto", self.decir("somos 2"))
        self.assertIn("Total", self.decir("1"))

    def test_entrada_no_reconocida(self):
        primera = self.decir("xyzzy")
        self.assertTrue(any(texto in primera for texto in mensajes.NO_ENTENDI))
        self.assertIn("Recomendame un destino", self.decir("qwerty asdf"))   # al 2.º intento muestra el menú

    def test_solicitud_fuera_de_alcance(self):
        self.assertIn("dentro de El Salvador", self.decir("reservame un vuelo a Cancún"))

    def test_quisiste_decir(self):
        self.assertIn("¿Quisiste decir *Perquín*?", self.decir("perkin"))
        self.assertIn("Museo de la Revolución", self.decir("sí"))

    def test_opcion_inexistente(self):
        self.decir("hola")
        self.assertIn("no existe", self.decir("42"))

    def test_ubicacion_recomienda_cercanos(self):
        respuesta = self.decir("", ubicacion=(13.49, -89.38))
        self.assertIn("El Tunco", respuesta.split("\n")[2])
        self.assertIn("No guardé tu ubicación", respuesta)

    def test_multimedia(self):
        self.assertIn("solo entiendo *texto*", self.decir("", tiene_multimedia=True))

    def test_clima_sin_internet_no_se_cae(self):
        self.assertIn("No pude consultar el clima", self.decir("clima en El Tunco"))

    def test_clima_con_datos(self):
        self.motor = crear_motor(clima=lambda destino: CLIMA_FALSO)
        respuesta = self.decir("¿cómo está el clima en El Tunco?")
        self.assertIn("29 °C", respuesta)
        self.assertIn("sombrilla", respuesta)                 # 85 % de lluvia -> consejo

    def test_calificacion_al_despedirse(self):
        self.assertIn("1 al 5", self.decir("chao"))
        self.assertIn("4/5", self.decir("4"))

    def test_no_gracias_responde_una_pregunta_de_si_o_no(self):
        self.decir("info de Suchitoto")
        self.decir("guardar")                                  # pide permiso (sí/no)
        self.assertIn("no guardé nada", self.decir("no, gracias"))
        self.assertIn("1 al 5", self.decir("no, gracias"))    # ahora sí es una despedida

    def test_respuestas_caben_en_un_mensaje_de_whatsapp(self):
        frases = ["hola", "1", "1", "1", "3", "5", "3", "6", "4", "3", "menu", "ayuda", "privacidad",
                  "seguridad", "sorprendeme", "itinerario de 3 días en la Ruta de las Flores",
                  "actividades en el centro histórico", "8"]
        for frase in frases:
            with self.subTest(frase=frase):
                self.assertLessEqual(len(self.decir(frase)), config.LIMITE_CARACTERES)


# ======================================================================
class PruebasPersistenciaSQLite(unittest.TestCase):
    """La base de datos SQLite guarda el contexto, los favoritos y los planes."""

    def setUp(self):
        self.bd = nueva_bd()
        self.motor = crear_motor(bd=self.bd)

    def decir(self, texto, uid="u1", motor=None):
        return (motor or self.motor).responder(uid, texto)

    def test_se_crean_las_tablas(self):
        tablas = {f[0] for f in sql(self.bd, "SELECT name FROM sqlite_master WHERE type='table'")}
        for tabla in ("usuarios", "favoritos", "planes", "sesiones", "interacciones",
                      "calificaciones", "mensajes_procesados"):
            self.assertIn(tabla, tablas)

    def test_contexto_sobrevive_a_un_reinicio_del_servidor(self):
        self.decir("info de Suchitoto")
        motor_nuevo = crear_motor(bd=self.bd)                 # como si se apagara y encendiera
        self.assertIn("Hospedaje en Suchitoto", self.decir("¿y dónde me puedo hospedar?", motor=motor_nuevo))

    def test_la_sesion_vence_a_los_30_minutos(self):
        self.decir("info de Suchitoto")
        sql(self.bd, "UPDATE sesiones SET actualizado = ?", (time.time() - 31 * 60,))   # pasaron 31 min
        self.assertIsNone(self.bd.cargar_sesion("u1", config.MINUTOS_SESION * 60))

    def test_guardar_plan_con_permiso(self):
        self.decir("armame un itinerario de 2 días en Suchitoto")
        self.assertIn("necesito tu permiso", self.decir("guardar plan"))
        self.assertIn("Guardé tu plan", self.decir("sí"))
        self.assertIn("ya está guardado", self.decir("guardar plan"))   # no se duplica
        self.assertEqual(len(self.bd.planes("u1")), 1)
        self.assertIn("Suchitoto: itinerario de 2 día(s)", self.decir("mis planes"))

    def test_guardar_presupuesto(self):
        self.bd.dar_consentimiento("u1")
        self.decir("¿cuánto me sale ir a El Pital 2 días con 3 personas?")
        self.decir("económico")
        self.assertIn("Guardé tu plan", self.decir("guardar plan"))
        plan = self.bd.planes("u1")[0]
        self.assertEqual((plan["destino_id"], plan["tipo"], plan["personas"]), ("el_pital", "presupuesto", 3))
        self.assertGreater(plan["total"], 0)

    def test_guardar_plan_sin_plan_previo(self):
        self.assertIn("Primero armá", self.decir("guardar plan"))

    def test_borrado_en_cascada(self):
        self.bd.dar_consentimiento("u1")
        self.bd.agregar_favorito("u1", "el_tunco")
        self.bd.guardar_plan("u1", {"destino": "el_tunco", "tipo": "itinerario", "dias": 2})
        self.decir("borrar mis datos")
        self.decir("sí")
        for tabla in ("usuarios", "favoritos", "planes"):
            self.assertEqual(sql(self.bd, f"SELECT COUNT(*) FROM {tabla}")[0][0], 0, tabla)

    def test_mensajes_repetidos(self):
        self.assertTrue(self.bd.marcar_mensaje("uuid-123"))
        self.assertFalse(self.bd.marcar_mensaje("uuid-123"))

    def test_estadisticas_con_sql(self):
        self.decir("hola")
        self.decir("xyzzy")
        self.decir("chao")
        self.decir("5")
        r = self.bd.resumen()
        self.assertEqual(r["mensajes_recibidos"], 4)
        self.assertEqual(r["calificacion_promedio"], 5)
        self.assertIn("saludo", r["intenciones_mas_usadas"])


# ======================================================================
class PruebasPrivacidad(unittest.TestCase):
    """Manejo responsable de datos personales."""

    def test_hash_anonimo(self):
        codigo = anonimizar("50370001234")
        self.assertEqual(len(codigo), 16)
        self.assertEqual(codigo, anonimizar("+50370001234"))       # siempre el mismo
        self.assertNotEqual(codigo, anonimizar("50370009999"))     # distinto por usuario

    def test_la_base_no_guarda_numero_nombre_ni_mensajes(self):
        bd = nueva_bd()
        motor = crear_motor(bd=bd)
        uid = anonimizar("50370001234")
        motor.responder(uid, "info de El Tunco", nombre="Ana López")
        motor.responder(uid, "guardar")
        motor.responder(uid, "sí")
        self.assertIn("Playa El Tunco", motor.responder(uid, "mis favoritos"))
        con = sqlite3.connect(bd.ruta)
        volcado = "\n".join(con.iterdump())                        # todo el contenido de la base
        con.close()
        for dato_personal in ("50370001234", "Ana", "info de El Tunco"):
            self.assertNotIn(dato_personal, volcado)

    def test_sin_permiso_no_se_guarda_nada(self):
        motor = crear_motor()
        motor.responder("u", "info de Suchitoto")
        motor.responder("u", "guardar")
        motor.responder("u", "no")
        self.assertEqual(motor.bd.favoritos("u"), [])
        self.assertFalse(motor.bd.tiene_consentimiento("u"))


# ======================================================================
class PruebasCalculos(unittest.TestCase):
    """Algoritmos de apoyo."""

    def test_distancia_haversine(self):
        # San Salvador -> Santa Ana: unos 52 km en línea recta
        self.assertAlmostEqual(distancia_km(13.6983, -89.1914, 13.9942, -89.5597), 52, delta=5)

    def test_presupuesto_economico(self):
        destino = {"horas": 1.0}
        p = estimar_presupuesto(destino, dias=2, personas=2, nivel="economico")
        # hospedaje 15x1x2=30 + comida 12x2x2=48 + actividades 5x2x2=20 + bus (1x1x2x2+2)=6
        self.assertEqual(p["total"], 104.0)


# ======================================================================
class PruebasArchivoEnv(unittest.TestCase):
    """Revisión del archivo .env: detecta errores comunes sin mostrar las claves."""

    def setUp(self):
        carpeta = Path(tempfile.mkdtemp())
        (carpeta / ".env").write_text("# archivo de prueba\n", encoding="utf-8")
        self.parche_carpeta = mock.patch.object(config, "CARPETA_BASE", carpeta)
        self.parche_carpeta.start()

    def tearDown(self):
        self.parche_carpeta.stop()

    def test_credenciales_correctas(self):
        with mock.patch.multiple(config, VONAGE_API_KEY="abcd1234", VONAGE_API_SECRET="secreto123",
                                 MI_NUMERO_WHATSAPP="50370123456"):
            self.assertTrue(config.credenciales_listas())
            self.assertEqual(config.problemas_credenciales(), [])

    def test_todo_pegado_en_una_sola_linea(self):
        with mock.patch.multiple(config, VONAGE_API_KEY="abcd1234 VONAGE_API_SECRET=secreto123",
                                 VONAGE_API_SECRET=""):
            self.assertFalse(config.credenciales_listas())
            self.assertTrue(any("UNA sola línea" in p for p in config.problemas_credenciales()))

    def test_valores_de_ejemplo_sin_cambiar(self):
        with mock.patch.multiple(config, VONAGE_API_KEY="tu_api_key", VONAGE_API_SECRET="tu_api_secret"):
            self.assertFalse(config.credenciales_listas())

    def test_numero_con_formato_incorrecto(self):
        with mock.patch.multiple(config, VONAGE_API_KEY="abcd1234", VONAGE_API_SECRET="secreto123",
                                 MI_NUMERO_WHATSAPP="503 7012-3456"):
            self.assertTrue(config.credenciales_listas())                 # las claves sí sirven
            self.assertTrue(any("MI_NUMERO_WHATSAPP" in p for p in config.problemas_credenciales()))

    def test_ocultar_no_muestra_la_clave_completa(self):
        self.assertEqual(config.ocultar("abcd1234"), "ab••••34")
        self.assertNotIn("cd12", config.ocultar("abcd1234"))


# ======================================================================
class PruebasEnvioVonage(unittest.TestCase):
    """Envío por la Messages API de Vonage (requests.post simulado: no se gastan mensajes)."""

    def credenciales(self):
        return mock.patch.multiple(config, VONAGE_API_KEY="clave_prueba", VONAGE_API_SECRET="secreto_prueba")

    def test_modo_simulacion_sin_credenciales(self):
        with mock.patch.multiple(config, VONAGE_API_KEY="", VONAGE_API_SECRET=""), \
                mock.patch("bot.vonage_api.requests.post") as post:
            self.assertEqual(vonage_api.enviar_whatsapp("50370001234", "hola"), (False, "simulacion"))
            post.assert_not_called()

    def test_peticion_correcta_a_vonage(self):
        with self.credenciales(), mock.patch("bot.vonage_api.requests.post",
                                             return_value=RespuestaFalsa(202, {"message_uuid": "abc"})) as post:
            self.assertEqual(vonage_api.enviar_whatsapp("+50370001234", "hola"), (True, "abc"))
        url = post.call_args.args[0]
        cuerpo = post.call_args.kwargs["json"]
        self.assertEqual(url, config.URL_MENSAJES)
        self.assertEqual(post.call_args.kwargs["auth"], ("clave_prueba", "secreto_prueba"))
        self.assertEqual((cuerpo["to"], cuerpo["channel"], cuerpo["message_type"]),
                         ("50370001234", "whatsapp", "text"))

    def test_credenciales_incorrectas(self):
        with self.credenciales(), mock.patch("bot.vonage_api.requests.post",
                                             return_value=RespuestaFalsa(401, {"title": "Unauthorized"})):
            enviado, detalle = vonage_api.enviar_whatsapp("50370001234", "hola")
        self.assertFalse(enviado)
        self.assertIn(".env", detalle)

    def test_limite_de_velocidad_reintenta(self):
        respuestas = [RespuestaFalsa(429), RespuestaFalsa(202, {"message_uuid": "xyz"})]
        with self.credenciales(), mock.patch("bot.vonage_api.time.sleep"), \
                mock.patch("bot.vonage_api.requests.post", side_effect=respuestas) as post:
            self.assertEqual(vonage_api.enviar_whatsapp("50370001234", "hola"), (True, "xyz"))
        self.assertEqual(post.call_count, 2)


# ======================================================================
class PruebasWebhookVonage(unittest.TestCase):
    """Integración: simula el JSON que Vonage envía al webhook /webhooks/inbound."""

    @classmethod
    def setUpClass(cls):
        import app as servidor
        cls.servidor = servidor
        cls.cliente = servidor.app.test_client()

    def setUp(self):
        self.enviados = []
        self.servidor.motor = crear_motor()
        self.parches = [
            mock.patch.object(self.servidor, "enviar_whatsapp", side_effect=self.enviar_falso),
            mock.patch.object(config, "PROCESAR_EN_SEGUNDO_PLANO", False),
            mock.patch.object(self.servidor.time, "sleep"),
        ]
        for parche in self.parches:
            parche.start()

    def tearDown(self):
        for parche in self.parches:
            parche.stop()

    def enviar_falso(self, destino, texto, remitente=""):
        self.enviados.append({"to": destino, "text": texto, "from": remitente})
        return True, "uuid-falso"

    @staticmethod
    def mensaje(texto="hola", uuid="m-1", numero="50370001234", **extra):
        datos = {"channel": "whatsapp", "message_uuid": uuid, "to": "14157386102", "from": numero,
                 "timestamp": "2026-10-05T15:00:00Z", "message_type": "text", "text": texto,
                 "profile": {"name": "Ana López"}}
        datos.update(extra)
        return datos

    def test_webhook_texto(self):
        r = self.cliente.post("/webhooks/inbound", json=self.mensaje("hola"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.enviados[0]["to"], "50370001234")
        self.assertEqual(self.enviados[0]["from"], "14157386102")
        self.assertIn("Hola, Ana", self.enviados[0]["text"])

    def test_reintento_de_vonage_no_se_contesta_dos_veces(self):
        self.cliente.post("/webhooks/inbound", json=self.mensaje("hola", uuid="m-repetido"))
        r = self.cliente.post("/webhooks/inbound", json=self.mensaje("hola", uuid="m-repetido"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(self.enviados), 1)

    def test_webhook_con_ubicacion(self):
        datos = self.mensaje(uuid="m-ubic", message_type="location",
                             location={"lat": 13.6769, "long": -89.2797})
        datos.pop("text")
        self.cliente.post("/webhooks/inbound", json=datos)
        self.assertIn("Santa Tecla", self.enviados[0]["text"])

    def test_webhook_con_imagen(self):
        datos = self.mensaje(uuid="m-img", message_type="image", image={"url": "https://ejemplo/foto.jpg"})
        datos.pop("text")
        self.cliente.post("/webhooks/inbound", json=datos)
        self.assertIn("solo entiendo *texto*", self.enviados[0]["text"])

    def test_formato_viejo_v01(self):
        datos = {"message_uuid": "m-v01", "from": {"type": "whatsapp", "number": "50370004321"},
                 "to": {"type": "whatsapp", "number": "14157386102"},
                 "message": {"content": {"type": "text", "text": "hola"}}}
        self.cliente.post("/webhooks/inbound", json=datos)
        self.assertEqual(self.enviados[0]["to"], "50370004321")
        self.assertIn("¿Qué querés hacer?", self.enviados[0]["text"])

    def test_procesa_en_segundo_plano(self):
        with mock.patch.object(config, "PROCESAR_EN_SEGUNDO_PLANO", True):
            r = self.cliente.post("/webhooks/inbound", json=self.mensaje("hola", uuid="m-hilo"))
            self.assertEqual(r.status_code, 200)              # contesta 200 sin esperar
            self.servidor.cola.join()                         # esperamos al hilo trabajador
        self.assertEqual(len(self.enviados), 1)

    def test_webhook_de_estado(self):
        r = self.cliente.post("/webhooks/status", json={"message_uuid": "x", "status": "delivered",
                                                         "channel": "whatsapp"})
        self.assertEqual(r.status_code, 200)

    def test_post_sin_datos_no_se_cae(self):
        self.assertEqual(self.cliente.post("/webhooks/inbound", data="basura").status_code, 200)
        self.assertEqual(self.enviados, [])

    def test_paginas_de_estado_y_estadisticas(self):
        self.assertEqual(self.cliente.get("/").status_code, 200)
        self.assertEqual(self.cliente.get("/webhooks/inbound").status_code, 200)
        self.assertIn("mensajes_recibidos", self.cliente.get("/estadisticas").get_json())

    def test_dividir_mensajes_largos(self):
        partes = self.servidor.dividir_mensaje("linea de prueba\n" * 600)
        self.assertTrue(all(len(p) <= config.LIMITE_CARACTERES for p in partes))
        self.assertGreater(len(partes), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
