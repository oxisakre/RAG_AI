import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

# Load database credentials
load_dotenv()

# Excel configuration
file_path = "data/wechselwirkungen_equiden_db_v2.xlsx"
sheet_name = "OKAPI Produkte × Medikament"

def ingest_okapi_interactions():
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        df = df.where(pd.notnull(df), None)

        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        cur = conn.cursor()

        inserted_count = 0
        for index, row in df.iterrows():
            
            db_interaktions_typ = 'okapi_produkt_wirkstoff'
            
            # Strict ENUM mapping for Schweregrad
            raw_schweregrad = str(row["Schweregrad"]).upper()
            if "KONTRAINDIZIERT" in raw_schweregrad: 
                db_schweregrad = "KONTRAINDIZIERT"
            elif "SCHWERWIEGEND" in raw_schweregrad: 
                db_schweregrad = "SCHWERWIEGEND"
            elif "KLINISCH" in raw_schweregrad: 
                db_schweregrad = "KLINISCH_RELEVANT"
            elif "BEACHTEN" in raw_schweregrad or "MONITORING" in raw_schweregrad: 
                db_schweregrad = "MONITORING"
            elif "GÜNSTIG" in raw_schweregrad or "GUENSTIG" in raw_schweregrad: 
                db_schweregrad = "GUENSTIG"
            else: 
                db_schweregrad = "MONITORING" # Fallback

            # Clean Sanoanimal-Praxisrelevanz 
            raw_praxis = str(row["Sanoanimal-Praxisrelevanz"])
            db_praxisrelevanz = raw_praxis.replace("—", " ").split()[0].upper() if raw_praxis != "None" else None

            # Foreign Key Lookups
            partner_a_typ = "okapi_produkt"
            partner_a_name = row["OKAPI Produkt / Inhaltsstoff"]

            cur.execute("SELECT id FROM therapeutencheck.wirkstoffe WHERE wirkstoff_inn = %s", (row["Medikament / Wirkstoffklasse"],))
            res_b = cur.fetchone()
            partner_b_id = res_b[0] if res_b else None

            # Insertion
            query = """
                INSERT INTO therapeutencheck.wechselwirkungen (
                    interaktions_typ, schweregrad, sanoanimal_praxisrelevanz,
                    partner_a_typ, partner_a_name, partner_a_id,
                    partner_b_typ, partner_b_name, partner_b_id,
                    mechanismus, klinische_konsequenz, empfehlung, evidenz, quellen
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            values = (
                db_interaktions_typ,
                db_schweregrad,
                db_praxisrelevanz,
                partner_a_typ,
                partner_a_name,
                None,
                "wirkstoff",
                row["Medikament / Wirkstoffklasse"],
                partner_b_id,
                row["Mechanismus"],
                row["Klinische Konsequenz beim Pferd"],
                row["Empfehlung für Therapeuten"],
                row["Evidenzbasis"],
                [row["Quelle"]] if row["Quelle"] else None
            )
            
            cur.execute(query, values)
            inserted_count += 1
            
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"Success! {inserted_count} OKAPI product interactions processed.")

    except Exception as e:
        print(f"Error during ingestion: {e}")

if __name__ == "__main__":
    ingest_okapi_interactions()