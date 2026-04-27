import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Usamos el Excel de los medicamentos (el que te dio error)
ruta_archivo = "data/feeder-db - pferde_arzneimittel_v3 (CaF Inout).xlsx"
hoja = "Arzneimittel"

try:
    print("Leyendo el Excel para buscar ingredientes faltantes...")
    df = pd.read_excel(ruta_archivo, sheet_name=hoja)
    # Agarramos todos los nombres de la columna "Wirkstoff" (sin repetir)
    ingredientes_en_excel = df["Wirkstoff"].unique()

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cur = conn.cursor()

    print("Chequeando la base de datos...")
    
    contador_nuevos = 0
    for nombre in ingredientes_en_excel:
        if nombre is None or str(nombre) == 'nan': continue
        
        # ¿Existe este ingrediente en la tabla de wirkstoffe?
        cur.execute("SELECT id FROM therapeutencheck.wirkstoffe WHERE wirkstoff_inn = %s", (nombre,))
        
        if cur.fetchone() is None:
            # Si no existe, lo creamos con datos genéricos
            cur.execute("""
                INSERT INTO therapeutencheck.wirkstoffe (
                    wirkstoff_inn, wirkstoffklasse, therapeutische_kategorie, 
                    wirkmechanismus, pferd_besonderheiten
                ) VALUES (%s, 'Genérico', 'Pendiente de Clasificación', 'Ver documentación', 'Cargado automáticamente')
            """, (nombre,))
            contador_nuevos += 1
            print(f" + Agregado ingrediente faltante: {nombre}")

    conn.commit()
    cur.close()
    conn.close()
    print(f"\n✅ ¡Listo! Se crearon {contador_nuevos} ingredientes que faltaban.")

except Exception as e:
    print(f"❌ Error: {e}")