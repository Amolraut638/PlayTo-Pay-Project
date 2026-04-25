# Playto Pay — Payout Engine

A minimal but production-correct payout engine for Indian merchants collecting international payments. Built for the Playto Founding Engineer challenge.

## What this does

- Merchants accumulate balance via credits (simulated customer payments)
- Merchants request payouts to their Indian bank account
- Funds are held immediately on request, released on failure
- Background worker processes payouts asynchronously with retry logic
- Full concurrency safety and idempotency guarantees

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | Django 5 + Django REST Framework |
| Database | PostgreSQL (amounts stored as paise in BigIntegerField) |
| Queue | Celery + Redis |
| Frontend | React + Tailwind CSS |

## Local Setup

### Prerequisites
- Python 3.11+
- PostgreSQL
- Redis
- Node.js 18+

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd "New project"
```

### 2. Backend setup

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Environment variables

Copy the example env file:

```bash
cp ../.env.example .env
```

Edit `.env` with your database and Redis credentials:

```bash
SECRET_KEY=your-secret-key-here
DEBUG=1
POSTGRES_DB=playto_pay
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
CELERY_BROKER_URL=redis://localhost:6379/0
```

### 4. Database setup

```bash
python manage.py migrate
python manage.py seed_playto
```

This seeds 3 merchants with bank accounts and credit history.

### 5. Run the backend

Open 3 separate terminals:

**Terminal 1 — Django server:**

```bash
python manage.py runserver
```

**Terminal 2 — Celery worker:**

```bash
celery -A playto_pay worker --loglevel=info
```

**Terminal 3 — Celery beat (scheduler):**

```bash
celery -A playto_pay beat --loglevel=info
```

### 6. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Visit: http://localhost:5173

## Docker (easiest way)

```bash
docker-compose up --build
```

This starts PostgreSQL, Redis, Django, Celery worker, Celery beat and React all together.

Visit: http://localhost:5173

## Running Tests

```bash
cd backend
pytest payouts/tests/ -v
```

**Concurrency test** — verifies two simultaneous 60-rupee payout requests against a 100-rupee balance results in exactly one success and one rejection.

**Idempotency test** — verifies the same idempotency key returns the identical response without creating a duplicate payout.

## API Reference

All endpoints require `X-Merchant-Id` header.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/merchants` | List all merchants |
| GET | `/api/v1/dashboard` | Merchant balance + payout history |
| GET | `/api/v1/payouts` | List payouts for merchant |
| POST | `/api/v1/payouts` | Create payout request |

**POST /api/v1/payouts** requires `Idempotency-Key` header (UUID).

```json
{
  "amount_paise": 50000,
  "bank_account_id": "uuid-here"
}
```

## Architecture Decisions

See [EXPLAINER.md](./EXPLAINER.md) for detailed explanation of the ledger model, locking strategy, idempotency implementation, state machine, and AI audit.

## Live Demo

URL: `<your-railway-url>`

Test merchants are pre-seeded with balance. Use the dashboard to request payouts and watch the background worker process them in real time.