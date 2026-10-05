# KredoBook

An enterprise-grade, secure, and production-ready **Loan Management Platform** built with **FastAPI**, **React (Vite)**, and **Neon Serverless PostgreSQL**.

---

## Table of Contents

- [1. Architecture Overview](#1-architecture-overview)
- [2. Features & Functional Modules](#2-features--functional-modules)
- [3. Monthly Email Reminder System](#3-monthly-email-reminder-system)
- [4. Security Hardening & Concurrency Protection](#4-security-hardening--concurrency-protection)
- [5. Financial Data Integrity](#5-financial-data-integrity)
- [6. Environment Variables](#6-environment-variables)
- [7. Local Development Guide](#7-local-development-guide)
- [8. Database Migrations (Alembic)](#8-database-migrations-alembic)
- [9. Production Deployment Guide](#9-production-deployment-guide)
- [10. API Reference](#10-api-reference)
- [11. Testing & Verification](#11-testing--verification)

---

## 1. Architecture Overview

```text
KredoBook

React Frontend
      ↓
FastAPI Backend
      ↓
Neon PostgreSQL
```

* **Frontend**: React (Vite), SPA routing via React Router DOM, centralized `AuthContext`, dark glassmorphic responsive UI, responsive mobile navigation drawer.
* **Backend**: FastAPI (Python 3.10+), SQLAlchemy 2.0 ORM, Pydantic v2 data validation, structured logging, centralized HTTP error masking.
* **Database**: Neon Serverless PostgreSQL with SSL connection pooling.
* **Storage**: Protected screenshot storage with MIME verification and access token authorization.
* **Notifications**: Informational SMTP email reminder engine with fallback logger and idempotent database audit logging.

---

## 2. Features & Functional Modules

### Roles & Access Control
- **ADMIN**:
  - Full management of borrowers (create, activate, deactivate, toggle email reminder preference).
  - Loan lifecycle management (create loans, update notes/terms, inspect multi-loan borrower accounts).
  - Repayment verification hub (review payment screenshots, approve payments to reduce balances, reject with explicit reasons).
  - Trigger manual or scheduled monthly reminder dispatch.
  - Comprehensive portfolio statistics and audit logs.
- **BORROWER**:
  - Secure login and isolated personal dashboard.
  - View all individual active and completed loans with independent progress metrics.
  - Submit repayment records with payment amount, month, date, and payment screenshot proof.
  - View historical payments with real-time status (`PENDING`, `VERIFIED`, `REJECTED`).
  - View and download verified screenshot receipts.

---

## 3. Monthly Email Reminder System

On the 1st of every month (or when triggered by admin/cron), the system scans eligible borrowers and dispatches an informational reminder.

### Key Rules
1. **Informational Only**:
   - The scheduler **NEVER** creates payment records.
   - The scheduler **NEVER** marks payments as paid.
   - The scheduler **NEVER** alters loan balances or deducts funds.
2. **Borrower Eligibility**:
   - Borrower is active (`is_active = true`).
   - Borrower has reminders enabled (`monthly_reminder_enabled = true`).
   - Borrower has at least one `ACTIVE` loan with `remaining_balance > 0`.
   - Borrowers with only `PAID` or `CANCELLED` loans are automatically skipped.
3. **Multi-Loan Aggregation**:
   - If a borrower has multiple active loans, they receive **one single email** summarizing all active loans with their respective principal, total payable, verified paid, remaining balance, and minimum monthly payment.
4. **Idempotency Guarantee**:
   - Tracked in `monthly_reminder_logs` with a unique constraint `(borrower_id, reminder_month)`.
   - Prevents duplicate reminders even across multiple backend worker instances.

---

## 4. Security Hardening & Concurrency Protection

* **Authentication**: Password hashing with Bcrypt; stateless JWT Bearer tokens with configurable expiration; inactive user login blocking.
* **Tenant Isolation**: Strict ownership checks preventing borrowers from accessing other borrowers' loans, payments, or screenshot proofs (`HTTP 403 / 404`).
* **Protected File Uploads**:
  - Uploaded files are stored outside the public document root.
  - Validated by MIME type inspection (`image/jpeg`, `image/png`, `image/webp`, `image/heic`).
  - Strict 5MB file size limit enforced before writing to disk.
  - Safe randomized UUID filenames to prevent path traversal or script execution.
  - Only authenticated admins and the owning borrower can view/download screenshots.
* **Payment Concurrency & State Machine**:
  - Strict transitions: `PENDING → VERIFIED` or `PENDING → REJECTED`.
  - Once a payment is `VERIFIED` or `REJECTED`, subsequent review attempts return `HTTP 400 Bad Request`.
* **CORS & Environment**:
  - CORS strictly configured via `CORS_ORIGINS` environment variable (no open wildcards in production).
  - Internal stack traces and database credentials are sanitised from production API responses.

---

## 5. Financial Data Integrity

* **Precision**: All financial columns (`loan_amount`, `total_payable`, `minimum_monthly_payment`, `amount`, `total_outstanding`) use PostgreSQL `NUMERIC(15, 2)`.
* **Balance Invariant**:
  $$\text{remaining\_balance} = \text{total\_payable} - \sum(\text{VERIFIED payments})$$
* Pending and Rejected payments never reduce loan balances.
* Overpayments exceeding remaining balance are rejected at submission.
* Total payable cannot be updated below the already verified paid amount.

---

## 6. Environment Variables

### Backend Configuration (`backend/.env`)

```env
# Neon PostgreSQL Connection (Direct or Pooled)
DATABASE_URL=postgresql://neondb_owner:YOUR_PASSWORD@ep-sample-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require

# JWT Secret & Expiration
JWT_SECRET=generate_with_openssl_rand_hex_32
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Allowed CORS Origins (Comma-separated)
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,https://your-domain.com

# SMTP Email Configuration
EMAIL_ENABLED=false
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USERNAME=apikey
EMAIL_PASSWORD=your_smtp_key
EMAIL_FROM=notifications@yourdomain.com

# Upload Settings
UPLOAD_MAX_SIZE=5242880
UPLOAD_DIR=uploads/screenshots
```

### Frontend Configuration (`frontend/.env`)

```env
# Backend API Base URL
VITE_API_BASE_URL=http://127.0.0.1:8000
```

---

## 7. Local Development Guide

### 1. Backend

```bash
cd backend
python -m venv ..\.venv
..\.venv\Scripts\activate   # Windows
# source ../.venv/bin/activate # macOS/Linux

pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

The application will be accessible at:
- **Frontend**: `http://localhost:5173`
- **Backend Swagger Docs**: `http://127.0.0.1:8000/docs`
- **Health Check**: `http://127.0.0.1:8000/health`

---

## 8. Database Migrations (Alembic)

Run all migrations against your Neon database:

```bash
cd backend
alembic upgrade head
```

To create a new migration after updating SQLAlchemy models:

```bash
alembic revision --autogenerate -m "describe_changes"
alembic upgrade head
```

---

## 9. Production Deployment Guide

### 1. Database (Neon PostgreSQL)
1. Verify database compute endpoints and connection pooling in the [Neon Console](https://console.neon.tech).
2. Set `DATABASE_URL` with `sslmode=require`.

### 2. Backend Deployment (e.g. Render, Railway, AWS ECS, VPS)
1. Set all environment variables defined in `backend/.env.example`.
2. Run database migrations: `alembic upgrade head`.
3. Start production ASGI server:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```
4. Verify `/health` returns `{"status": "ok", "database": "connected"}`.

### 3. Frontend Deployment (e.g. Vercel, Netlify, Cloudflare Pages)
1. Set `VITE_API_BASE_URL` to your production backend domain.
2. Build static bundle: `npm run build`.
3. Deploy output folder `dist/` with single-page application fallback rules (`index.html`).

---

## 10. API Reference

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/health` | Public | System & database health check |
| `POST` | `/auth/login` | Public | Authenticate user & issue JWT |
| `GET` | `/auth/me` | Authenticated | Retrieve profile of authenticated user |
| `GET` | `/borrowers` | Admin | List all registered borrowers |
| `POST` | `/borrowers` | Admin | Register new borrower account |
| `PATCH` | `/borrowers/{id}` | Admin | Update borrower status / details |
| `PATCH` | `/borrowers/{id}/reminders` | Admin / Owner | Toggle monthly reminder preference |
| `GET` | `/loans` | Admin | List all loans in portfolio |
| `POST` | `/loans` | Admin | Issue a new loan |
| `GET` | `/loans/{id}` | Admin | Get loan details and summary |
| `PATCH` | `/loans/{id}` | Admin | Update loan terms or notes |
| `GET` | `/my/loans` | Borrower | List current borrower's loans |
| `GET` | `/my/loans/{id}` | Borrower | Get borrower's specific loan details |
| `POST` | `/my/payments` | Borrower | Submit repayment proof with screenshot |
| `GET` | `/my/payments` | Borrower | View repayment submission history |
| `GET` | `/payments` | Admin | View all submitted payments with status filter |
| `GET` | `/payments/pending` | Admin | List all pending payments awaiting review |
| `POST` | `/payments/{id}/approve` | Admin | Approve payment and decrease remaining balance |
| `POST` | `/payments/{id}/reject` | Admin | Reject payment with reason |
| `GET` | `/payments/{id}/screenshot` | Admin / Owner | View/stream encrypted payment proof |
| `POST` | `/reminders/send-monthly` | Admin | Trigger monthly payment reminder dispatch |
| `GET` | `/reminders/logs` | Admin | Audit logs of sent reminder notifications |

---

## 11. Testing & Verification

Run the full automated integration test suite:

```bash
cd backend
pytest tests/ -v
```

All 51+ integration tests validate:
- Authentication & JWT validation
- Role-based authorization & tenant isolation
- Multi-loan portfolio calculations & balances
- Repayment submission, file upload checks, and admin approvals
- Monthly reminder dispatch, multi-loan aggregation, and idempotency
#   K r e d o b o o k  
 