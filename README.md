# POD Bot — Tự động tìm keyword → AI design → mockup → đăng bán áo thun

Hệ thống tự động hoá pipeline Print-on-Demand:

```
 [ Google Trends / Etsy / Amazon / Pinterest / TikTok ]
                       │
                       ▼
            [ Keyword Aggregator ]  ← xếp hạng theo điểm số
                       │
                       ▼
  [ AI Designer ]  ← Gemini / DALL-E / SDXL (plug-in)
                       │
                       ▼
        [ Mockup Maker ]  ← Pillow compositor
                       │
                       ▼
 [ Publisher Adapters ]  ← Printify · Printful · Etsy · Redbubble · …
```

## ✨ Tính năng chính

- **Keyword Scout** — tổng hợp nhiều nguồn trend (Google Trends, Etsy, Amazon BSR, Pinterest, TikTok), chuẩn hoá điểm và xếp hạng.
- **AI Designer** — sinh design áo thun từ prompt được tối ưu cho POD (background trong suốt, không watermark, độ tương phản cao). Đổi engine chỉ cần dropdown: `Gemini` · `OpenAI DALL-E` · `Replicate (SDXL / Flux / …)`.
- **Mockup Maker** — ghép design lên template áo (đi kèm template mẫu vẽ bằng Pillow — thay bằng ảnh studio thật dễ dàng).
- **Auto Publisher** — adapter riêng cho từng platform. Đăng API thật cho **Printify**, **Printful**, **Etsy**; skeleton Selenium cho **Redbubble / Teespring / Merch by Amazon** (các platform này không có public API).
- **Campaign Manager** — mỗi chiến dịch có niche, style prompt, nguồn keyword, AI engine, platform đích, giá, cron. Chế độ `semi` (chờ bạn duyệt) hoặc `full` (đăng tự động).
- **Dashboard tiếng Việt** — Next.js 14 + Tailwind, tối ưu UX.
- **Docker Compose** — `docker compose up -d` là xong.

## 🧱 Kiến trúc

| Layer        | Tech                                          |
|--------------|-----------------------------------------------|
| Frontend     | Next.js 14, Tailwind, TypeScript, shadcn-ish UI |
| Backend API  | FastAPI (Python 3.12) + SQLAlchemy 2 + Alembic |
| Worker       | Celery + Redis, Celery Beat (cron scheduler)   |
| DB           | PostgreSQL 16                                  |
| Cache/queue  | Redis 7                                        |
| Storage      | Volume `media/` (designs, mockups)             |

## 🚀 Chạy nhanh (Docker Compose)

```bash
git clone <repo> pod-bot && cd pod-bot
cp .env.example .env
# Mở .env điền GEMINI_API_KEY (hoặc OPENAI/REPLICATE) + PRINTIFY_API_KEY, …
docker compose up -d --build
```

Các endpoint:

| Service     | URL                                       |
|-------------|-------------------------------------------|
| Dashboard   | http://localhost:3000                     |
| API         | http://localhost:8000                     |
| Swagger     | http://localhost:8000/docs                |
| Postgres    | `localhost:5432` (user/pass: `podbot`)    |
| Redis       | `localhost:6379`                          |

Tài khoản admin mặc định: `admin@podbot.local` / `admin123` (đổi trong `.env`).

## 🔑 Kết nối tài khoản platform

Vào `/platforms` trong dashboard rồi chọn:

### Printify
1. Lấy API key tại https://printify.com/app/account/api
2. Dán vào `api_key`; điền `shop_id` (xem `/v1/shops.json`).
3. Bấm **Test** để xác minh.

### Printful
1. Tạo API key tại https://developers.printful.com/
2. Dán vào `api_key`. Bấm **Test**.

### Etsy (OAuth 2.0)
1. Đăng ký app tại https://www.etsy.com/developers/your-apps
2. Điền `ETSY_CLIENT_ID`, `ETSY_CLIENT_SECRET` vào `.env`.
3. Trong dashboard, chọn **Etsy** rồi bấm **Kết nối Etsy qua OAuth →**.

### Redbubble / Teespring / Merch by Amazon
Các platform này **không có public API**. Adapter đi kèm là skeleton Selenium/Playwright. Để kích hoạt:

1. `pip install playwright && playwright install chromium`
2. Đăng nhập bằng browser profile riêng, export cookies thành JSON.
3. Lưu cookies vào `PlatformAccount.extra["cookies"]` (hiện đang để placeholder trong code — xem `backend/app/services/platforms/redbubble.py`).

⚠️ Tự động upload lên các platform này có thể vi phạm ToS. Dùng có trách nhiệm.

## 🧠 Tạo chiến dịch

1. Vào `/campaigns/new`.
2. Nhập niche (vd: `cat lovers`), style prompt, chọn nguồn keyword.
3. Chọn AI engine + số design / keyword.
4. Chọn platform đích + chế độ `semi` / `full`.
5. (tuỳ chọn) nhập cron `0 3 * * *` — mỗi 3h sáng chạy.
6. Bấm **Tạo**, rồi bấm ▶ để chạy ngay.

## 🧩 Thêm nguồn keyword / platform mới

**Thêm nguồn keyword**: tạo class kế thừa `KeywordSource` trong `backend/app/services/keywords/` rồi đăng ký vào `aggregator.SOURCE_REGISTRY`.

**Thêm platform**: tạo class kế thừa `PODPlatform` trong `backend/app/services/platforms/` rồi đăng ký vào `base.get_platform()` + `PLATFORM_META`.

Adapter pattern → thêm mới không cần sửa core pipeline.

## 🛠️ Lệnh hữu ích

```bash
# Tail logs
docker compose logs -f backend worker

# Re-run migrations
docker compose exec backend alembic upgrade head

# Vào shell Python của backend
docker compose exec backend python

# Chạy pipeline ngay (không chờ cron) bằng API
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/campaigns/1/run?force_auto=true"
```

## 🗂️ Cấu trúc repo

```
pod-bot/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry + admin seeder
│   │   ├── core/                # settings, db, security
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── api/v1/              # REST endpoints
│   │   ├── services/
│   │   │   ├── keywords/        # Google Trends, Etsy, Amazon, Pinterest, TikTok + aggregator
│   │   │   ├── ai/              # Gemini, OpenAI, Replicate
│   │   │   ├── mockup/          # Pillow compositor
│   │   │   └── platforms/       # Printify, Printful, Etsy, Redbubble, Teespring, Merch Amazon
│   │   └── workers/             # Celery app + pipeline task + beat scheduler
│   ├── alembic/                 # DB migrations
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── app/                     # Next.js 14 App Router (tiếng Việt)
│   │   ├── login/
│   │   └── (app)/
│   │       ├── dashboard/
│   │       ├── campaigns/ (+ new)
│   │       ├── keywords/
│   │       ├── designs/
│   │       ├── products/
│   │       ├── platforms/
│   │       ├── runs/
│   │       └── settings/
│   ├── components/Sidebar.tsx
│   ├── lib/api.ts
│   └── Dockerfile
```

## 🔒 Ghi chú bảo mật & ToS

- Không commit `.env` lên repo (đã gitignore).
- Scraping Etsy / Amazon có thể vi phạm ToS — rate-limit hoặc dùng proxy.
- Credentials platform được lưu plaintext trong DB — trong production, encrypt thêm bằng `cryptography.fernet` với key trong KMS.
- Chỉ đăng upload design bạn có bản quyền (tránh DMCA).

## 📜 License

MIT — tự do thương mại hoá.
