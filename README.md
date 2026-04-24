# Playto Pay Payout Engine

Minimal payout engine for the Playto founding engineer challenge. It uses Django, DRF, PostgreSQL, Celery, Redis, React, and Tailwind.

The core behavior is intentionally small and strict:

- balances are integer paise in `BigIntegerField`
- available balance is derived from ledger credits minus debits
- payout creation locks the merchant row before checking and holding funds
- idempotency keys are scoped to a merchant and store the first response
- payout state changes are guarded by a small state machine
- stuck processing payouts are retried with exponential backoff and max 3 attempts

## Run Locally

Start PostgreSQL and Redis:

```bash
docker compose up -d
```

Create the backend environment:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_playto
python manage.py runserver
```

In two more terminals, run the worker and scheduler:

```bash
cd backend
.venv\Scripts\activate
celery -A playto_pay worker -l info
```

```bash
cd backend
.venv\Scripts\activate
celery -A playto_pay beat -l info
```

Run the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## API

The demo uses `X-Merchant-Id` instead of auth so reviewers can switch seeded merchants quickly.

List merchants:

```bash
GET /api/v1/merchants
```

Dashboard:

```bash
GET /api/v1/dashboard
X-Merchant-Id: <merchant_uuid>
```

Create payout:

```bash
POST /api/v1/payouts
X-Merchant-Id: <merchant_uuid>
Idempotency-Key: <uuid>

{
  "amount_paise": 60000,
  "bank_account_id": "<bank_account_uuid>"
}
```

## Tests

Run the meaningful money tests against PostgreSQL:

```bash
cd backend
pytest
```

Included tests:

- `payouts/tests/test_concurrency.py`: two parallel 60 rupee payouts against a 100 rupee balance result in exactly one hold.
- `payouts/tests/test_idempotency.py`: repeat requests with the same idempotency key return the same response and create no duplicate payout.

## Deployment Notes

Backend can be deployed to Render, Railway, Fly.io, or Koyeb with three processes from `backend/Procfile`: `web`, `worker`, and `beat`. Configure:

- `DATABASE_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `CORS_ALLOWED_ORIGINS`

Frontend can be deployed to Vercel or Netlify with:

- build command: `npm run build`
- output directory: `dist`
- env var: `VITE_API_BASE=https://<backend-host>/api/v1`
