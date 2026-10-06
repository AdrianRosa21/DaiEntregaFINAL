"""
ver_base_datos.py - Muestra lo que está guardado en la base de datos SQLite (datos/guanaco.db).

Sirve como evidencia para el reporte y la defensa: se ve que la base guarda
códigos anónimos (hash), NO números de teléfono ni el texto de los mensajes.
"""
import sqlite3
import sys
from datetime import datetime

import config

TABLAS = ["usuarios", "favoritos", "planes", "sesiones",
          "interacciones", "calificaciones", "mensajes_procesados"]


def recortar(valor, largo: int = 48) -> str:
    if isinstance(valor, float) and valor > 1e9:          # fecha guardada como número (epoch)
        valor = datetime.fromtimestamp(valor).strftime("%Y-%m-%d %H:%M:%S")
    texto = "" if valor is None else str(valor)
    return texto if len(texto) <= largo else texto[:largo - 1] + "…"


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")       # emojis en la consola de Windows
    except (AttributeError, ValueError):
        pass
    if not config.ARCHIVO_BD.exists():
        print("Todavía no existe la base de datos. Usá primero el bot o la consola.")
        return

    con = sqlite3.connect(config.ARCHIVO_BD)
    con.row_factory = sqlite3.Row
    print("=" * 70)
    print(f"  🗄️  Base de datos SQLite: {config.ARCHIVO_BD.name}  (últimas 5 filas de cada tabla)")
    print("=" * 70)
    for tabla in TABLAS:
        total = con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
        print(f"\n📋 {tabla}  ({total} filas)")
        filas = con.execute(f"SELECT * FROM {tabla} ORDER BY rowid DESC LIMIT 5").fetchall()
        if not filas:
            print("   (vacía)")
            continue
        columnas = filas[0].keys()
        print("   " + " | ".join(columnas))
        for fila in filas:
            print("   " + " | ".join(recortar(fila[c]) for c in columnas))
    con.close()


if __name__ == "__main__":
    main()
