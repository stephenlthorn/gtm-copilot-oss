# Deploying GTM Copilot

## Production: AWS EC2 (Primary)

The live environment runs on a single EC2 `t4g.small` (ARM64, Amazon Linux 2023) with an Elastic IP. HTTPS is handled by Caddy using [sslip.io](https://sslip.io) — no domain purchase required.

### Architecture

```
Internet → Caddy (443/8443) → Docker network
                               ├── ui:3000    (Next.js)
                               ├── api:8000   (FastAPI)
                               ├── worker     (Celery)
                               ├── beat       (Celery Beat)
                               └── redis:6379
```

### First-Time EC2 Bootstrap

```bash
# 1. Install Docker
sudo yum install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user

# 2. Install Docker Compose plugin
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-aarch64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# 3. Clone repo
cd ~
git clone https://github.com/stephenlthorn/gtm-copilot-oss.git app
cd app

# 4. Create env file
cp infra/aws/.env.example infra/aws/.env
# Edit infra/aws/.env — see Configuration section below

# 5. Open ports in Security Group: 80, 443, 8443 (inbound from 0.0.0.0/0)

# 6. Start services
docker compose -f infra/aws/docker-compose.prod.yml up -d

# 7. Run migrations (first time only)
docker compose -f infra/aws/docker-compose.prod.yml exec api alembic upgrade heads
```

### Configuration (`infra/aws/.env`)

```bash
# Domain (free HTTPS via sslip.io — replace IP with your Elastic IP)
DOMAIN=100.49.55.13.sslip.io

# Database (TiDB Cloud)
DATABASE_URL=postgresql+psycopg://user:pass@host:4000/gtm_copilot?ssl_ca=/etc/ssl/certs/ca-certificates.crt

# Auth
ALLOWED_EMAIL_DOMAIN=yourcompany.com
GOOGLE_CLIENT_ID=<Google OAuth client ID>
GOOGLE_CLIENT_SECRET=<Google OAuth client secret — use the Drive client secret>

# Next.js
NEXT_PUBLIC_APP_URL=https://100.49.55.13.sslip.io
API_BASE_URL=http://api:8000

# Security
SECURITY_TRUSTED_HOST_ALLOWLIST=100.49.55.13.sslip.io,localhost,api

# Optional connectors
FIRECRAWL_API_KEY=
ZOOMINFO_API_KEY=          # Leave blank — reps auth individually via Settings UI
OPENAI_API_KEY=            # Set here OR reps provide their own via Settings
```

### Google OAuth Setup

In [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → Credentials → your OAuth client:

**Authorized redirect URIs:**
```
https://100.49.55.13.sslip.io/api/auth/exchange
```

> **Important:** Use the **Drive** OAuth client secret (starts `GOCSPX-cJow...`), not the ChatGPT/other secrets.

### Auto-Deploy via GitHub Actions

Every push to `main` auto-deploys. Add these secrets to your GitHub repo (Settings → Secrets → Actions):

| Secret | Value |
|--------|-------|
| `EC2_HOST` | `100.49.55.13` |
| `EC2_USER` | `ec2-user` |
| `EC2_SSH_KEY` | Full contents of your `.pem` key file |

Workflow: `.github/workflows/deploy.yml` — SSHes to EC2, runs `git pull`, rebuilds `ui` and `api` containers.

### Manual Deploy

```bash
ssh ec2-user@100.49.55.13
cd ~/app
git pull
docker compose -f infra/aws/docker-compose.prod.yml up -d --build ui api
```

> **Note:** Always use `up -d` (not `restart`) to pick up `.env` changes.

### Troubleshooting

```bash
# View logs
docker compose -f infra/aws/docker-compose.prod.yml logs -f api
docker compose -f infra/aws/docker-compose.prod.yml logs -f ui

# Rebuild single service
docker compose -f infra/aws/docker-compose.prod.yml up -d --build api

# Re-run migrations (after schema changes)
docker compose -f infra/aws/docker-compose.prod.yml exec api alembic upgrade heads

# Check container status
docker compose -f infra/aws/docker-compose.prod.yml ps
```

---

## Alternative: Railway

Railway works well for teams without an AWS account. Supports free tier.

### Prerequisites
- Railway account at railway.app
- GitHub repo connected to Railway
- Google OAuth credentials

### Services to Deploy

| Service | Root Directory | Start Command |
|---------|---------------|---------------|
| API | `api/` | `alembic upgrade heads && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Worker | `api/` | `celery -A app.worker.celery_app worker --loglevel=info` |
| Beat | `api/` | `celery -A app.worker.celery_app beat --loglevel=info` |
| UI | `ui/` | `npm start` |

Add PostgreSQL and Redis databases via Railway's database templates.

### Railway Environment Variables

**API / Worker / Beat:**
```
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
ALLOWED_EMAIL_DOMAIN=yourcompany.com
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

**UI:**
```
NEXT_PUBLIC_APP_URL=https://<ui-railway-domain>
API_BASE_URL=https://<api-railway-domain>
ALLOWED_EMAIL_DOMAIN=yourcompany.com
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

**OAuth redirect URI:** `https://<ui-railway-domain>/api/auth/exchange`
