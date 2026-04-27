import os
from unittest import result
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_professional_demo():
    """
    Demonstrates the relational link between Commercial Products 
    and Active Ingredients within the Sanoanimal database.
    """
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        cur = conn.cursor()

        # Define the drug to search (e.g., Equipalazone)
        search_term = "Equipalazone"

        # SQL Query joining 'medikamente' (Products) and 'wirkstoffe' (Ingredients)
        query = """
            SELECT m.handelsname, w.wirkstoff_inn, m.anwendung, w.wirkmechanismus
            FROM therapeutencheck.medikamente m
            JOIN therapeutencheck.wirkstoffe w ON m.wirkstoff_id = w.id
            WHERE m.handelsname ILIKE %s;
        """

        print(f"--- Sanoanimal DB Query: Searching for '{search_term}' ---")
        cur.execute(query, (f"%{search_term}%",))
        result = cur.fetchone()

        if result:
            print(f"\n✅ PRODUCT FOUND: {result[0]}")
            print(f"🧪 ACTIVE INGREDIENT (INN): {result[1]}")
            print(f"📖 APPLICATION: {result[2]}")
            print(f"⚙️ PHARMACOLOGICAL MECHANISM: {result[3]}")
        else:
            print(f"❌ No records found for '{search_term}'.")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"❌ Database connection error: {e}")

if __name__ == "__main__":
    run_professional_demo()