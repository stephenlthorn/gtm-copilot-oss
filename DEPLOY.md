# Deploying GTM Copilot to Railway

## Prerequisites
- Railway account at railway.app (free tier works)
- GitHub repo connected to Railway
- Google OAuth app credentials

## Step 1: Create Railway Project

1. Go to railway.app → New Project → Deploy from GitHub repo
2. Select `gtm-copilot-oss`
3. Railway auto-detects services

## Step 2: Add Databases

In Railway dashboard:
1. Click **+ New** → **Database** → **PostgreSQL** — Railway provisions it automatically
2. Click **+ New** → **Database** → **Redis** — Railway provisions it automatically

## Step 3: Deploy Services

Add 4 services from the repo:
1. **API** — Root directory: `api/`, Start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
2. **Worker** — Root directory: `api/`, Start command: `celery -A app.worker.celery_app worker --loglevel=info`
3. **Beat** — Root directory: `api/`, Start command: `celery -A app.worker.celery_app beat --loglevel=info`
4. **UI** — Root directory: `ui/`, Start command: `npm start`

## Step 4: Set Environment Variables

On the **API, Worker, and Beat** services, set:
```
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
SECRET_KEY=<generate with: openssl rand -hex 32>
GOOGLE_CLIENT_ID=<from Google Cloud Console>
GOOGLE_CLIENT_SECRET=<from Google Cloud Console>
ENVIRONMENT=production
LOG_LEVEL=INFO
SENTRY_DSN=<optional - from sentry.io>
```

On the **UI** service, set:
```
NEXT_PUBLIC_API_URL=https://<your-api-railway-domain>
NEXT_PUBLIC_APP_URL=https://<your-ui-railway-domain>
NEXTAUTH_URL=https://<your-ui-railway-domain>
NEXTAUTH_SECRET=<generate with: openssl rand -hex 32>
GOOGLE_CLIENT_ID=<same as API>
GOOGLE_CLIENT_SECRET=<same as API>
```

## Step 5: Configure Google OAuth

In Google Cloud Console → APIs & Services → Credentials → your OAuth app:
- Add Authorized redirect URI: `https://<your-ui-railway-domain>/api/auth/exchange`

## Step 6: First Login

1. Visit your UI Railway domain
2. Sign in with Google
3. Go to `/admin` → set OpenAI API key and other integrations

## Step 7: Verify

- API health: `https://<api-domain>/` → `{"status":"ok"}`
- UI loads and Google login works
- Admin panel accessible at `/admin`
