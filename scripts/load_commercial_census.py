import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

# --- Configuration (Based on your Docker setup) ---
DB_USER = "geo_user"
DB_PASSWORD = "g3o_p@ssw0rdAI"  
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "geoyield_db"

# Official file name from your downloads
CSV_PATH = "data/raw/241021_censcomercialbcn_opendata_2024_v5.csv"
TABLE_NAME = "commercial_venues"

def get_db_engine():
    """Creates a SQLAlchemy engine handling special characters in credentials."""
    # Escapamos la contraseña para evitar errores en la cadena de conexión
    encoded_password = quote_plus(DB_PASSWORD)
    
    conn_string = f"postgresql+psycopg2://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(conn_string)

def run_etl():
    print("🚀 Starting ETL Pipeline: Barcelona Commercial Census 2024")
    
    # --- 1. EXTRACT ---
    print(f"📥 Reading raw data from: {CSV_PATH}")
    try:
        # low_memory=False ensures robust reading of large files
        df = pd.read_csv(CSV_PATH, low_memory=False)
    except FileNotFoundError:
        print(f"❌ Error: File not found at {CSV_PATH}. Check your 'data/raw' folder.")
        return
    except Exception as e:
        print(f"❌ Error during extraction: {e}")
        return

    # --- 2. TRANSFORM ---
    print("⚙️ Filtering records for Hospitality (Restaurants, bars i hotels)...")
    
    # We use 'Nom_Grup_Activitat' as identified in our data exploration
    if 'Nom_Grup_Activitat' in df.columns:
        # We look for the hospitality group using a partial match
        mask = df['Nom_Grup_Activitat'].str.contains('Restaurants, bars i hotels', na=False, case=False)
        df_filtered = df[mask].copy()
    else:
        print("⚠️ Warning: Column 'Nom_Grup_Activitat' not found. Check CSV headers.")
        df_filtered = df.copy()
        
    print(f"✅ Transformation complete: {len(df_filtered)} venues identified.")

    # --- 3. LOAD ---
    engine = get_db_engine()
    print(f"📤 Uploading data to table: '{TABLE_NAME}'...")
    
    try:
        # This sends the clean DataFrame to PostgreSQL
        df_filtered.to_sql(TABLE_NAME, engine, if_exists='replace', index=False)
    except Exception as e:
        print(f"❌ Error during Load phase: {e}")
        return
    
    # --- 4. SPATIAL ENRICHMENT (PostGIS) ---
    print("🗺️ Generating PostGIS geometries (ST_MakePoint)...")
    try:
        with engine.begin() as conn:
            # 4.1. Add the geometry column if it doesn't exist
            conn.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326);"))
            
            # 4.2. Convert Latitude/Longitude columns into actual spatial points
            # Double quotes handle case-sensitivity in PostgreSQL column names
            conn.execute(text(f"""
                UPDATE {TABLE_NAME} 
                SET geom = ST_SetSRID(ST_MakePoint("Longitud", "Latitud"), 4326)
                WHERE "Longitud" IS NOT NULL AND "Latitud" IS NOT NULL;
            """))
            
            # 4.3. Create a spatial index for high-performance mapping
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS {TABLE_NAME}_geom_idx ON {TABLE_NAME} USING GIST (geom);"))
        
        print("🎉 ETL Process finished successfully! Data is ready in PostGIS.")
        
    except Exception as e:
        print(f"❌ Error during spatial enrichment: {e}")

if __name__ == "__main__":
    run_etl()