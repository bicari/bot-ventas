"""Verificación de solo lectura de la clasificación de tasa de IVA.

Corre el fragmento IMPUESTO_EFECTIVO_SQL contra códigos conocidos y asserta:
  01010030 (8%)     -> 8
  01010029 (exento) -> 0

Ejecutar:  python scripts/verificar_impuestos.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.dbisam import DBISAMDatabase, IMPUESTO_EFECTIVO_SQL

ESPERADO = {"01010030": 8, "01010029": 0}

db = DBISAMDatabase()
codes = "(" + ",".join(f"'{c}'" for c in ESPERADO) + ")"
with db.connect_dbisam() as conn, conn.cursor() as cur:
    cur.execute(
        f"""SELECT FI_CODIGO, {IMPUESTO_EFECTIVO_SQL} AS IMPUESTO
            FROM SINVENTARIO
            INNER JOIN A2INVCOSTOSPRECIOS ON FIC_CODEITEM = FI_CODIGO
            WHERE FI_CODIGO IN {codes}"""
    )
    obtenido = {row[0]: round(float(row[1])) for row in cur.fetchall()}

print("Obtenido:", obtenido)
for cod, tasa in ESPERADO.items():
    assert obtenido.get(cod) == tasa, f"{cod}: esperaba {tasa}, obtuvo {obtenido.get(cod)}"
print("OK: clasificación de tasa correcta.")
