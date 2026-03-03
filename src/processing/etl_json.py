"""
ETL Pipeline: MinIO CSV → Carry Detection → SQLite 3NF
Reads tft_participants.csv from MinIO, extracts units, applies carry detection.
"""
import os
import sys
import json
import io
import pandas as pd
import sqlite3
from minio import Minio
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from processing.logic_carry import load_configs, is_unit_carry, parse_units_json

# Load environment variables
load_dotenv()

# --- CONFIG ---
def is_running_in_docker():
    return os.path.exists('/.dockerenv')

_env_endpoint = os.getenv("MINIO_ENDPOINT", None)
if _env_endpoint:
    MINIO_ENDPOINT = "minio:9000" if is_running_in_docker() else "localhost:9000"
else:
    MINIO_ENDPOINT = "localhost:9000"

MINIO_ACCESS = os.getenv("MINIO_ACCESS_KEY", os.getenv("MINIO_ROOT_USER", "admin"))
MINIO_SECRET = os.getenv("MINIO_SECRET_KEY", os.getenv("MINIO_ROOT_PASSWORD", "password12345678"))

BUCKET_RAW = "tft-raw"
BUCKET_PROCESSED = "tft-processed"

# Local paths
LOCAL_PARTICIPANTS_CSV = "data/raw/tft_participants_top150_20260205_024108.csv"
LOCAL_RAW_JSON = "data/raw/tft_raw_top150_20260205_024108.json"
DB_PATH = "data/processed/tft_data.db"


def get_minio_client():
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS,
        secret_key=MINIO_SECRET,
        secure=False
    )


def upload_raw_to_minio():
    """Upload tft_participants.csv và tft_raw.json lên MinIO"""
    print("--- UPLOAD RAW FILES TO MINIO ---")
    
    try:
        client = get_minio_client()
        
        # Create bucket if not exists
        if not client.bucket_exists(BUCKET_RAW):
            client.make_bucket(BUCKET_RAW)
            print(f"Created bucket: {BUCKET_RAW}")
        
        uploaded = []
        
        # Upload participants CSV
        if os.path.exists(LOCAL_PARTICIPANTS_CSV):
            file_name = os.path.basename(LOCAL_PARTICIPANTS_CSV)
            # Check if already exists
            try:
                existing = client.stat_object(BUCKET_RAW, file_name)
                local_size = os.path.getsize(LOCAL_PARTICIPANTS_CSV)
                if existing.size == local_size:
                    print(f"⏭️  {file_name} already exists (same size), skipping.")
                else:
                    client.fput_object(BUCKET_RAW, file_name, LOCAL_PARTICIPANTS_CSV)
                    print(f"✅ Uploaded {file_name} (updated)")
                    uploaded.append(file_name)
            except:
                client.fput_object(BUCKET_RAW, file_name, LOCAL_PARTICIPANTS_CSV)
                print(f"✅ Uploaded {file_name}")
                uploaded.append(file_name)
        
        # Upload raw JSON
        if os.path.exists(LOCAL_RAW_JSON):
            file_name = os.path.basename(LOCAL_RAW_JSON)
            try:
                existing = client.stat_object(BUCKET_RAW, file_name)
                local_size = os.path.getsize(LOCAL_RAW_JSON)
                if existing.size == local_size:
                    print(f"⏭️  {file_name} already exists (same size), skipping.")
                else:
                    client.fput_object(BUCKET_RAW, file_name, LOCAL_RAW_JSON)
                    print(f"✅ Uploaded {file_name} (updated)")
                    uploaded.append(file_name)
            except:
                client.fput_object(BUCKET_RAW, file_name, LOCAL_RAW_JSON)
                print(f"✅ Uploaded {file_name}")
                uploaded.append(file_name)
        
        return uploaded
        
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return []


def read_participants_from_minio() -> pd.DataFrame:
    """Read participants CSV from MinIO"""
    print("\n--- READ FROM MINIO ---")
    
    try:
        client = get_minio_client()
        file_name = os.path.basename(LOCAL_PARTICIPANTS_CSV)
        
        response = client.get_object(BUCKET_RAW, file_name)
        csv_bytes = response.read()
        response.close()
        response.release_conn()
        
        df = pd.read_csv(io.BytesIO(csv_bytes))
        print(f"✅ Read {len(df)} rows from MinIO")
        return df
        
    except Exception as e:
        print(f"❌ MinIO read error: {e}")
        print("Falling back to local file...")
        if os.path.exists(LOCAL_PARTICIPANTS_CSV):
            return pd.read_csv(LOCAL_PARTICIPANTS_CSV)
        return None


def parse_units_from_raw(units_str: str) -> list:
    """Wrapper for logic_carry.parse_units_json"""
    if not units_str or pd.isna(units_str):
        return []
    
    try:
        # Handle escaped quotes from CSV
        units = json.loads(units_str)
        return parse_units_json(units)
        
    except json.JSONDecodeError:
        # Try cleaning quotes if direct parse fails
        try:
            cleaned = units_str.replace('""', '"')
            units = json.loads(cleaned)
            return parse_units_json(units)
        except:
            return []
    except Exception:
        return []


def deduplicate_df(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicates by (match_id, puuid)"""
    before = len(df)
    df = df.drop_duplicates(subset=['match_id', 'puuid'], keep='first')
    after = len(df)
    
    if before != after:
        print(f"🔄 Deduplication: {before} → {after} rows ({before - after} duplicates removed)")
    
    return df


def run_etl():
    """Main ETL: MinIO → Parse → Carry Detection → SQLite"""
    print("\n--- ETL: MINIO → CARRY DETECTION → SQLITE ---")
    
    # 1. Load configs
    champ_map, items_roles, basic_components, ornn_items, unit_costs = load_configs()
    if not champ_map:
        print("❌ Failed to load configs. Aborting.")
        return
    
    # 2. Read from MinIO
    df = read_participants_from_minio()
    if df is None or len(df) == 0:
        print("❌ No data to process.")
        return
    
    # 3. Deduplicate
    df = deduplicate_df(df)
    
    # 4. Process each row
    carries_data = []
    players_set = set()
    matches_set = set()
    skipped = 0
    
    print("\n🔍 Processing carries...")
    for idx, row in df.iterrows():
        units_str = row.get('units', '')
        parsed_units = parse_units_from_raw(units_str)
        
        # Apply unit_costs correction
        for unit in parsed_units:
            if unit_costs and unit['character_id'] in unit_costs:
                unit['cost'] = unit_costs[unit['character_id']]
        
        # Find carries
        carries_found = []
        for unit in parsed_units:
            if is_unit_carry(unit, champ_map, items_roles, basic_components, ornn_items):
                carries_found.append({
                    'carry_name': unit['character_id'],
                    'carry_tier': unit['tier'],
                    'carry_cost': unit['cost']
                })
        
        if not carries_found:
            skipped += 1
            continue
        
        puuid = row.get('puuid', '')
        match_id = row.get('match_id', '')
        
        players_set.add(puuid)
        matches_set.add(match_id)
        
        for carry in carries_found:
            carries_data.append({
                'puuid': puuid,
                'match_id': match_id,
                'placement': row.get('placement', 0),
                'level': row.get('level', 0),
                'carry_name': carry['carry_name'],
                'carry_tier': carry['carry_tier'],
                'carry_cost': carry['carry_cost']
            })
    
    print(f"✅ Found {len(carries_data)} carry instances. Skipped {skipped} rows without carry.")
    
    # 5. Create DataFrames
    df_players = pd.DataFrame({'puuid': list(players_set)})
    df_matches = pd.DataFrame({'match_id': list(matches_set)})
    df_carries = pd.DataFrame(carries_data)
    
    # 6. Save to SQLite
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    
    conn.execute("PRAGMA foreign_keys = ON;")
    
    conn.execute("DROP TABLE IF EXISTS carries;")
    conn.execute("DROP TABLE IF EXISTS players;")
    conn.execute("DROP TABLE IF EXISTS matches;")
    
    conn.execute("""
        CREATE TABLE players (
            puuid TEXT PRIMARY KEY
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
            puuid TEXT,
            match_id TEXT,
            placement INTEGER,
            level INTEGER,
            carry_name TEXT,
            carry_tier INTEGER,
            carry_cost INTEGER,
            FOREIGN KEY (puuid) REFERENCES players(puuid),
            FOREIGN KEY (match_id) REFERENCES matches(match_id)
        );
    """)
    
    df_players.to_sql("players", conn, if_exists="append", index=False)
    df_matches.to_sql("matches", conn, if_exists="append", index=False)
    df_carries.to_sql("carries", conn, if_exists="append", index=False)
    
    print(f"\n✅ Saved to SQLite (3NF):")
    print(f"   - players: {len(df_players)} rows")
    print(f"   - matches: {len(df_matches)} rows")
    print(f"   - carries: {len(df_carries)} rows")
    
    conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--upload-only", action="store_true", help="Only upload to MinIO")
    args = parser.parse_args()
    
    # Always upload first
    upload_raw_to_minio()
    
    if not args.upload_only:
        run_etl()
    
    print("\n🎉 Done!")
