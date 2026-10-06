# 🇸🇻 Guanaco Viajero — Chatbot de turismo para WhatsApp (Vonage + Cloudflare + SQLite)

Chatbot en **Python** que recomienda destinos turísticos de **El Salvador** según las preferencias
del usuario (playa, montaña o ciudad) y da información de **hospedaje, transporte y actividades**.
Funciona en **WhatsApp** con la **Messages API de Vonage** (Sandbox), un **túnel de Cloudflare**
y una base de datos **SQLite**.

```
📱 WhatsApp ──► Vonage (Sandbox) ──► https://xxxx.trycloudflare.com ──► cloudflared ──► Flask (app.py :5000)
                    ▲                                                                       │
                    └──────────── Messages API (POST /v1/messages, 202 Accepted) ◄──────────┘
                                                      PLN ► motor de diálogo ► SQLite (guanaco.db)
```

**Innovaciones:** PLN con jerga salvadoreña y corrección ortográfica (notación de clase
`#intención` / `@entidad`), recomendador por puntos que explica sus razones, itinerario automático,
calculadora de presupuesto, clima en tiempo real (Open-Meteo), destinos cercanos con la ubicación de
WhatsApp, enlace a Google Maps, **persistencia en SQLite** (contexto, favoritos y planes guardados),
privacidad por diseño (hash SHA-256, consentimiento y borrado) y calificación del servicio.

---

## 📁 Estructura

```
1_Chatbot_Codigo/
├── app.py               ← Servidor Flask: webhooks de Vonage (/webhooks/inbound y /webhooks/status)
├── consola.py           ← Probar el bot en la terminal, sin WhatsApp (no gasta mensajes)
├── enviar_prueba.py     ← Envía un WhatsApp de prueba para comprobar tus credenciales
├── ver_base_datos.py    ← Muestra lo guardado en SQLite (evidencia para el reporte)
├── config.py            ← Configuración (lee las credenciales del archivo .env)
├── credenciales_ejemplo.txt ← Plantilla: 0_configurar_credenciales.bat la copia como .env
├── .env                 ← TUS credenciales de Vonage (se crea en tu PC; no va en el ZIP)
├── requirements.txt     ← Librerías: flask, requests, python-dotenv
├── bot/
│   ├── nlp.py           ← PLN: normalización, jerga, tokens, corrección, intenciones y entidades
│   ├── motor.py         ← Gestor del diálogo: estados, contexto y llenado de datos faltantes
│   ├── base_datos.py    ← Persistencia SQLite: 7 tablas y todas las consultas SQL
│   ├── vonage_api.py    ← Envío de mensajes con la Messages API de Vonage
│   ├── recomendador.py  ← Algoritmo de recomendación por puntos + distancias (Haversine)
│   ├── planificador.py  ← Itinerario automático y calculadora de presupuesto
│   ├── servicios.py     ← APIs externas: clima (Open-Meteo) y Google Maps
│   ├── privacidad.py    ← Código anónimo (hash SHA-256) del número de WhatsApp
│   └── mensajes.py      ← Textos del bot (tono salvadoreño)
├── datos/
│   ├── destinos.json    ← Base de conocimiento: 22 destinos de El Salvador
│   └── guanaco.db       ← Base de datos SQLite (se crea sola al usar el bot)
├── pruebas/
│   ├── test_chatbot.py  ← 57 pruebas automáticas (unittest), Vonage simulado
│   └── evaluar_nlp.py   ← Mide la exactitud del PLN
└── 0_ … 7_*.bat         ← Accesos directos para Windows (doble clic)
```

## ▶️ Cómo ejecutarlo (Windows) — resumen

| Paso | Doble clic en | Qué hace |
|---|---|---|
| 1 | `1_instalar_dependencias.bat` | Instala Flask, Requests y python-dotenv (una sola vez) |
| 2 | `0_configurar_credenciales.bat` | Abre `.env` para pegar **API Key**, **API Secret** y tu número |
| 3 | *(en el celular)* | Unite al Sandbox de WhatsApp: QR o frase de dashboard.vonage.com/messages/sandbox |
| 4 | `6_enviar_mensaje_prueba.bat` | Comprueba las credenciales: te llega un WhatsApp |
| 5 | `3_iniciar_bot.bat` | Enciende el servidor Flask en el puerto 5000 (dejarlo abierto) |
| 6 | `4_abrir_tunel_cloudflared.bat` | Abre el túnel y muestra `https://xxxx.trycloudflare.com` (dejarlo abierto) |
| 7 | *(en el navegador)* | En el Sandbox pegá **Inbound** `…/webhooks/inbound` y **Status** `…/webhooks/status` → *Save webhooks* |
| 8 | *(en WhatsApp)* | Escribile **hola** al número del Sandbox |

Sin internet o sin WhatsApp: `2_probar_en_consola.bat`. Ver la base de datos: `7_ver_base_de_datos.bat`.
El manual completo con capturas está en la carpeta `2_Documentacion`.

## 🗄️ Base de datos SQLite (`datos/guanaco.db`)

| Tabla | Qué guarda |
|---|---|
| `usuarios` | Código anónimo (hash) + fecha del permiso |
| `favoritos` | Destinos guardados (solo con permiso) |
| `planes` | Itinerarios y presupuestos guardados (solo con permiso) |
| `sesiones` | Contexto de la conversación en JSON (se borra a los 30 min) |
| `interacciones` | Intención detectada y si se entendió (**sin** el texto del mensaje) |
| `calificaciones` | Notas del 1 al 5, anónimas |
| `mensajes_procesados` | `message_uuid` de Vonage para no contestar dos veces un reintento |

## 🧪 Pruebas

```
python -m unittest discover -s pruebas -v     # 57 pruebas automáticas (no envían mensajes reales)
python pruebas/evaluar_nlp.py                 # exactitud del PLN
```

## 💬 Ejemplos de uso

- `hola` → menú principal
- `quiero ir a la playa con mis cheros`
- `¿cómo llego a Suchitoto?`
- `armame un itinerario de 2 días en la Ruta de las Flores` → `guardar plan`
- `¿cuánto me sale ir a El Pital 2 días con 3 personas?`
- `clima en Coatepeque` · 📍 enviar ubicación · `mis planes` · `privacidad` · `borrar mis datos` · `salir`

## ⚠️ Límites del Sandbox de Vonage

- 100 mensajes al mes y 1 mensaje por segundo (el bot espera 1.1 s entre mensajes largos).
- Solo responde a números que se unieron al Sandbox. Si pasan 24 h sin escribirle, mandá otro mensaje.
- La dirección del túnel `trycloudflare.com` cambia cada vez que se abre: hay que pegarla de nuevo.

## ⚖️ Uso responsable

- La información es **referencial** (precios, horarios y rutas cambian); el bot lo avisa.
- No usa IA generativa: responde desde una base de datos revisada, para no inventar datos.
- No guarda números de teléfono, nombres ni mensajes; solo un código anónimo y, con permiso, favoritos y planes.
- Las credenciales viven en `.env` (fuera del código y del ZIP). Después de la defensa, generá un API Secret nuevo.
- Basado en la *Ley para la Protección de Datos Personales* de El Salvador (D. L. N.° 144, 2024).
