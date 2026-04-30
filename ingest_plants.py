import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

# Load database credentials
load_dotenv()

# Excel configuration
file_path = "data/giftpflanzen_equiden_v2.xlsx"
sheet_name = "Giftpflanzen Equiden"

def ingest_toxic_plants():
    """
    Ingests toxic plant data into the 'giftpflanzen' table.
    Matches the exact schema columns and cleans CHECK constraints.
    """
    try:
        print(f"--- Reading data from: {sheet_name} ---")
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        
        # Clean data: Replace NaN with None for PostgreSQL compatibility
        df = df.where(pd.notnull(df), None)

        # Establish database connection
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        cur = conn.cursor()

        print("✅ Database connected. Starting ingestion...")
        
        inserted_count = 0
        for index, row in df.iterrows():
            
            # DATA CLEANING 1: Evidenz beim Pferd
            # Turns "GESICHERT — multiple cases..." into "GESICHERT"
            evidenz_raw = row["Evidenz beim Pferd"]
            evidenz_clean = str(evidenz_raw).split()[0] if evidenz_raw else None
            
            # DATA CLEANING 2: Giftigkeitsstufe (Toxic Level)
            # Turns "STARK (chronisch kumulativ)" into "STARK" to pass DB constraints
            gift_raw = row["Giftigkeitsstufe"]
            gift_clean = str(gift_raw).split()[0] if gift_raw else None
            
            query = """
                INSERT INTO therapeutencheck.giftpflanzen (
                    deutscher_name, botanischer_name, familie, giftigkeitsstufe, 
                    evidenz_pferd, dokumentierte_faelle, toxin_wirkstoff, toxische_teile, 
                    wirkmechanismus, symptome_pferd, letale_dosis, latenzzeit, 
                    therapie, prognose, vorkommen_dach, saisonale_gefaehrdung, 
                    giftig_im_heu, verwechslungsgefahr, quellen
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
            """
            
            values = (
                row["Deutscher Name"],
                row["Botanischer Name"],
                row["Familie"],
                gift_clean,      # <-- Usamos la variable limpia aquí
                evidenz_clean,   # <-- Y la otra variable limpia aquí
                row["Dokumentierte Fälle / Fallberichte Equiden"],
                row["Toxin / Wirkstoff"],
                row["Toxische Pflanzenteile"],
                row["Wirkmechanismus"],
                row["Symptome beim Pferd"],
                row["Letale Dosis / Toxische Menge"],
                row["Latenzzeit"],
                row["Therapie (Erste Hilfe & Klinik)"],
                row["Prognose"],
                row["Vorkommen DACH"],
                row["Saisonale Gefährdung"],
                row["Giftig im Heu/Silage?"],
                row["Verwechslungsgefahr"],
                [row["Quelle"]] if row["Quelle"] else None
            )
            
            cur.execute(query, values)
            inserted_count += 1
            
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"\n🚀 Success! {inserted_count} toxic plants processed for the 'giftpflanzen' table.")

    except Exception as e:
        print(f"❌ Critical Error during ingestion: {e}")

if __name__ == "__main__":
    ingest_toxic_plants()