# ♟️ TFT Match History Analysis & Strategy Optimization

> **Project ID:** ADY201m
> **Topic:** Phân tích dữ liệu lịch sử đấu Teamfight Tactics (Riot Games API)

## 📖 Giới thiệu (Overview)
Dự án xây dựng hệ thống Data Pipeline mô phỏng doanh nghiệp để thu thập, lưu trữ và phân tích dữ liệu trận đấu TFT. Hệ thống tự động Crawl dữ liệu từ Riot API, lưu trữ Raw Data vào Data Lake (MinIO), làm sạch và chuyển đổi vào Data Warehouse (PostgreSQL) để phân tích chiến thuật.

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
4.  **Warehousing:** **SQLite** lưu trữ dữ liệu có cấu trúc.
5.  **Analysis:** Jupyter Notebook kết nối DB để trực quan hóa và kiểm định giả thuyết.

---

## 📂 Cấu trúc dự án (Project Structure)
Tuân thủ quy định môn học:

```text
Student_ID_Project_Name/
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
│
├── src/                     # Source Code
│   ├── ingestion/           # Riot API Crawler
│   ├── processing/          # ETL & Cleaning Logic
│   └── modeling/            # Analysis Logic
│
├── notebooks/               # Analysis & Visualization (EDA)
└── reports/                 # PDF Reports