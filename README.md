# KredoBook

KredoBook is a role-based loan management application for tracking borrower accounts, individual loans, repayment proof, and monthly payment reminders. It gives administrators a central portfolio view while keeping each borrower limited to their own financial records.

## Purpose

Small lending operations often need a lightweight way to record loans, verify repayments, and follow up on outstanding balances without relying on spreadsheets. KredoBook provides that workflow in one place:

- administrators create and manage borrower accounts and loans;
- borrowers view their loan portfolio and submit repayment proof;
- verified payments update balances; and
- monthly reminders notify eligible borrowers without changing any financial data.

## Key features

### Administration

- Create, update, activate, deactivate, and permanently remove borrower accounts.
- Create, edit, inspect, and remove loans.
- Record historic/offline payments and review borrower-submitted payments.
- Approve or reject repayment proofs, with rejection reasons.
- View portfolio statistics, outstanding balances, and pending-payment counts.
- Filter loans by borrower and sort them by newest, oldest, highest amount, or lowest amount.
- Trigger monthly reminder delivery and review reminder logs.

### Borrower portal

- Secure login and an account-scoped dashboard.
- View active and historical loans, repayment progress, balances, and loan details.
- Sort loans by newest, oldest, highest amount, or lowest amount.
- Submit repayment amount, payment month/date, and a screenshot proof.
- Review payment history and verification status.

### Financial integrity and security

- Separate `ADMIN` and `BORROWER` roles with JWT authentication.
- Borrower ownership checks prevent access to another borrower's loans, payments, or screenshots.
- Amounts are persisted as `NUMERIC(15,2)` / `Decimal` values.
- A loan balance is derived from verified payments only; pending and rejected payments do not reduce it.
- Payment review follows a one-way workflow: `PENDING` -> `VERIFIED` or `REJECTED`.
- Payment uploads are size- and MIME-validated, stored with generated filenames, and served only to authorised users.
- Monthly reminder records are idempotent per borrower and month.

## Domain model

| Entity | Meaning | Important relationships |
| --- | --- | --- |
| `User` | An administrator or borrower account. | A borrower can have many loans and payments. |
| `Loan` | A distinct loan issued to one borrower. | Has an amount, payable total, minimum monthly payment, status, and payments. |
| `Payment` | A repayment submission or admin-recorded historic payment. | Belongs to one loan and borrower; may have a proof screenshot and verifier. |
| `ReminderLog` | Audit record for a monthly reminder attempt. | Prevents duplicate reminders for the same borrower/month. |

Loan statuses are `ACTIVE`, `PAID`, and `CANCELLED`. Payment statuses are `PENDING`, `VERIFIED`, and `REJECTED`.

## Tech stack

- **Frontend:** React 19, Vite, React Router
- **Backend:** FastAPI, SQLAlchemy 2, Pydantic
- **Database:** PostgreSQL (configured for Neon)
- **Authentication:** JWT and bcrypt password hashing
- **Migrations:** Alembic
- **Background jobs:** APScheduler for monthly reminder scheduling
- **Email templates:** Jinja2

## Architecture

```text
React / Vite frontend
        | HTTP + JWT
        v
FastAPI API
 |- authentication and role checks
 |- loan, payment, borrower, and reminder services
 |- protected screenshot storage
 `- monthly reminder scheduler
        |
        v
PostgreSQL / Neon
```

## Project structure

```text
Loan_tracker/
├── backend/
│   ├── app/
│   │   ├── models/       # SQLAlchemy domain models
│   │   ├── routes/       # FastAPI endpoints
│   │   ├── schemas/      # Request and response validation
│   │   ├── services/     # Loan, payment, email, and reminder logic
│   │   └── utils/        # Security and upload helpers
│   ├── alembic/          # Database migrations
│   ├── tests/            # API and workflow tests
│   └── requirements.txt
├── frontend/
│   ├── src/pages/        # Admin, borrower, login, and home pages
│   ├── src/services/     # API client modules
│   └── src/context/      # Authentication state
├── .env.example
└── README.md
```

## Getting started

### Prerequisites

- Python 3.10 or newer
- Node.js 18 or newer
- A PostgreSQL database (a Neon PostgreSQL database is supported)

### 1. Configure environment variables

Create a `.env.local` file in the repository root. Start from [`.env.example`](.env.example) and supply real values. The backend reads `.env.local` from the project root.

Important values:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require
JWT_SECRET=replace-with-a-long-random-secret
CORS_ORIGINS=http://localhost:5173

EMAIL_ENABLED=false
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_USERNAME=...
EMAIL_PASSWORD=...
EMAIL_FROM=notifications@example.com
```

For the frontend, create `frontend/.env` when the API is not hosted at the default local address:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Never commit real database credentials, JWT secrets, or SMTP passwords.

### 2. Install backend dependencies and migrate the database

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

Set-Location backend
alembic upgrade head
```

Use a direct (non-`-pooler`) Neon connection for Alembic migrations when one is available.

### 3. Start the API

From `backend/`:

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Useful local endpoints:

- API health: `http://127.0.0.1:8000/health`
- OpenAPI/Swagger: `http://127.0.0.1:8000/docs`

### 4. Start the frontend

In a separate terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## API overview

| Area | Main endpoints |
| --- | --- |
| Health | `GET /health` |
| Authentication | `POST /auth/login`, `GET /auth/me` |
| Borrowers | `GET/POST /borrowers`, `PUT/DELETE /borrowers/{id}` |
| Admin loans | `GET/POST /loans`, `GET/PUT/DELETE /loans/{id}`, `GET /loans/stats` |
| Borrower loans | `GET /my/loans`, `GET /my/loans/{id}`, `GET /my/stats` |
| Payments | `GET /payments`, `GET /payments/pending`, approve/reject endpoints, protected screenshot endpoint |
| Borrower payments | `POST /my/payments`, `GET /my/payments` |
| Reminders | `POST /reminders/send-monthly`, `GET /reminders/logs` |

Refer to the running API’s Swagger interface for the complete request and response schemas.

## Monthly reminder rules

The reminder process is informational only. It does not create payments, verify payments, or alter loan balances. A borrower is eligible only when they are active, have reminders enabled, and have at least one active loan with a positive remaining balance. Multiple active loans are consolidated into one reminder per borrower per month.

## Testing and quality checks

Frontend checks:

```powershell
Set-Location frontend
npm run lint
npm run build
```

Backend tests:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest tests -v
```

The current backend tests use the configured database connection. Point `DATABASE_URL` to an isolated test database before running them; do not run test cleanup against production data.

## Deployment notes

- Set a strong, unique `JWT_SECRET` and production-only `CORS_ORIGINS`.
- Use a pooled database URL for the running web application and a direct database URL for migrations.
- Set `EMAIL_ENABLED=true` only after verifying SMTP credentials and sender configuration.
- Persist the backend upload directory or use managed object storage in production; uploaded payment proofs should not be publicly served.
- Configure frontend single-page-app fallback routing on the hosting provider.

## License

No license has been specified for this repository.
