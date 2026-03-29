# ♟️ TFT Match History Analysis & Strategy Optimization

> **Project ID:** ADY201m
> **Topic:** Phân tích dữ liệu lịch sử đấu Teamfight Tactics (Riot Games API)

## 📖 Giới thiệu (Overview)
Dự án xây dựng hệ thống Data Pipeline mô phỏng quy trình doanh nghiệp để thu thập, lưu trữ và phân tích dữ liệu trận đấu TFT. Hệ thống tự động Crawl dữ liệu từ Riot API, lưu trữ Raw Data vào Data Lake (MinIO), làm sạch và chuyển đổi vào Data Warehouse (SQLite/PostgreSQL) để phân tích chiến thuật.

**Mục tiêu chính:**
1.  Xác định **Top 5 Champion Carry** hiệu quả nhất dựa trên trang bị và thứ hạng.
2.  So sánh tỷ lệ thắng (Win Rate) giữa hai lối chơi phổ biến: **Reroll** và **Fast Level**.

---

## 👥 Thành viên thực hiện (Team Members)

| STT | Họ và Tên | Mã Sinh Viên |
|:---:|:---|:---|
| 01 | **Nguyễn Trung Hiếu** | QE200041 |
| 02 | **Lê Gia Bảo** | QE200316 |

---

## 🏗️ Kiến trúc hệ thống (Architecture)
Dự án được container hóa hoàn toàn bằng Docker Compose:

1.  **Ingestion:** Python Script crawl dữ liệu JSON từ Riot API.
2.  **Storage (Data Lake):** **MinIO** (S3 Compatible) lưu trữ dữ liệu thô.
3.  **Processing:** Làm sạch dữ liệu, xử lý logic (Nhận diện Carry, Phân loại Reroll/Fast8).
4.  **Warehousing:** **SQLite** lưu trữ dữ liệu có cấu trúc (hoặc PostgreSQL tùy cấu hình).
5.  **Analysis:** Jupyter Notebook kết nối DB để trực quan hóa và kiểm định giả thuyết.

---

## 📂 Cấu trúc dự án (Project Structure)
Tuân thủ quy định môn học:

```text
ADY201m/
│
├── .gitignore               # Ignored: .env, __pycache__, data/raw/*
├── README.md                # Documentation
├── AI_Log.md                # Generative AI Prompt Logs
├── docker-compose.yml       # Infrastructure Setup
├── requirements.txt         # Python Dependencies
│
├── configs/                 # Configuration files
├── docker/                  # Dockerfiles
├── data/                    # Sample Data (No large files committed)
│   ├── raw/                 # Nơi chứa file CSV/JSON thô
│   └── processed/           # Nơi chứa Database sau xử lý
│
├── src/                     # Source Code
│   ├── ingestion/           # Riot API Crawler (Jupyter Notebooks)
│   ├── processing/          # ETL & Cleaning Logic
│   └── modeling/            # Analysis Logic
│
├── notebooks/               # Analysis & Visualization (EDA)
└── reports/                 # Reports & Images
```

---

## 🚀 Hướng dẫn Cài đặt & Chạy (Installation & Usage)

Để chạy dự án này, bạn cần cài đặt sẵn **Docker Desktop** và **Git**.

### 1. Clone dự án

```bash
git clone https://github.com/WHT413/ADY201m
cd ADY201m
```

### 2. Cấu hình biến môi trường (.env)

Dự án sử dụng file `.env` để bảo mật API Key và Database Credentials.
Tạo file `.env` tại thư mục gốc và điền nội dung sau:

```ini
# --- MinIO Configuration ---
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=password12345678  # Mật khẩu phải >= 8 ký tự
MINIO_ENDPOINT=minio:9000

# --- Riot Games API (Optional nếu chạy Crawler) ---
# Lấy key tại: https://developer.riotgames.com/
RIOT_API_KEY=RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### 3. Khởi chạy hệ thống (Docker)

**Lưu ý quan trọng:** Vui lòng mở ứng dụng **Docker Desktop** và chờ đến khi trạng thái hiển thị **"Engine Running"** trước khi thực thi lệnh bên dưới.

Dựng toàn bộ hạ tầng (MinIO, Python Environment) bằng Docker Compose:

```bash
docker-compose up -d --build
```

*Lệnh này sẽ tự động cài đặt các thư viện trong `requirements.txt` và khởi động các container.*

### 4. Kiểm tra trạng thái

Đảm bảo các services đều ở trạng thái `Up`:

```bash
docker ps
```

*   **MinIO Console:** Truy cập `http://localhost:9001` (User/Pass như trong file .env).

### 5. Chạy quy trình ETL

Chạy script ETL xử lý toàn bộ dữ liệu (JSON sang SQLite 3NF):

**Chạy bằng Conda Environment (Khuyên dùng)**
Trước khi chạy, bạn cần tạo môi trường Conda và cài đặt các dependencies từ `requirements.txt`:
```bash
# Tạo và kích hoạt môi trường conda
conda create -n tft_env python=3.10 -y
conda activate tft_env

# Cài đặt thư viện yêu cầu
pip install -r requirements.txt

# Chạy script ETL
python src/processing/etl_json.py
```

**Chạy bằng Docker (Nếu đã start container)**
```bash
docker exec -it tft_app python src/processing/etl_json.py
```

*Lưu ý: Quá trình thu thập dữ liệu (Crawl) hiện được chạy thông qua các file Jupyter Notebook trong thư mục `src/ingestion/`.*

### 6. Huấn luyện mô hình (Modeling)

Chạy pipeline phân lớp Logistic Regression và Random Forest (đầu vào từ database):

```bash
python src/modeling/model_comparison.py
```
*(Kết quả đánh giá và biểu đồ sẽ được tự động lưu trong thư mục `reports/imgs/`)*

### 7. Xem kết quả (Database)

Sau khi chạy ETL, file database sẽ được tạo tại:

*   **Đường dẫn:** `data/processed/tft_data.db`
*   **Cách xem:** Sử dụng Extension **SQLite Viewer** trên VS Code hoặc phần mềm **DB Browser for SQLite** để mở file này và truy vấn SQL.

---

### ⚠️ Troubleshooting (Sự cố thường gặp)

*   **Lỗi `minio refuses connection`:** Kiểm tra lại mật khẩu trong `.env`, MinIO yêu cầu mật khẩu tối thiểu 8 ký tự.
*   **Lỗi `ports are not available`:** Đảm bảo không có ứng dụng nào khác đang chạy chiếm cổng `9000`, `9001` hoặc `5432`.
*   **Clean & Reset:** Để xóa sạch dữ liệu và chạy lại từ đầu:
    ```bash
    docker-compose down -v
    docker-compose up -d --build
    ```