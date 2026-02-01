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

# Đường dẫn file
LOCAL_CSV_PATH = "data/raw/tft_matches_vn2_top150.csv"
DB_PATH = "data/processed/tft_data.db"

# Khởi tạo MinIO Client
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS,
    secret_key=MINIO_SECRET,
    secure=False
)

def step_1_upload_csv_to_datalake():
    """Upload file CSV gốc lên MinIO để lưu trữ (Backup)"""
    print("--- STEP 1: UPLOAD TO DATA LAKE ---")
    
    # Kiểm tra bucket
    if not minio_client.bucket_exists(BUCKET_NAME):
        minio_client.make_bucket(BUCKET_NAME)
    
    file_name = os.path.basename(LOCAL_CSV_PATH)
    
    try:
        minio_client.fput_object(
            BUCKET_NAME,
            file_name,
            LOCAL_CSV_PATH,
        )
        print(f"✅ Đã upload '{file_name}' lên MinIO bucket '{BUCKET_NAME}'.")
        return file_name
    except Exception as e:
        print(f"❌ Lỗi upload: {e}")
        return None

def step_2_transform_and_load_db(minio_file_name):
    """Đọc từ MinIO -> Pandas -> SQLite"""
    print("\n--- STEP 2: TRANSFORM & LOAD TO DB ---")
    
    try:
        # 1. Đọc file từ MinIO (Không đọc local để đúng quy trình Data Lake)
        print(f"📥 Đang đọc '{minio_file_name}' từ MinIO...")
        response = minio_client.get_object(BUCKET_NAME, minio_file_name)
        csv_bytes = response.read()
        
        # 2. Load vào Pandas
        df = pd.read_csv(io.BytesIO(csv_bytes))
        print(f"📊 Dữ liệu gốc: {df.shape[0]} dòng, {df.shape[1]} cột.")
        
        # --- DATA CLEANING (Tuỳ chỉnh theo data của bạn) ---
        # Ví dụ: Xóa các dòng bị trùng lặp dựa trên match_id và player
        if 'match_id' in df.columns:
            df.drop_duplicates(subset=['match_id', 'puuid'], keep='first', inplace=True)
        
        # Đổi tên cột cho chuẩn SQL (viết thường, không dấu cách)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        
        # 3. Lưu vào SQLite
        # Tạo thư mục nếu chưa có
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        conn = sqlite3.connect(DB_PATH)
        
        # 'replace': Ghi đè bảng cũ, 'append': nối thêm
        df.to_sql("matches_raw", conn, if_exists="replace", index=False)
        
        print(f"✅ Đã lưu {len(df)} dòng vào bảng 'matches_raw' trong SQLite.")
        print(f"📂 Database path: {DB_PATH}")
        
        conn.close()
        response.close()
        response.release_conn()
        
    except Exception as e:
        print(f"❌ Lỗi xử lý dữ liệu: {e}")

if __name__ == "__main__":
    # Chạy quy trình
    if os.path.exists(LOCAL_CSV_PATH):
        uploaded_file = step_1_upload_csv_to_datalake()
        if uploaded_file:
            step_2_transform_and_load_db(uploaded_file)
    else:
        print(f"❌ Không tìm thấy file: {LOCAL_CSV_PATH}")