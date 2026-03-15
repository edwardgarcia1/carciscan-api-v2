import psycopg2
import os
from app.core.config import settings

# Path to your exported TSV file
tsv_path = os.path.join(os.path.dirname(__file__), 'compounds.tsv')

try:
    # 1. Establish connection
    conn = psycopg2.connect(
        host=settings.DB_HOST,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        port=settings.DB_PORT,
    )

    conn.autocommit = False
    cur = conn.cursor()
    # ---------------------------------------------------------
    # STEP 1: Create the Table Schema
    # ---------------------------------------------------------
    print("Preparing schema...")

    # Drop existing table to ensure a clean run
    cur.execute("DROP TABLE IF EXISTS public.compounds CASCADE;")

    # Create the table.
    # Using TEXT for 'name' and 'smiles' to safely handle varying lengths.
    cur.execute("""
        CREATE TABLE public.compounds (
            "cid" INT NULL,
            "name" TEXT NULL,
            "smiles" TEXT NULL
        );
    """)

    conn.commit()
    print("Table 'compounds' created.")

    # ---------------------------------------------------------
    # STEP 2: Import TSV Data
    # ---------------------------------------------------------

    if not os.path.exists(tsv_path):
        raise FileNotFoundError(f"The file '{tsv_path}' was not found in the script directory.")

    with open(tsv_path, 'r', encoding='utf-8') as f:
        # COPY command to stream data from the TSV
        # If your TSV has a header row, add HEADER to the options:
        # WITH (FORMAT text, DELIMITER E'\t', ENCODING 'UTF8', HEADER)
        sql = "COPY public.compounds FROM STDIN WITH (FORMAT text, DELIMITER E'\\t', ENCODING 'UTF8', HEADER)"
        print(f"Importing data from {tsv_path}...")
        cur.copy_expert(sql, f)

        conn.commit()
        print("Data import completed.")

    # ---------------------------------------------------------
    # STEP 3: Constraints & Indexing
    # ---------------------------------------------------------
    print("Adding constraints and indexes...")

    # Set Primary Key
    cur.execute('ALTER TABLE public.compounds ADD CONSTRAINT compounds_pkey PRIMARY KEY ("cid");')

    # Enable Trigram Extension for fuzzy search
    cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # Create GIN Index
    cur.execute("""
        CREATE INDEX idx_compounds_name_gin 
        ON public.compounds USING gin ("name" gin_trgm_ops);
    """)

    conn.commit()
    print("Migration completed successfully.")

except Exception as e:
    print(f"An error occurred: {e}")
    conn.rollback()
    print("Transaction rolled back.")

finally:
    cur.close()
    conn.close()