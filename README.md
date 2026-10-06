# 🇸🇻 Guanaco Viajero — Chatbot de turismo para WhatsApp

**Actividad #13 · Diseño de Aplicaciones con Inteligencia Artificial (DAI)**
3.er año de Bachillerato en Desarrollo de Software «C» · Período IV · 2026 · Estudiante N.º 16
Chatbot #4: **Planificación de Viajes y Turismo**

Chatbot en **Python** que recomienda destinos de **El Salvador** según las preferencias del usuario
(playa, montaña o ciudad) y da información de **hospedaje, transporte y actividades**.
Funciona en **WhatsApp** con la **Messages API de Vonage** (Sandbox), un **túnel de Cloudflare**
(`cloudflared`) y una base de datos **SQLite**.

```
📱 WhatsApp → Vonage (Messages API) → https://xxxx.trycloudflare.com → Flask (app.py :5000)
             → PLN (#intención + @entidades) → gestor de diálogo ↔ SQLite → respuesta por la Messages API
```

## 📁 Contenido

| Carpeta / archivo | Qué contiene |
|---|---|
| [`1_Chatbot_Codigo/`](1_Chatbot_Codigo) | Código del chatbot (ver su [README](1_Chatbot_Codigo/README.md)) |
| [`2_Infografia_y_Diagramas/`](2_Infografia_y_Diagramas) | Infografía (PDF y PNG), diagrama de flujo, tabla de intenciones/entidades y esquema de la BD |
| [`1_Manual_Paso_a_Paso.pdf`](1_Manual_Paso_a_Paso.pdf) | Cómo configurarlo: Vonage, Sandbox, cloudflared y webhooks |
| [`Entrega_ZIP/`](Entrega_ZIP) | El ZIP de entrega con todo lo anterior |

## ✨ Funcionalidades e innovaciones

- **PLN con jerga salvadoreña**: normalización, corrección ortográfica, 27 `#intenciones` y 8 `@entidades`.
- **Manejo de casos especiales**: entradas no reconocidas («¿Quisiste decir…?», ejemplos y menú),
  datos incompletos (pregunta solo lo que falta) y solicitudes fuera de alcance (explica sus límites).
- **Recomendador por puntos** que explica sus razones, **itinerario** automático y **calculadora de presupuesto**.
- **Clima en tiempo real** (Open-Meteo), **destinos cercanos** con la ubicación de WhatsApp y enlace a Google Maps.
- **Persistencia con SQLite**: contexto de la conversación, favoritos y «guardar plan» (solo con permiso).
- **Privacidad por diseño**: hash SHA-256 del número, consentimiento, «borrar mis datos» en cascada
  y credenciales en `.env` (fuera del código).

## ▶️ Ejecución rápida (Windows)

1. `1_instalar_dependencias.bat` → instala Flask, Requests y python-dotenv.
2. `0_configurar_credenciales.bat` → pegar API Key y API Secret de Vonage en `.env`.
3. `3_iniciar_bot.bat` y `4_abrir_tunel_cloudflared.bat`.
4. En el Sandbox de Vonage: Inbound `…/webhooks/inbound` y Status `…/webhooks/status`.
5. Escribir **hola** al número del Sandbox. Sin WhatsApp: `2_probar_en_consola.bat`.

## 🧪 Pruebas

`python -m unittest discover -s pruebas -v` → **57/57** pruebas aprobadas (Vonage simulado) ·
`python pruebas/evaluar_nlp.py` → **118/118** intenciones correctas.

> 🔒 Este repositorio **no** incluye el archivo `.env` (credenciales) ni la base de datos `guanaco.db`.
