import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

# Cargar contraseñas
load_dotenv()

ruta_archivo = "data/wirkstoffe_equiden_v2.xlsx"
hoja = "Wirkstoffe Equiden"

print(f"Leyendo la hoja '{hoja}' del Excel...")
df = pd.read_excel(ruta_archivo, sheet_name=hoja)

# Truco: Pandas lee las celdas vacías como "NaN", lo cual rompe PostgreSQL.
df = df.where(pd.notnull(df), None)

try:
    # Conectar a la base
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cur = conn.cursor()

    print("✅ Conectado a la base de datos. Inyectando medicamentos...")
    
    contador = 0
    # Recorrer el Excel fila por fila
    for index, fila in df.iterrows():
        # Instrucción SQL corregida con los nombres exactos de Carsten
        consulta = """
            INSERT INTO therapeutencheck.wirkstoffe (
                wirkstoff_inn, wirkstoffklasse, therapeutische_kategorie, 
                wirkmechanismus, bioverfuegbarkeit_oral, hwz_plasma, 
                verteilungsvolumen, metabolismus, elimination, 
                therapeutischer_index, pferd_besonderheiten
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (wirkstoff_inn) DO NOTHING;
        """
        
        # Extraer exactamente los nombres de las columnas del Excel
        valores = (
            fila["Wirkstoff (INN)"],
            fila["Wirkstoffklasse"],
            fila["Therapeutische Kategorie"],
            fila["Wirkmechanismus (pferdespezifisch)"],
            fila["Pharmakokinetik Pferd: Bioverfügbarkeit oral"],
            fila["Pharmakokinetik Pferd: HWZ Plasma"],
            fila["Pharmakokinetik Pferd: Verteilungsvolumen"],
            fila["Pharmakokinetik Pferd: Metabolismus"],
            fila["Pharmakokinetik Pferd: Elimination"],
            fila["Therapeutischer Index / Sicherheit"],
            fila["Pferdespezifische Besonderheiten"]
        )
        
        # Ejecutar la inyección
        cur.execute(consulta, valores)
        contador += 1
        
    # Guardar los cambios
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"🚀 ¡Impecable! Se procesaron {contador} medicamentos en la tabla 'wirkstoffe'.")

except Exception as e:
    print("❌ Error al inyectar los datos:")
    print(e)