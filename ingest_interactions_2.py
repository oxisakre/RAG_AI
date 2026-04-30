import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

# Load database credentials
load_dotenv()

# Excel configuration
file_path = "data/wechselwirkungen_equiden_db_v2.xlsx"
sheet_name = "Wirkstoff × Futtermittel"

def ingest_food_interactions():
    """
    Ingests Drug-to-Food (Wirkstoff x Futtermittel) interactions.
    Links Wirkstoff (A) to the database and stores Food (B) as text.
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

        print("✅ Database connected. Starting food interaction ingestion...")
        
        inserted_count = 0
        for index, row in df.iterrows():
            
            # --- ENUM CLEANING ---
            db_interaktions_typ = 'wirkstoff_futtermittel'
            
            raw_schweregrad = str(row["Schweregrad"]).split('(')[0].strip()
            db_schweregrad = raw_schweregrad.replace(" ", "_").upper().rstrip('_')

            # --- FOREIGN KEY LOOKUP ---
            # Partner A is the drug ingredient
            cur.execute("SELECT id FROM therapeutencheck.wirkstoffe WHERE wirkstoff_inn = %s", (row["Wirkstoff"],))
            res_a = cur.fetchone()
            partner_a_id = res_a[0] if res_a else None

            # Partner B is the food (no ID needed)
            partner_b_typ = "futter"
            partner_b_name = row["Futtermittel / Ergänzung"]

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
                row["Wirkstoff"],      # Name A
                partner_a_id,          # UUID A
                partner_b_typ,         # Type B (futter)
                partner_b_name,        # Name B
                None,                  # UUID B (None because food has no table)
                row["Mechanismus"],
                row["Klinische Konsequenz beim Pferd"],
                row["Empfehlung"],
                row["Evidenz"],
                [row["Quelle"]] if row["Quelle"] else None
            )
            
            cur.execute(query, values)
            inserted_count += 1
            
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"\n🚀 Success! {inserted_count} food interactions processed.")

    except Exception as e:
        print(f"❌ Error during ingestion: {e}")

if __name__ == "__main__":
    ingest_food_interactions()