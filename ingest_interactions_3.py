import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

# Load database credentials
load_dotenv()

# Excel configuration
file_path = "data/wechselwirkungen_equiden_db_v2.xlsx"
sheet_name = "Wirkstoff × Erkrankung"

def ingest_disease_interactions():
    """
    Ingests Drug-to-Disease (Wirkstoff x Erkrankung) interactions.
    Combines the 'Risiko' and 'Mechanismus' columns to preserve all data.
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

        print("✅ Database connected. Starting disease interaction ingestion...")
        
        inserted_count = 0
        for index, row in df.iterrows():
            
            # --- ENUM CLEANING ---
            db_interaktions_typ = 'wirkstoff_erkrankung'
            
            raw_schweregrad = str(row["Schweregrad"]).split('(')[0].strip()
            db_schweregrad = raw_schweregrad.replace(" ", "_").upper().rstrip('_')

            # --- FOREIGN KEY LOOKUP ---
            # Partner A is the drug ingredient
            cur.execute("SELECT id FROM therapeutencheck.wirkstoffe WHERE wirkstoff_inn = %s", (row["Wirkstoff / Wirkstoffklasse"],))
            res_a = cur.fetchone()
            partner_a_id = res_a[0] if res_a else None

            # Partner B is the disease (no ID needed, stored as text)
            partner_b_typ = "erkrankung"
            partner_b_name = row["Erkrankung / Zustand"]

            # --- DATA MERGING ---
            # Combine 'Risiko' and 'Mechanismus' from Excel into the DB's mechanismus field
            risiko = row.get("Risiko", "")
            mechanismus_raw = row.get("Mechanismus", "")
            combined_mechanismus = f"Risiko: {risiko} | {mechanismus_raw}" if risiko else mechanismus_raw

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
                "wirkstoff",           # Type A
                row["Wirkstoff / Wirkstoffklasse"],  # Name A
                partner_a_id,          # UUID A
                partner_b_typ,         # Type B (erkrankung)
                partner_b_name,        # Name B
                None,                  # UUID B (None because diseases have no table)
                combined_mechanismus,  # Combined Risk + Mechanism
                row["Klinische Konsequenz"],
                row["Empfehlung"],
                row["Evidenz"],
                [row["Quelle"]] if row["Quelle"] else None
            )
            
            cur.execute(query, values)
            inserted_count += 1
            
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"\n🚀 Success! {inserted_count} disease interactions processed.")

    except Exception as e:
        print(f"❌ Error during ingestion: {e}")

if __name__ == "__main__":
    ingest_disease_interactions()