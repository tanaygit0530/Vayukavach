# Deploying VayuKavach

| Part | Where | Config |
| --- | --- | --- |
| Database | Supabase (already running) | `DATABASE_URL`, session pooler |
| API | Render, free web service, Singapore | `render.yaml` |
| Frontend | Vercel, root directory `frontend` | `frontend/vercel.json` |
| Collectors | GitHub Actions + the Mac launchd job (CPCB) | `.github/workflows/collect-hourly.yml` |
| Deploy on main | GitHub Actions, after CI passes | `.github/workflows/deploy.yml` |
| Uptime | GitHub Actions, every 10 min | `.github/workflows/uptime.yml` |

## 1. API on Render

1. render.com → New → Blueprint → pick the `Vayukavach` repo. Render reads `render.yaml`.
2. Fill the secret values it asks for (same as your `.env`):
   - `DATABASE_URL`: the Supabase session-pooler URL, written as `postgresql+psycopg://...`
   - `FRONTEND_ORIGIN`: the Vercel URL from step 2 (add it after step 2; several origins can be
     comma-separated)
   - `PUBLIC_API_URL`: this service's own URL, e.g. `https://vayukavach-api.onrender.com`
   - `DATA_GOV_IN_API_KEY`, `OPENAQ_API_KEY`, `GEMINI_API_KEY`
   - Alerts (optional): `SMTP_*`, `TWILIO_*`
3. Settings → Deploy Hook → copy the URL.
4. Check `https://<service>.onrender.com/health` shows `"database":"ok"`.

The free plan sleeps after 15 minutes without traffic; the uptime check (every 10 minutes)
keeps it awake, and one always-on service fits in the free 750 hours a month.

## 2. Frontend on Vercel

1. vercel.com → Add New → Project → import the repo.
2. Root Directory: `frontend`. Framework: Vite (read from `vercel.json`).
3. Environment variable: `VITE_API_BASE_URL` = the Render URL (no trailing slash).
4. Deploy. Then put the Vercel URL into Render's `FRONTEND_ORIGIN` and redeploy the API.

Vercel's Git integration deploys every push to `main`.

## 3. GitHub settings

Repository → Settings → Secrets and variables → Actions.

| Name | Type | Used by |
| --- | --- | --- |
| `RENDER_DEPLOY_HOOK_URL` | secret | deploy after CI |
| `PUBLIC_API_URL` | variable | deploy health wait, uptime, alert stop links |
| `DATABASE_URL`, `DATA_GOV_IN_API_KEY`, `OPENAQ_API_KEY` | secret | collectors (already set) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | secret | alerts, uptime notice |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_SMS_FROM`, `TWILIO_WHATSAPP_FROM` | secret | alerts, uptime notice |
| `ADMIN_EMAIL`, `ADMIN_PHONE` | secret | collector-failure and uptime notices |

## 4. Alert channels

**Email (Gmail):** Google Account → Security → 2-Step Verification on → App passwords →
create one for "VayuKavach". Then `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`,
`SMTP_USER=<your gmail>`, `SMTP_PASSWORD=<16-letter app password>`, `SMTP_FROM=<your gmail>`.
Gmail allows about 500 messages a day.

**WhatsApp (Twilio sandbox, free):** console.twilio.com → Messaging → Try it out → Send a
WhatsApp message. Note the sandbox number (`+14155238886`) and the join phrase
(`join <two-words>`). Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
`TWILIO_WHATSAPP_FROM=whatsapp:+14155238886`, `TWILIO_WHATSAPP_JOIN=join <two-words>`.
Each recipient must send the join phrase to the sandbox number first; the sign-up page shows
it. Sandbox sessions end after 72 hours without a message from the recipient.

**SMS (Twilio):** buy or use the trial number as `TWILIO_SMS_FROM`. A trial account only sends
to numbers verified in the Twilio console and prefixes messages with "Sent from your Twilio
trial account". Sending to any Indian number in production needs DLT registration
(TRAI rules) or an Indian SMS provider.

## 5. Check after deploying

- `https://<api>/health` → `{"status":"ok","database":"ok"}`
- The Vercel URL opens the Air tab with live data and no CORS errors in the browser console.
- `/alerts`: channels you configured are selectable; sign up and confirm with the code.
- Actions → Uptime → Run workflow: passes.
