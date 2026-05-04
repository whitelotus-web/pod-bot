# POD Bot — Hướng dẫn sử dụng

Tài liệu này dành cho **người dùng cuối** (chủ shop). Mỗi mục giải thích "page làm gì" + "khi nào dùng" + "cấu hình tối thiểu".

## Mục lục

1. [Quick start 30 phút](#1-quick-start-30-phút)
2. [13 trang UI giải thích từng cái](#2-13-trang-ui-giải-thích-từng-cái)
3. [Workflow theo ngày / tuần / tháng](#3-workflow-theo-ngày--tuần--tháng)
4. [Cấu hình tối thiểu](#4-cấu-hình-tối-thiểu)
5. [Troubleshooting](#5-troubleshooting)

---

## 1) Quick start 30 phút

Mục tiêu: từ login → có 1 listing đầu trên Etsy/Printify (sandbox được).

```
B1. Đăng nhập admin@podbot.io / admin123 (default seeder)
B2. /settings/ai → thêm Gemini API key (role=image)
B3. /platforms → thêm Printify account (paste API token + shop ID)
B4. /trademark → thêm các brand riêng anh muốn chặn (optional)
B5. /campaigns → "Tạo chiến dịch":
     • Niche: "cat lovers"
     • Keyword seeds: "vintage cat mom"
     • Product types: tick "tshirt_unisex"
     • Auto mode: "Bán tự động" (semi-auto)
     • Target shops: chọn shop vừa add
     • Save & Run
B6. /runs → theo dõi pipeline qua từng stage:
     keyword_scout → trademark_filter → ai_generate → quality_gate
     → bg_remove → upscale → mockup → seo → publish
B7. /designs → xem ảnh AI sinh ra; nếu để semi-auto, bấm "Duyệt"
B8. /products → listing đầu tiên, link Etsy/Printify
```

Thời gian thực tế: 5–8 phút setup + 15–20 phút chạy pipeline.

---

## 2) 13 trang UI giải thích từng cái

### `/dashboard`
**Mục đích**: tổng quan số. Designs hôm nay / tuần, run logs gần nhất, alert critical.

**Khi nào dùng**: vào mỗi sáng để check shop tối qua chạy thế nào.

### `/campaigns`
**Mục đích**: master config — niche, keyword seed, product types, target shops, schedule (cron), auto mode (full / semi / draft).

**Khi nào dùng**:
- Lần đầu setup 1 niche mới (ví dụ "plant moms").
- Khi cần đổi product types (thêm hoodie, mug…).
- Khi muốn tạm dừng campaign (toggle is_active).

**Mẹo**: 1 niche = 1 campaign. Đừng gộp "cat lovers + plant moms" vào 1 campaign vì keyword scout sẽ loãng.

### `/keywords`
**Mục đích**: kho keyword scout từ Google Trends + Etsy bestsellers + Pinterest + Amazon Merch + TikTok Creative Center. Hệ thống chấm điểm `score` (volume × intent / competition) và đo `momentum` (SMA-7 vs SMA-30).

**Khi nào dùng**:
- Trước khi launch campaign mới: anh review keyword pool, archive bad ones, mark "starred" cho bot ưu tiên.
- Hàng tuần: xem keyword nào đang break-out (momentum tag "rising 🚀").

**Mẹo**: keyword có badge "trademark risk" tự động bị skip khi sinh design — không cần xoá.

### `/designs`
**Mục đích**: thư viện ảnh AI sinh ra (transparent PNG). Filter theo campaign / status / quality gate.

**Khi nào dùng**:
- Mỗi ngày 1 lần (nếu chạy semi-auto): duyệt design qua nút "Approve". Design fail quality gate hiện badge đỏ kèm lý do (sharpness <80, OCR mismatch, palette quá tối...).
- Khi muốn regenerate 1 design cụ thể (nút "Sinh lại").

### `/products`
**Mục đích**: listing đã publish lên Etsy/Printify. Cột: status, views, clicks, CTR, orders, revenue, lifecycle stage.

**Khi nào dùng**:
- Hàng tuần để xem listing nào hot.
- Lifecycle audit chạy 12:00 UTC mỗi ngày → product có `lifecycle_stage="cut_loss_recommended"` hoặc `="winner"` xuất hiện ở đây để anh bấm "Cut" hoặc "Duplicate 5 variants".

### `/platforms`
**Mục đích**: quản lý multi-shop. Mỗi PlatformAccount = 1 cặp (provider, shop). Cột: api_token, shop_id, proxy_url (optional), warmup tier, fingerprint hash.

**Khi nào dùng**:
- Lần đầu setup shop.
- Khi mua thêm residential proxy (~$3-5/tháng/account) — paste vào `proxy_url`.
- Khi shop bị Etsy review → chuyển `health_status = paused`.

**Quan trọng**: mỗi shop phải có proxy riêng nếu chạy ≥3 shop trên cùng VPS, tránh bị Etsy link và ban hàng loạt.

### `/templates` (Prompt Templates)
**Mục đích**: 20 art-school templates (Wes Anderson, Bauhaus, Ukiyo-e, Ernst Haeckel...) — preview prompt sau khi điền niche+keyword.

**Khi nào dùng**:
- Khám phá style mới cho campaign tiếp theo (ví dụ test "Soviet Constructivist" cho niche kỳ lạ).
- Copy prompt sang campaign config.

### `/trademark` (Trademark Shield)
**Mục đích**: 3 lớp lọc bản quyền: substring marker (©®™) → builtin 120+ brand → user blacklist → optional USPTO TESS API.

**Khi nào dùng**:
- Setup ban đầu: paste vào blacklist các brand riêng anh quan tâm (ví dụ trademark trong VN, các quote nổi tiếng).
- Khi nhận alert "trademark hit" qua Telegram → vào đây thêm phrase đó để chặn vĩnh viễn.

**Test nhanh**: gõ "Star Wars cat shirt" → red banner. "vintage botanical illustration" → green safe.

### `/health` (Account Health & Warm-up)
**Mục đích**: dashboard tình trạng từng shop. Mỗi card hiển thị:
- Tier (week_1 / week_2 / month_1 / mature)
- Daily cap (3 / 5 / 8 / 12 / 18) + `Hôm nay: X / cap`
- Health badge (healthy / warn / paused)
- Proxy + last publish time

**Khi nào dùng**:
- Mỗi sáng: kiểm tra cap còn lại trước khi trigger campaign.
- Khi shop bị warn: vào đây + Telegram để diagnose.

**Tier ladder mặc định**:
| Account age | Tier | Daily cap |
|---|---|---|
| 0-7 ngày | week_1 | 3 |
| 8-14 | week_2 | 5 |
| 15-28 | weeks_3_4 | 8 |
| 29-60 | month_2 | 12 |
| 60+ | mature | 18 |

### `/notifications` (Thông báo)
**Mục đích**: log sự kiện hệ thống — trademark hit, hết quota AI, account paused, sale đầu tiên, lifecycle audit.

**Filter**: Tất cả / Chưa đọc.

**Khi nào dùng**:
- Lần đầu mỗi ngày, replace việc check email.
- Mỗi sáng review notif severity = `critical` (red).

### `/settings/ai` (AI Keys)
**Mục đích**: quản lý API key per-role. 3 role: `image` (Gemini Flash Image / DALL-E / Replicate), `seo` (Gemini Pro / GPT-4), `keyword_expansion` (Gemini Pro / GPT-4). Mỗi role có nhiều key fallback theo quota.

**Khi nào dùng**:
- Setup ban đầu — bắt buộc tối thiểu 1 key role=`image` để chạy được pipeline.
- Khi hết quota: thêm key thứ 2 cho role đó, hệ thống auto failover.

**Cost reference** (ước tính):
- Gemini Flash Image: ~$0.04/ảnh
- Gemini Pro (SEO + keyword): free tier 1500 req/ngày
- Replicate Real-ESRGAN upscale: ~$0.0023/ảnh

### `/runs` (Run logs)
**Mục đích**: log từng pipeline run, từng stage (keyword_scout → publish), success/error, duration.

**Khi nào dùng**:
- Khi 1 design bị "stuck", trace stage nào fail.
- Debug khi đổi config mà thấy hành vi lạ.

### `/settings`
**Mục đích**: chung — đổi mật khẩu, ngôn ngữ UI, default branch (light/dark mode).

---

## 3) Workflow theo ngày / tuần / tháng

### Hằng ngày (5 phút sáng + 5 phút tối)

| Giờ | Việc | Page |
|---|---|---|
| 09:00 | Mở `/notifications`, đọc severity ≥ warn | `/notifications` |
| 09:05 | Check `/health`, đảm bảo không có shop nào `paused` | `/health` |
| 09:10 | Nếu có design semi-auto chờ duyệt → vào `/designs` | `/designs` |
| 21:00 | Review `/dashboard`, xem hôm nay sale được mấy | `/dashboard` |

### Hằng tuần (30 phút thứ 2)

| Việc | Page |
|---|---|
| Review `/products` filter `lifecycle_stage=winner` → bấm "Duplicate 5 variants" cho top 3 | `/products` |
| Review `lifecycle_stage=cut_loss_recommended` → cut những cái không có khả năng cứu | `/products` |
| Xem `/keywords` filter momentum tag `rising` → starred những keyword phù hợp niche | `/keywords` |
| Adjust pricing rules (`/pricing` UI hoặc DB) | `/pricing` |

### Hằng tháng (1 giờ)

| Việc |
|---|
| Audit `/health` xem account nào sắp lên tier mới — adjust cap nếu muốn nhanh |
| Backup postgres (cron task auto) — verify dump tồn tại trên S3 |
| Review tổng doanh thu vs cost AI key + proxy + VPS |
| Xoá design fail quality gate >7 ngày để tiết kiệm storage |

### Auto schedule (Celery beat)

| Task | Khi chạy | Mô tả |
|---|---|---|
| `tick` (campaign scheduler) | mỗi 5 phút | Check campaign nào đến giờ chạy |
| `keyword_scout` | 02:00 UTC | Scout 5 nguồn keyword |
| `lifecycle_audit` | 12:00 UTC | Đánh giá CTR/orders 30 ngày, recommend cut/duplicate |
| `account_health_sweep` | mỗi giờ :15 | Reset paused account hết hạn |
| `pricing_evaluator` | 04:00 UTC thứ 7 | Apply weekend flash sale |
| `pricing_revert` | 04:00 UTC thứ 2 | Revert về giá gốc |

---

## 4) Cấu hình tối thiểu

### Bắt buộc (không có thì không chạy)

| Env var / config | Đặt ở đâu | Lấy ở đâu |
|---|---|---|
| `GEMINI_API_KEY` (role=image) | `/settings/ai` | https://aistudio.google.com/app/apikey |
| Etsy hoặc Printify account | `/platforms` | Etsy: OAuth flow trong UI. Printify: https://printify.com/app/account/api |
| Postgres + Redis | `docker-compose.yml` | Local container |

### Optional (đáng đầu tư)

| Tính năng | Cost | Setup |
|---|---|---|
| Telegram bot remote | Free | Tạo bot qua @BotFather, paste token vào `.env` `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` |
| USPTO TESS check | Free | Đăng ký https://developer.uspto.gov/ → paste `USPTO_TESS_API_KEY` |
| Replicate upscaler | $0.0023/ảnh | https://replicate.com/account/api-tokens → `REPLICATE_API_TOKEN` |
| Residential proxy | ~$3-5/shop/tháng | SmartProxy / IPRoyal → paste vào `/platforms` per shop |
| OpenAI fallback | Pay-as-you-go | https://platform.openai.com/api-keys → `/settings/ai` role=image |

### Cloud deploy (bắt buộc cho production)

Xem `docs/deploy.md` (hướng dẫn deploy lên Ubuntu VPS với systemd + Caddy reverse proxy + auto HTTPS + postgres backup).

Min VPS spec: 2 vCPU / 4GB RAM / 40GB SSD (~$10-12/tháng Hetzner CX21).

---

## 5) Troubleshooting

### "Không có design nào sinh ra"
1. `/runs` xem stage `ai_generate` có error gì.
2. `/settings/ai` check key role=image còn quota không (badge `quota_exhausted`).
3. Add key thứ 2 → auto failover.

### "Shop bị Etsy warn / paused"
1. `/health` check shop có badge `warn`.
2. Vào `/notifications` đọc lý do.
3. Thường do publish quá nhanh → giảm `daily_publish_cap_override` về 50% tier hiện tại.
4. Nếu paused → đợi 24h, hệ thống auto retry.

### "Trademark hit liên tục"
1. `/notifications` xem keyword nào dính.
2. `/keywords` archive keyword đó.
3. `/trademark` thêm phrase vào blacklist nội bộ → block vĩnh viễn.

### "Design AI có chữ sai chính tả"
- Hệ thống `/quality.py` gate `ocr_text_match` đã reject — vào `/designs` xem badge fail.
- Nếu vẫn lọt qua: vào `/settings/ai` thêm `negative prompt` chặn text artifacts.

### "Pipeline stuck giữa chừng"
1. `/runs` filter `status=running` >10 phút.
2. SSH vào VPS: `docker compose logs worker --tail=100`.
3. Restart worker: `docker compose restart worker`.

### "Listing in ra mờ trên áo"
- Upscaler chưa hoạt động. Check `Design.upscaled_path` trong DB.
- Setup `REPLICATE_API_TOKEN` để dùng Real-ESRGAN qua API (recommend) hoặc `UPSCALE_BACKEND=pil_lanczos` (fallback miễn phí, kém hơn).

### "Telegram không nhận thông báo"
- Verify `.env` có `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`.
- Test: `docker compose exec backend python -c "from app.services.telegram_bot import send; send('test', severity='info')"`.

### "CTR thấp, không có sale"
- Xem `/keywords`: keyword đang dùng có volume thấp / competition cao? Switch sang keyword `momentum=rising`.
- Xem `/products`: listing có review 5 sao nào chưa? Nhờ bạn bè mua thật, để 1-2 review đầu (Etsy thuật toán cần social proof).
- Xem `/templates`: thử style mới (Bauhaus / Soviet Constructivist) thay vì AI generic.
- Pricing có hợp lý không? `/pricing` rules tự bump hoặc giảm — anh override được.

### "Hết quota AI giữa lúc đang chạy"
- Hệ thống auto failover sang key thứ 2 cùng role. Nếu chỉ có 1 key → pipeline pause + notif `quota_exhausted`.
- Add key thứ 2 ngay, pipeline tiếp tục từ chỗ dừng (idempotent).

---

## Liên hệ / phản hồi

- Bug report: mở GitHub issue
- Tính năng mới: mở Discussion
- Critical incident (shop bị bay): xem trace ở `/runs` + `/notifications`, gửi log cho Devin
