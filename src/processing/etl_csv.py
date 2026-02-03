import os
import pandas as pd
import sqlite3
from minio import Minio
from dotenv import load_dotenv
import io

# 1. Load Config
load_dotenv()
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET = os.getenv("MINIO_SECRET_KEY", "password12345678")
BUCKET_NAME = "tft-raw-matches"

# File paths
LOCAL_CSV_PATH = "data/raw/tft_matches_vn2_top150.csv"
DB_PATH = "data/processed/tft_data.db"

# Initialize MinIO Client
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS,
    secret_key=MINIO_SECRET,
    secure=False
)

def step_1_upload_csv_to_datalake():
    """Upload raw CSV file to MinIO for storage (Backup)"""
    print("--- STEP 1: UPLOAD TO DATA LAKE ---")
    
    # Check bucket
    if not minio_client.bucket_exists(BUCKET_NAME):
        minio_client.make_bucket(BUCKET_NAME)
    
    file_name = os.path.basename(LOCAL_CSV_PATH)
    
    try:
        minio_client.fput_object(
            BUCKET_NAME,
            file_name,
            LOCAL_CSV_PATH,
        )
        print(f"✅ Uploaded '{file_name}' to MinIO bucket '{BUCKET_NAME}'.")
        return file_name
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return None

def step_2_transform_and_load_db(minio_file_name):
    """Read from MinIO (With Header) -> Pandas -> SQLite"""
    print("\n--- STEP 2: TRANSFORM & LOAD TO DB ---")
    
    try:
        # 1. Read file from MinIO
        print(f"📥 Reading '{minio_file_name}' from MinIO...")
        response = minio_client.get_object(BUCKET_NAME, minio_file_name)
        csv_bytes = response.read()
        
        # 2. Define STANDARD column names (Schema)
        target_columns = [
            "riot_id", "leaderboard_id", "match_id", "datetime", 
            "placement", "level", "traits", "units", "units_detailed", "item_column"
        ]
        
        # --- IMPORTANT CHANGE HERE ---
        # header=0: Tell Pandas the first line is the header, use it as column names
        df = pd.read_csv(io.BytesIO(csv_bytes), header=0)
        
        print(f"📊 Raw data: {df.shape[0]} rows, {df.shape[1]} columns.")
        print(f"   (Original columns in CSV: {list(df.columns)})")

        # 3. Normalize column names (Overwrite headers)
        # Force column names to standard snake_case for easier SQL queries
        if df.shape[1] == len(target_columns):
            df.columns = target_columns
            print("✅ Normalized column names to database schema.")
        else:
            print(f"⚠️ Warning: Column counts do not match. Keeping original columns from CSV.")

        # 4. Clean data (Deduplication)
        # Remove duplicates based on Match ID and Riot ID
        keys_to_check = ['match_id', 'riot_id']
        
        if set(keys_to_check).issubset(df.columns):
            before = len(df)
            df.drop_duplicates(subset=keys_to_check, keep='first', inplace=True)
            after = len(df)
            print(f"🧹 Removed {before - after} duplicate rows.")
        
        # 5. Save to SQLite
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        
        df.to_sql("matches_raw", conn, if_exists="replace", index=False)
        
        print(f"✅ SUCCESS: Saved {len(df)} rows to table 'matches_raw'.")
        
        conn.close()
        response.close()
        response.release_conn()
        
    except Exception as e:
        print(f"❌ Data processing error: {e}")

if __name__ == "__main__":
    # Run process
    if os.path.exists(LOCAL_CSV_PATH):
        uploaded_file = step_1_upload_csv_to_datalake()
        if uploaded_file:
            step_2_transform_and_load_db(uploaded_file)
    else:
        print(f"❌ File not found: {LOCAL_CSV_PATH}")