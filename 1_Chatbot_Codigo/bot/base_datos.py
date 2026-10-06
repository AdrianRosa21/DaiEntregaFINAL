"""
base_datos.py - Persistencia con SQLite (archivo datos/guanaco.db).

SQLite viene incluido en Python (módulo sqlite3): no hay que instalar nada.
La base se crea sola la primera vez que se ejecuta el bot.

Tablas:
  usuarios ............ código anónimo del usuario + fecha en que dio permiso
  favoritos ........... destinos guardados (solo con permiso)
  planes .............. itinerarios y presupuestos guardados (solo con permiso)
  sesiones ............ contexto de la conversación (se borra a los 30 minutos)
  interacciones ....... métricas SIN el texto del mensaje (intención y si se entendió)
  calificaciones ...... notas del 1 al 5, anónimas
  mensajes_procesados . id de cada mensaje de Vonage, para no contestar dos veces
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id              TEXT PRIMARY KEY,           -- hash SHA-256 del número (anónimo)
    consentimiento  TEXT,                       -- fecha del permiso; NULL = sin permiso
    creado          TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS favoritos (
    usuario_id  TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    destino_id  TEXT NOT NULL,
    fecha       TEXT NOT NULL,
    PRIMARY KEY (usuario_id, destino_id)
);
CREATE TABLE IF NOT EXISTS planes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    destino_id  TEXT NOT NULL,
    tipo        TEXT NOT NULL,                  -- 'itinerario' o 'presupuesto'
    dias        INTEGER,
    personas    INTEGER,
    nivel       TEXT,
    total       REAL,
    fecha       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sesiones (
    usuario_id   TEXT PRIMARY KEY,
    estado_json  TEXT NOT NULL,
    actualizado  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS interacciones (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha      TEXT NOT NULL,
    intencion  TEXT NOT NULL,
    entendido  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS calificaciones (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha  TEXT NOT NULL,
    valor  INTEGER NOT NULL CHECK (valor BETWEEN 1 AND 5)
);
CREATE TABLE IF NOT EXISTS mensajes_procesados (
    message_uuid  TEXT PRIMARY KEY,
    fecha         TEXT NOT NULL
);
"""


def ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class BaseDatos:
    """Todas las consultas SQL del chatbot están en esta clase."""

    def __init__(self, ruta=None):
        self.ruta = Path(ruta or config.ARCHIVO_BD)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with self._conexion() as con:
            con.executescript(ESQUEMA)

    @contextmanager
    def _conexion(self):
        """Abre una conexión, guarda los cambios (commit) y la cierra siempre."""
        con = sqlite3.connect(self.ruta, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")   # activa el borrado en cascada
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    # ------------------------------------------------------------------
    # Usuarios y consentimiento
    # ------------------------------------------------------------------
    def tiene_consentimiento(self, usuario_id: str) -> bool:
        with self._conexion() as con:
            fila = con.execute("SELECT consentimiento FROM usuarios WHERE id = ?",
                               (usuario_id,)).fetchone()
        return bool(fila and fila["consentimiento"])

    def dar_consentimiento(self, usuario_id: str) -> None:
        with self._conexion() as con:
            con.execute("""INSERT INTO usuarios (id, consentimiento, creado) VALUES (?, ?, ?)
                           ON CONFLICT(id) DO UPDATE SET consentimiento = excluded.consentimiento""",
                        (usuario_id, ahora(), ahora()))

    # ------------------------------------------------------------------
    # Favoritos y planes
    # ------------------------------------------------------------------
    def agregar_favorito(self, usuario_id: str, destino_id: str) -> bool:
        """Devuelve False si el destino ya estaba en favoritos."""
        with self._conexion() as con:
            cursor = con.execute("INSERT OR IGNORE INTO favoritos (usuario_id, destino_id, fecha) "
                                 "VALUES (?, ?, ?)", (usuario_id, destino_id, ahora()))
            return cursor.rowcount == 1

    def favoritos(self, usuario_id: str) -> list:
        with self._conexion() as con:
            filas = con.execute("SELECT destino_id FROM favoritos WHERE usuario_id = ? ORDER BY fecha",
                                (usuario_id,)).fetchall()
        return [f["destino_id"] for f in filas]

    def guardar_plan(self, usuario_id: str, plan: dict) -> int:
        with self._conexion() as con:
            cursor = con.execute(
                """INSERT INTO planes (usuario_id, destino_id, tipo, dias, personas, nivel, total, fecha)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (usuario_id, plan["destino"], plan["tipo"], plan.get("dias"), plan.get("personas"),
                 plan.get("nivel"), plan.get("total"), ahora()))
            return cursor.lastrowid

    def planes(self, usuario_id: str, limite: int = 5) -> list:
        with self._conexion() as con:
            filas = con.execute("""SELECT destino_id, tipo, dias, personas, nivel, total, fecha
                                   FROM planes WHERE usuario_id = ? ORDER BY id DESC LIMIT ?""",
                                (usuario_id, limite)).fetchall()
        return [dict(f) for f in filas]

    # ------------------------------------------------------------------
    # Derechos del usuario: acceso y cancelación (borrado)
    # ------------------------------------------------------------------
    def datos_de(self, usuario_id: str) -> dict:
        with self._conexion() as con:
            fila = con.execute("SELECT consentimiento FROM usuarios WHERE id = ?",
                               (usuario_id,)).fetchone()
        if not fila:
            return {}
        return {"consentimiento": fila["consentimiento"], "favoritos": self.favoritos(usuario_id),
                "planes": self.planes(usuario_id, limite=50)}

    def borrar_usuario(self, usuario_id: str) -> bool:
        """Borra al usuario y, en cascada, sus favoritos y planes; también su sesión."""
        with self._conexion() as con:
            borrados = con.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,)).rowcount
            con.execute("DELETE FROM sesiones WHERE usuario_id = ?", (usuario_id,))
        return borrados > 0

    # ------------------------------------------------------------------
    # Sesiones (memoria de la conversación)
    # ------------------------------------------------------------------
    def cargar_sesion(self, usuario_id: str, max_segundos: int) -> Optional[dict]:
        with self._conexion() as con:
            con.execute("DELETE FROM sesiones WHERE actualizado < ?", (time.time() - max_segundos,))
            fila = con.execute("SELECT estado_json FROM sesiones WHERE usuario_id = ?",
                               (usuario_id,)).fetchone()
        return json.loads(fila["estado_json"]) if fila else None

    def guardar_sesion(self, usuario_id: str, estado: dict) -> None:
        with self._conexion() as con:
            con.execute("""INSERT INTO sesiones (usuario_id, estado_json, actualizado) VALUES (?, ?, ?)
                           ON CONFLICT(usuario_id) DO UPDATE
                           SET estado_json = excluded.estado_json, actualizado = excluded.actualizado""",
                        (usuario_id, json.dumps(estado, ensure_ascii=False), time.time()))

    # ------------------------------------------------------------------
    # Métricas, calificaciones y control de duplicados
    # ------------------------------------------------------------------
    def registrar_interaccion(self, intencion: str, entendido: bool) -> None:
        with self._conexion() as con:
            con.execute("INSERT INTO interacciones (fecha, intencion, entendido) VALUES (?, ?, ?)",
                        (ahora(), intencion, int(entendido)))

    def calificar(self, valor: int) -> None:
        with self._conexion() as con:
            con.execute("INSERT INTO calificaciones (fecha, valor) VALUES (?, ?)", (ahora(), int(valor)))

    def marcar_mensaje(self, message_uuid: str) -> bool:
        """Devuelve True si el mensaje es nuevo y False si ya se había procesado."""
        with self._conexion() as con:
            cursor = con.execute("INSERT OR IGNORE INTO mensajes_procesados (message_uuid, fecha) "
                                 "VALUES (?, ?)", (message_uuid, ahora()))
            return cursor.rowcount == 1

    def resumen(self) -> dict:
        """Estadísticas calculadas con consultas SQL (COUNT, AVG, GROUP BY)."""
        with self._conexion() as con:
            total, entendidos = con.execute(
                "SELECT COUNT(*), COALESCE(SUM(entendido), 0) FROM interacciones").fetchone()
            intenciones = con.execute(
                """SELECT intencion, COUNT(*) AS veces FROM interacciones
                   GROUP BY intencion ORDER BY veces DESC LIMIT 10""").fetchall()
            promedio, cantidad = con.execute(
                "SELECT ROUND(AVG(valor), 2), COUNT(*) FROM calificaciones").fetchone()
            populares = con.execute(
                """SELECT destino_id, COUNT(*) AS veces FROM favoritos
                   GROUP BY destino_id ORDER BY veces DESC LIMIT 5""").fetchall()
            usuarios = con.execute(
                "SELECT COUNT(*) FROM usuarios WHERE consentimiento IS NOT NULL").fetchone()[0]
            planes = con.execute("SELECT COUNT(*) FROM planes").fetchone()[0]
        return {
            "mensajes_recibidos": total,
            "porcentaje_comprendidos": round(100 * entendidos / total, 1) if total else None,
            "intenciones_mas_usadas": {f["intencion"]: f["veces"] for f in intenciones},
            "calificacion_promedio": promedio,
            "cantidad_calificaciones": cantidad,
            "destinos_favoritos_populares": {f["destino_id"]: f["veces"] for f in populares},
            "usuarios_con_permiso": usuarios,
            "planes_guardados": planes,
        }
