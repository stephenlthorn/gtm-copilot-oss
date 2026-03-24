# Deploying GTM Copilot to Railway

## Architecture

```
Railway Project
├── UI          (Next.js, port $PORT)
├── API         (FastAPI, port $PORT)
├── Worker      (Celery worker)
├── Beat        (Celery beat scheduler)
└── Redis       (Railway plugin, internal networking)

External
└── TiDB Cloud  (database — already provisioned)
```

## Prerequisites

- Railway account at [railway.app](https://railway.app) (Hobby plan: $5/mo)
- GitHub repo connected to Railway
- Google OAuth app credentials (Google Cloud Console)
- TiDB Cloud Serverless cluster (already provisioned)
- OpenAI API key

## Step 1: Create Railway Project

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select `gtm-copilot-oss`
3. Railway will detect the repo — don't deploy yet, configure services first

## Step 2: Add Redis

In Railway dashboard:
- Click **+ New** → **Database** → **Redis**
- Railway provisions it automatically with internal networking

> **Note:** No PostgreSQL needed — we use TiDB Cloud as the database.

## Step 3: Create Services

Add **4 services** from the same repo. For each, click **+ New** → **GitHub Repo** → select `gtm-copilot-oss`:

### API Service
| Setting | Value |
|---------|-------|
| Name | `api` |
| Root Directory | `api` |
| Start Command | `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check | `GET /` returns `{"status":"ok"}` |

### Worker Service
| Setting | Value |
|---------|-------|
| Name | `worker` |
| Root Directory | `api` |
| Start Command | `celery -A app.worker.celery_app worker --loglevel=info --concurrency=2` |

### Beat Service
| Setting | Value |
|---------|-------|
| Name | `beat` |
| Root Directory | `api` |
| Start Command | `celery -A app.worker.celery_app beat --loglevel=info` |

### UI Service
| Setting | Value |
|---------|-------|
| Name | `ui` |
| Root Directory | `ui` |
| Start Command | `npm start` |

## Step 4: Set Environment Variables

### Shared Variables (API, Worker, Beat)

Set these on all three Python services. Use Railway's **Shared Variables** feature to avoid duplication.

```bash
# Database — TiDB Cloud connection string
DATABASE_URL=mysql+pymysql://<user>:<password>@<host>:4000/<database>?ssl_verify_cert=true&ssl_verify_identity=true

# Redis — Railway internal reference
REDIS_URL=${{Redis.REDIS_URL}}

# LLM
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1

# Auth
SECRET_KEY=<openssl rand -hex 32>
GOOGLE_CLIENT_ID=<from Google Cloud Console>
GOOGLE_CLIENT_SECRET=<from Google Cloud Console>

# CORS — must include the Railway UI domain
CORS_ALLOW_ORIGINS=https://<your-ui-domain>.up.railway.app

# Production settings
ENVIRONMENT=production
APP_ENV=production
LOG_LEVEL=INFO
AUTO_CREATE_SCHEMA=true

# Optional integrations
SENTRY_DSN=
FIRECRAWL_API_KEY=
SLACK_BOT_TOKEN=
CHORUS_API_KEY=
```

### UI Service Variables

```bash
# API connection — Railway internal networking (private, no egress cost)
API_BASE_URL=http://api.railway.internal:${{api.PORT}}

# Public URLs (Railway assigns these automatically)
NEXT_PUBLIC_APP_URL=https://<your-ui-domain>.up.railway.app
NEXT_PUBLIC_API_URL=https://<your-api-domain>.up.railway.app
NEXTAUTH_URL=https://<your-ui-domain>.up.railway.app
NEXTAUTH_SECRET=<openssl rand -hex 32>

# OAuth
GOOGLE_CLIENT_ID=<same as API>
GOOGLE_CLIENT_SECRET=<same as API>
```

> **Tip:** Use Railway's internal networking for UI → API calls (`http://api.railway.internal`).
> This is free (no egress charges) and faster than going through the public URL.

## Step 5: Configure Google OAuth

In Google Cloud Console → APIs & Services → Credentials → your OAuth app:

1. Add **Authorized redirect URI**: `https://<your-ui-domain>.up.railway.app/api/auth/exchange`
2. Add **Authorized JavaScript origin**: `https://<your-ui-domain>.up.railway.app`

## Step 6: Deploy

1. Push to the `railway` branch (or whichever branch Railway is configured to watch)
2. Railway auto-builds and deploys all 4 services
3. First deploy takes 3-5 minutes (builds Python + Node.js environments)

## Step 7: Verify

```bash
# API health check
curl https://<api-domain>.up.railway.app/
# → {"service":"GTM Copilot API","status":"ok"}

# UI loads
open https://<ui-domain>.up.railway.app

# Google login works
# Admin panel accessible at /admin
```

## Updating

Push to the `railway` branch and Railway auto-deploys:

```bash
# Develop on main
git checkout main
# ... make changes, test locally ...

# Ship to production
git checkout railway
git merge main
git push origin railway
```

## Cost Estimate

| Service | CPU | Memory | Est. Monthly |
|---------|-----|--------|-------------|
| API | 0.1 vCPU | 256 MB | ~$4.50 |
| Worker | 0.1 vCPU | 256 MB | ~$4.50 |
| Beat | 0.05 vCPU | 128 MB | ~$1.50 |
| Redis | minimal | 64 MB | ~$0.75 |
| **Total** | | | **~$11** |

Hobby plan ($5/mo) includes $5 in credits → **~$11/mo actual cost**.
Pro plan ($20/mo) includes $20 in credits → **$20/mo flat, no overage**.

## Troubleshooting

### API won't start
- Check `DATABASE_URL` — TiDB Cloud requires SSL. The connection string must include the full pymysql prefix.
- Check Railway logs: click the API service → **Logs** tab.

### OAuth login fails
- Verify `NEXT_PUBLIC_APP_URL` matches the Railway UI domain exactly (including `https://`).
- Verify the Google OAuth redirect URI matches: `https://<ui-domain>/api/auth/exchange`.

### Chat returns errors
- Set `OPENAI_API_KEY` on the API service.
- Check that `CORS_ALLOW_ORIGINS` includes the UI domain.

### Worker not processing jobs
- Verify `REDIS_URL` is set using Railway's variable reference: `${{Redis.REDIS_URL}}`.
- Check worker logs for connection errors.
