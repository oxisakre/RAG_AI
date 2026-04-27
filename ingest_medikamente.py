import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Pfad zur Excel-Datei und zum Sheet
ruta_archivo = "data/feeder-db - pferde_arzneimittel_v3 (CaF Inout).xlsx"
hoja = "Arzneimittel"

print(f"Lese das Sheet '{hoja}' aus der Excel-Datei...")
df = pd.read_excel(ruta_archivo, sheet_name=hoja)
df = df.where(pd.notnull(df), None)

try:
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    cur = conn.cursor()

    print("✅ Verbunden. Starte Injektion der Handelspräparate...")
    
    contador = 0
    for index, fila in df.iterrows():
        # SCHRITT 1: Die UUID des Wirkstoffs aus der anderen Tabelle holen
        wirkstoff_name = fila["Wirkstoff"]
        cur.execute("SELECT id FROM therapeutencheck.wirkstoffe WHERE wirkstoff_inn = %s", (wirkstoff_name,))
        resultado = cur.fetchone()
        
        if resultado is None:
            print(f"⚠️ Warnung: Wirkstoff '{wirkstoff_name}' nicht in Datenbank gefunden. Überspringe {fila['Handelsname']}.")
            continue
            
        wirkstoff_id = resultado[0]

        # SCHRITT 2: Das Medikament mit der gefundenen ID speichern
        consulta = """
            INSERT INTO therapeutencheck.medikamente (
                handelsname, wirkstoff_id, zulassungsstatus, dosierung_pferd, 
                applikationsweg, anwendung, wirkung, nebenwirkungen, 
                kreuzreaktionen, wartezeit, rezeptpflicht, fei_dopingstatus, 
                quelle_url
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING;
        """
        
        # Mapping der Excel-Spalten auf die DB-Spalten von Carsten
        valores = (
            fila["Handelsname"],
            wirkstoff_id,
            fila["Zulassungsstatus"],
            fila["Dosierung (Pferd)"],
            fila["Applikationsweg"],
            fila["Anwendung"],
            fila["Wirkung"],
            fila["Nebenwirkungen"],
            fila["Kreuzreaktionen"],
            fila["Wartezeit (Fleisch/Milch)"],
            fila["Rezeptpflicht"],
            fila["Dopingrelevanz / FEI-Absetzfristen"],
            fila["Quelle"]
        )
        
        cur.execute(consulta, valores)
        contador += 1
        
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"\n🚀 Erfolg! {contador} Medikamente wurden in die Tabelle 'medikamente' eingetragen.")

except Exception as e:
    print("❌ Fehler bei der Injektion:")
    print(e)