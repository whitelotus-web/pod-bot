# POD Bot — Auto Keyword → AI Design → Mockup → Đăng bán

Hệ thống full-stack tự động hoá pipeline Print-on-Demand. Triết lý: **"ngon bổ rẻ"** — chỉ
hỗ trợ những platform có API thật, đáng tin, dễ mở rộng.

```
 ┌──────────────────────────────────────────────────────────┐
 │ Google Trends · Etsy · Amazon BSR · Pinterest · TikTok   │
 └──────────────────────────┬───────────────────────────────┘
                            ▼
                 [ Keyword Aggregator ]
                            │  (tổng hợp + xếp hạng)
                            ▼
            [ AI Designer ] · Gemini / DALL·E / SDXL
                            │
                            ▼
            [ Mockup Maker ] · Pillow + Printify
                            │
                            ▼
   [ Publisher ]   Printify (core) → auto-sync sang Etsy
                   Printful (premium tier)
```

## ✨ Vì sao chỉ 3 platform?

| Platform | Vì sao chọn |
|---|---|
| **Printify** | Free, API tốt nhất, mockup miễn phí, auto-sync sang Etsy/Shopify/eBay |
| **Printful** | Chất lượng cao cấp, fulfillment nhanh, API ổn định |
| **Etsy** | 95M người mua/tháng, OAuth 2.0 chính chủ |

❌ Bỏ Redbubble / Teespring / Merch by Amazon vì **không có public API** — Selenium dễ bị ban,
DOM thay đổi liên tục, ROI thấp.

## 🚀 Quickstart 15 phút

```bash
git clone https://github.com/whitelotus-web/pod-bot.git && cd pod-bot
cp .env.example .env
# Mở .env, điền tối thiểu:
#   GEMINI_API_KEY=...        (https://aistudio.google.com/apikey)
#   PRINTIFY_API_KEY=...      (https://printify.com/app/account/api)
docker compose up -d --build
```

| Service | URL |
|---|---|
| Dashboard | http://localhost:3000 |
| API + Swagger | http://localhost:8000/docs |
| Postgres | `localhost:5432` (`podbot` / `podbot`) |
| Redis | `localhost:6379` |

Đăng nhập admin: `admin@podbot.local` / `admin123` (đổi trong `.env`).

## 🔑 Kết nối Printify (hướng dẫn từng bước)

1. Vào https://printify.com/app/account/api → **Create new token** (chọn scope full).
2. Vào https://printify.com/app/store → copy **Shop ID** (số trong URL).
3. Trong dashboard POD Bot, mở `/platforms` → form **Thêm tài khoản mới**:
   - Platform: `Printify`
   - API key: token vừa tạo
   - Shop ID: số shop
4. Bấm **Test** — phải hiện ✅ Kết nối OK.
5. (Khuyến nghị) Vào Printify dashboard → **Add new sales channel** → kết nối Etsy shop.
   Từ giờ mỗi sản phẩm bot tạo trên Printify sẽ tự động xuất hiện trên Etsy.

## 🧠 Tạo chiến dịch đầu tiên

1. `/campaigns/new`:
   - **Tên**: `Cat lovers vintage tee`
   - **Niche**: `cat lovers`
   - **Style prompt**: `vintage retro cartoon, bold outline, 4 color palette`
   - **Nguồn keyword**: Google Trends + Etsy
   - **AI engine**: Gemini
   - **Số design / keyword**: 2
   - **Platform**: Printify
   - **Chế độ**: `semi` (an toàn — duyệt rồi mới đăng)
2. Bấm **Tạo** → bấm ▶ để chạy ngay.
3. Pipeline mất ~2-3 phút (tuỳ AI quota).
4. Vào `/designs` để xem ảnh & mockup; vào `/products` để xem sản phẩm đã đăng.

Khi đã tin tưởng pipeline, đổi `auto_mode` sang `full` và đặt cron `0 3 * * *` — bot tự đăng
mỗi sáng 3h.

## 🧱 Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 14 · TypeScript · Tailwind · shadcn-style UI |
| Backend | FastAPI 0.110 · SQLAlchemy 2 · Alembic · Pydantic 2 |
| Worker | Celery 5 · Redis 7 · Celery Beat |
| DB | PostgreSQL 16 |
| AI | google-genai · openai · replicate (plug-in qua factory) |
| Deploy | Docker Compose (6 services) |

## 🧩 Mở rộng

**Thêm nguồn keyword**: tạo class kế thừa `KeywordSource` trong
`backend/app/services/keywords/` → đăng ký vào `SOURCE_REGISTRY`.

**Thêm AI engine**: tạo class kế thừa `AIDesignEngine` trong
`backend/app/services/ai/` → đăng ký vào `get_engine()`.

**Thêm platform POD**: tạo class kế thừa `PODPlatform` trong
`backend/app/services/platforms/` → đăng ký vào `base.get_platform()` + `PLATFORM_META`.

Tất cả là plugin thuần — không cần sửa core pipeline.

## 🛠️ Lệnh hữu ích

```bash
docker compose logs -f backend worker          # tail logs
docker compose exec backend alembic upgrade head
docker compose exec backend pytest             # smoke tests
docker compose exec backend ruff check .       # lint
docker compose exec frontend npm run lint
docker compose exec frontend npm run build
```

Chạy thủ công 1 chiến dịch (không chờ cron):

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@podbot.local","password":"admin123"}' | jq -r .access_token)

curl -X POST http://localhost:8000/v1/campaigns/1/run \
  -H "Authorization: Bearer $TOKEN"
```

## 🔒 Bảo mật

- Không commit `.env` (đã có trong `.gitignore`).
- API key được mã hoá ở rest qua Postgres user (đổi password mặc định khi deploy).
- Mỗi platform account scope theo `user_id` — không chia sẻ giữa users.

## 📋 Roadmap gợi ý

- [ ] Plug-in Pinterest API (Trial program)
- [ ] AI quality filter — auto reject design xấu trước khi publish
- [ ] A/B test nhiều style prompt cùng 1 keyword
- [ ] Webhook nhận đơn hàng từ Printify → tự kích hoạt re-design
- [ ] Multi-tenant (mỗi user 1 isolated workspace)

## 📝 Giấy phép

MIT — dùng tự do, fork tự do.
