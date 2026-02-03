import os
import pandas as pd
import sqlite3
import sys
import io
from minio import Minio
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from processing.logic_carry import load_configs, find_carry_in_match

# Load environment variables
load_dotenv()

# MinIO Config - Detect environment for correct endpoint
def is_running_in_docker():
    """Check if running inside Docker container"""
    return os.path.exists('/.dockerenv')

_env_endpoint = os.getenv("MINIO_ENDPOINT", None)
if _env_endpoint:
    # If MINIO_ENDPOINT is explicitly set, use smart detection
    if is_running_in_docker():
        MINIO_ENDPOINT = "minio:9000"  # Docker internal network
    else:
        MINIO_ENDPOINT = "localhost:9000"  # Host machine access
else:
    MINIO_ENDPOINT = "localhost:9000"
    
MINIO_ACCESS = os.getenv("MINIO_ACCESS_KEY", os.getenv("MINIO_ROOT_USER", "admin"))
MINIO_SECRET = os.getenv("MINIO_SECRET_KEY", os.getenv("MINIO_ROOT_PASSWORD", "password12345678"))
BUCKET_NAME = "tft-raw-matches"

# File paths
LOCAL_CSV_PATH = "data/raw/tft_matches_vn2_top150.csv"
DB_PATH = "data/processed/tft_data.db"

# Initialize MinIO Client
def get_minio_client():
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS,
        secret_key=MINIO_SECRET,
        secure=False
    )

def upload_to_minio():
    """Upload local CSV to MinIO bucket"""
    print("--- UPLOAD TO MINIO ---")
    
    if not os.path.exists(LOCAL_CSV_PATH):
        print(f"Local file not found: {LOCAL_CSV_PATH}")
        return None
    
    try:
        minio_client = get_minio_client()
        
        # Create bucket if not exists
        if not minio_client.bucket_exists(BUCKET_NAME):
            minio_client.make_bucket(BUCKET_NAME)
            print(f"Created bucket: {BUCKET_NAME}")
        
        file_name = os.path.basename(LOCAL_CSV_PATH)
        minio_client.fput_object(BUCKET_NAME, file_name, LOCAL_CSV_PATH)
        print(f"Uploaded '{file_name}' to MinIO bucket '{BUCKET_NAME}'")
        return file_name
    except Exception as e:
        print(f"Upload error: {e}")
        return None

def read_from_minio(file_name):
    """Read CSV file from MinIO and return as DataFrame"""
    print(f"Reading '{file_name}' from MinIO...")
    
    try:
        minio_client = get_minio_client()
        response = minio_client.get_object(BUCKET_NAME, file_name)
        csv_bytes = response.read()
        response.close()
        response.release_conn()
        
        df = pd.read_csv(io.BytesIO(csv_bytes), header=0)
        return df
    except Exception as e:
        print(f"MinIO read error: {e}")
        return None

def run_etl(use_minio=True):
    """Read CSV -> Extract Carries -> Load to SQLite (3NF)"""
    print("--- ETL: TRANSFORM & LOAD TO DB (3NF) ---")
    
    try:
        # 1. Load data
        if use_minio:
            file_name = os.path.basename(LOCAL_CSV_PATH)
            df = read_from_minio(file_name)
            if df is None:
                print("Falling back to local CSV...")
                df = pd.read_csv(LOCAL_CSV_PATH, header=0)
        else:
            print(f"Reading local '{LOCAL_CSV_PATH}'...")
            df = pd.read_csv(LOCAL_CSV_PATH, header=0)
        
        print(f"Raw data: {df.shape[0]} rows.")

        # 2. Normalize column names
        target_columns = [
            "riot_id", "leaderboard_id", "match_id", "datetime", 
            "placement", "level", "traits", "units", "units_detailed", "item_column"
        ]
        if df.shape[1] == len(target_columns):
            df.columns = target_columns

        # 3. Load carry detection configs
        champ_map, items_roles, basic_components, ornn_items = load_configs()
        if not champ_map:
            print("Failed to load configs. Aborting.")
            return

        # 4. Process each row and extract carry data
        carries_data = []
        players_set = set()
        matches_set = set()
        
        skipped = 0
        for _, row in df.iterrows():
            units_str = row.get('units_detailed', '')
            carry_info = find_carry_in_match(units_str, champ_map, items_roles, basic_components, ornn_items)
            
            if carry_info is None:
                skipped += 1
                continue  # Skip rows without a carry
            
            riot_id = row.get('riot_id', '')
            match_id = row.get('match_id', '')
            
            players_set.add(riot_id)
            matches_set.add(match_id)
            
            carries_data.append({
                'riot_id': riot_id,
                'match_id': match_id,
                'placement': row.get('placement', 0),
                'level': row.get('level', 0),
                'carry_name': carry_info['carry_name'],
                'carry_tier': carry_info['carry_tier'],
                'carry_cost': carry_info['carry_cost']
            })
        
        print(f"🔍 Found {len(carries_data)} rows with carries. Skipped {skipped} rows without carry.")

        # 5. Create DataFrames for 3NF tables
        df_players = pd.DataFrame({'riot_id': list(players_set)})
        df_matches = pd.DataFrame({'match_id': list(matches_set)})
        df_carries = pd.DataFrame(carries_data)

        # 6. Save to SQLite
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        
        conn.execute("PRAGMA foreign_keys = ON;")
        
        # Drop and recreate tables
        conn.execute("DROP TABLE IF EXISTS carries;")
        conn.execute("DROP TABLE IF EXISTS players;")
        conn.execute("DROP TABLE IF EXISTS matches;")
        
        conn.execute("""
            CREATE TABLE players (
                riot_id TEXT PRIMARY KEY
            );
        """)
        conn.execute("""
            CREATE TABLE matches (
                match_id TEXT PRIMARY KEY
            );
        """)
        conn.execute("""
            CREATE TABLE carries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                riot_id TEXT,
                match_id TEXT,
                placement INTEGER,
                level INTEGER,
                carry_name TEXT,
                carry_tier INTEGER,
                carry_cost INTEGER,
                FOREIGN KEY (riot_id) REFERENCES players(riot_id),
                FOREIGN KEY (match_id) REFERENCES matches(match_id)
            );
        """)
        
        # Insert data
        df_players.to_sql("players", conn, if_exists="append", index=False)
        df_matches.to_sql("matches", conn, if_exists="append", index=False)
        df_carries.to_sql("carries", conn, if_exists="append", index=False)
        
        print(f"SUCCESS: Saved to 3NF tables:")
        print(f"   - players: {len(df_players)} rows")
        print(f"   - matches: {len(df_matches)} rows")  
        print(f"   - carries: {len(df_carries)} rows")
        
        conn.close()
        
    except Exception as e:
        print(f"Data processing error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # First upload to MinIO if local file exists
    if os.path.exists(LOCAL_CSV_PATH):
        upload_to_minio()
    
    # Run ETL from MinIO (with fallback to local)
    run_etl(use_minio=True)