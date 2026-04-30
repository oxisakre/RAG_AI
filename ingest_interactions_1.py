import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

# Load database credentials
load_dotenv()

# Excel configuration
file_path = "data/wechselwirkungen_equiden_db_v2.xlsx"
sheet_name = "Wirkstoff × Wirkstoff"

def ingest_drug_interactions():
    """
    Ingests Drug-to-Drug (Wirkstoff x Wirkstoff) interactions.
    Handles strict ENUM formatting by cleaning extra text in parentheses.
    """
    try:
        print(f"--- Reading data from: {sheet_name} ---")
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

        print("✅ Database connected. Starting interaction ingestion...")
        
        inserted_count = 0
        for index, row in df.iterrows():
            
            # --- ENUM CLEANING ---
            db_interaktions_typ = 'wirkstoff_wirkstoff'
            
            # Cleaning Schweregrad: 
            # 1. Takes everything before an opening parenthesis
            # 2. Replaces spaces with underscores
            # 3. Removes trailing underscores and converts to UPPERCASE
            raw_schweregrad = str(row["Schweregrad"]).split('(')[0].strip()
            db_schweregrad = raw_schweregrad.replace(" ", "_").upper().rstrip('_')

            # --- FOREIGN KEY LOOKUPS ---
            cur.execute("SELECT id FROM therapeutencheck.wirkstoffe WHERE wirkstoff_inn = %s", (row["Wirkstoff A"],))
            res_a = cur.fetchone()
            partner_a_id = res_a[0] if res_a else None

            cur.execute("SELECT id FROM therapeutencheck.wirkstoffe WHERE wirkstoff_inn = %s", (row["Wirkstoff B"],))
            res_b = cur.fetchone()
            partner_b_id = res_b[0] if res_b else None

            # --- INSERTION ---
            query = """
                INSERT INTO therapeutencheck.wechselwirkungen (
                    interaktions_typ, schweregrad,
                    partner_a_typ, partner_a_name, partner_a_id,
                    partner_b_typ, partner_b_name, partner_b_id,
                    mechanismus, klinische_konsequenz, empfehlung, evidenz, quellen
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            values = (
                db_interaktions_typ,
                db_schweregrad,
                "wirkstoff",
                row["Wirkstoff A"],
                partner_a_id,
                "wirkstoff",
                row["Wirkstoff B"],
                partner_b_id,
                row["Mechanismus"],
                row["Klinische Konsequenz beim Pferd"],
                row["Empfehlung"],
                row["Evidenz beim Pferd"],
                [row["Quelle"]] if row["Quelle"] else None
            )
            
            cur.execute(query, values)
            inserted_count += 1
            
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"\n🚀 Success! {inserted_count} drug-to-drug interactions processed.")

    except Exception as e:
        print(f"❌ Error during ingestion: {e}")

if __name__ == "__main__":
    ingest_drug_interactions()