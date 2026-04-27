# Deployment Guide — POD Bot 24/7 trên Ubuntu VPS

Mục tiêu: stack Docker chạy ngầm 24/7, auto-restart khi reboot, có HTTPS,
backup DB hằng ngày, alert qua Telegram. Không phụ thuộc vào việc bật máy
tính cá nhân.

## 1. Provision VPS

### Khuyến nghị spec

| Provider | Plan | RAM | vCPU | Disk | Giá/tháng | Note |
|---|---|---|---|---|---|---|
| **Hetzner** | CPX21 | 4 GB | 3 | 80 GB | ~$8 | Recommended cho start. EU region. |
| **DigitalOcean** | s-2vcpu-4gb | 4 GB | 2 | 80 GB | $24 | NYC/SFO region. |
| **Vultr** | High Frequency 2GB | 2 GB | 1 | 64 GB | $12 | OK nếu chỉ chạy 1-2 shop. |

Nếu chạy **upscale local Real-ESRGAN**, cần GPU VPS:
- **RunPod** A40 / RTX 4090 on-demand ~$0.20-0.40/h (~$150/tháng nếu chạy 24/7)
- Hoặc giữ CPU VPS + dùng **Replicate API** ~$0.002/ảnh (rẻ hơn rất nhiều cho ≤10k ảnh/tháng).

### Ubuntu 22.04 LTS setup

```bash
# Bật ssh key only (sau khi đã set key)
sudo passwd -l root  # khóa root password login
sudo nano /etc/ssh/sshd_config   # PasswordAuthentication no
sudo systemctl reload ssh

# Firewall
sudo ufw allow OpenSSH
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable

# Auto security updates
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

## 2. Cài Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER  # logout/login lại để effect
```

## 3. Clone + cấu hình

```bash
sudo mkdir -p /srv/podbot && sudo chown $USER:$USER /srv/podbot
cd /srv/podbot
git clone https://github.com/whitelotus-web/pod-bot.git .
cp .env.example .env
nano .env       # set POSTGRES_PASSWORD, JWT_SECRET (≥32 char random),
                # GEMINI/OPENAI/REPLICATE keys, TELEGRAM_BOT_TOKEN,
                # TELEGRAM_CHAT_ID, USPTO_TESS_TOKEN (optional)
```

Random secrets:
```bash
openssl rand -hex 32   # JWT_SECRET
openssl rand -hex 16   # POSTGRES_PASSWORD
```

## 4. Reverse proxy + HTTPS (Caddy)

Caddy auto-renews Let's Encrypt cert.

```bash
sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update && sudo apt-get install -y caddy
```

`/etc/caddy/Caddyfile`:
```caddy
podbot.yourdomain.com {
    reverse_proxy /api/* localhost:8000
    reverse_proxy /media/* localhost:8000
    reverse_proxy /* localhost:3000
}
```

```bash
sudo systemctl reload caddy
```

DNS: trỏ A record `podbot.yourdomain.com` về IP VPS.

## 5. systemd auto-start

`/etc/systemd/system/podbot.service`:

```ini
[Unit]
Description=POD Bot Docker Compose stack
Requires=docker.service
After=docker.service network-online.target
StartLimitIntervalSec=0

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/srv/podbot
ExecStart=/usr/bin/docker compose up -d --build
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=600

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now podbot
```

VPS reboot → Docker khởi động → POD Bot tự up.

## 6. Migrate DB lần đầu

```bash
cd /srv/podbot
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.bootstrap_admin   # tạo admin
```

## 7. Backup PostgreSQL daily

`/srv/podbot/scripts/backup.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
TS=$(date -u +%Y%m%dT%H%M%SZ)
DEST=/srv/podbot/backups
mkdir -p "$DEST"
docker compose exec -T postgres pg_dump -U podbot podbot \
  | gzip > "$DEST/podbot-$TS.sql.gz"
# Keep last 14 days only.
find "$DEST" -name 'podbot-*.sql.gz' -mtime +14 -delete
```

```bash
chmod +x /srv/podbot/scripts/backup.sh
sudo crontab -e
# 0 3 * * * /srv/podbot/scripts/backup.sh >> /var/log/podbot-backup.log 2>&1
```

Nâng cao: dùng `rclone` push lên S3/B2/Drive để có off-site backup.

## 8. Celery beat schedule mặc định

Stack đã có sẵn 3 job định kỳ chạy trong container `pod-bot-beat-1`:

| Job | Cron | Mục đích |
|---|---|---|
| `check-scheduled-campaigns` | every 5 min | Phát hiện campaign nào đến giờ chạy theo cron user set, dispatch worker |
| `lifecycle-audit-daily` | 12:00 UTC | Quét product cũ → recommend cut-loss / duplicate winner + ping notification |
| `account-health-sweep-hourly` | mỗi giờ phút :15 | Reset paused account đã hết hạn |

User có thể set `Campaign.schedule_cron` ví dụ:
- `0 2 * * *` → 02:00 UTC mỗi ngày scout keyword + chạy pipeline campaign
- `0 6 * * 1-5` → 06:00 UTC thứ 2 đến thứ 6
- `0 */6 * * *` → mỗi 6 giờ

## 9. Telegram setup

1. BotFather → `/newbot` → copy token vào `TELEGRAM_BOT_TOKEN`
2. Mở chat với bot, gõ `/start`
3. `curl https://api.telegram.org/bot<TOKEN>/getUpdates` → đọc `chat.id` → set `TELEGRAM_CHAT_ID`
4. Restart backend: `docker compose restart backend worker beat`

Bot sẽ tự bắn alert khi:
- Trademark hit → ngăn chặn keyword nguy hiểm trước khi vẽ
- Hết quota AI key → fallback sang key khác / engine khác
- Account paused → cảnh báo Etsy có thể đang review
- Sale đầu tiên → 🎉 push ảnh + URL listing
- Lifecycle audit → tóm tắt cut-loss / duplicate

## 10. Monitoring (optional)

Stack mặc định chỉ ghi log vào Docker. Để có dashboard:
- **Uptime Kuma** (`docker run --restart=always louislam/uptime-kuma`) — ping `https://podbot.yourdomain.com/api/v1/healthz` mỗi phút.
- **Grafana + Loki** nếu muốn search log đầy đủ.

## 11. Rate limiting đề xuất

Đã có warm-up tier built-in (3/5/8/12/18 listing/ngày). Ngoài ra:

| Account age | Daily cap | Min spacing | Khuyến cáo |
|---|---|---|---|
| 0-7 days | 3 | 90s | Chỉ publish 1 shop, 1 design/giờ |
| 8-14 days | 5 | 60s | Mỗi shop độc lập proxy |
| 15-30 days | 8 | 45s | Có thể bật 2-3 shop |
| 31-60 days | 12 | 30s | OK nhiều shop |
| 61+ days | 18 | 30s | Steady state |

Override per-account qua UI `/health` hoặc DB:
```sql
UPDATE platform_accounts SET daily_publish_cap_override = 25 WHERE id = 1;
UPDATE platform_accounts SET account_age_days_override = 90 WHERE id = 2;
```

## 12. Multi-shop fingerprint

Nếu chạy ≥3 shop trên cùng VPS, BẮT BUỘC dùng residential proxy khác nhau:

| Provider | Plan | Giá |
|---|---|---|
| **SmartProxy** | Sticky session 10GB | $75/tháng |
| **IPRoyal** | Royal residential pay-as-go | $7/GB |
| **BrightData** | Residential static | $500/tháng (tier cao nhất) |

Cấu hình trong UI `/platforms` → mỗi account 1 `proxy_url`:
```
http://user-shop1:pass@proxy.smartproxy.com:7000
```

Stack tự gán per-account User-Agent (deterministic SHA256 của account_id),
cộng với proxy → Etsy không link được các shop với nhau.
