# URL Shortener Backend

A high-performance URL shortening platform built with **FastAPI**, designed to scale from day one. Architecture mirrors real-world systems like Bitly and TinyURL with an emphasis on low-latency redirects, async analytics, and Redis-first caching.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                        Clients                          │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP
┌────────────────────────▼────────────────────────────────┐
│              FastAPI (async, uvicorn)                   │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  Auth API   │  │  URL API     │  │  Analytics    │  │
│  │  /register  │  │  POST /urls  │  │  /summary     │  │
│  │  /login     │  │  GET /urls   │  │               │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │         GET /{short_code}  (hot path)           │    │
│  └─────────────────────────────────────────────────┘    │
└────────┬───────────────────────────────────┬────────────┘
         │                                   │
┌────────▼────────┐               ┌──────────▼──────────┐
│  Redis Cluster  │               │   PostgreSQL        │
│                 │               │                     │
│  url:{code}     │◄──cache miss──│  short_urls         │
│  hot:{code}     │               │  click_events       │
│  analytics:queue│               │  analytics_snapshot │
│  ratelimit:*    │               │  users              │
│  qr:{code}      │               │  refresh_tokens     │
└─────────────────┘               └─────────────────────┘
         │
         │  async drain
┌────────▼────────┐
│ Analytics Worker│  (background asyncio Task)
│ batch flush →   │
│ PostgreSQL      │
└─────────────────┘
```

---

## Redirect Flow (Critical Path)

Every short link click executes this sequence, optimized for minimum latency:

```
GET /{short_code}
      │
      ▼
1. Redis GET url:{short_code}
      │
      ├─ HIT → validate expiry → HTTP 302 ──────────────────┐
      │                                                      │
      └─ MISS → PostgreSQL SELECT (active, not expired)      │
                     │                                       │
                     ├─ NOT FOUND → 404                      │
                     │                                       │
                     └─ FOUND → HTTP 302 ────────────────────┤
                                                             │
                              ┌──────────────────────────────┘
                              │  BackgroundTasks (non-blocking)
                              │
                              ├─ cache_warm: Redis SETEX url:{code}
                              ├─ click_track: Redis INCR hot:{code}
                              └─ analytics: Redis RPUSH analytics:queue
```

The HTTP response is returned **before** the cache warm and analytics tasks execute. Analytics writes never add latency to redirects.

---

## Analytics Pipeline

```
Redirect endpoint
      │
      └── BackgroundTask → Redis RPUSH analytics:queue
                                      │
                      ┌───────────────┘
                      │  Every 5 seconds (configurable)
                      ▼
           AnalyticsProcessor (asyncio.Task)
                      │
                      ├── Redis LRANGE analytics:queue 0 99
                      ├── Redis LTRIM  analytics:queue 100 -1
                      └── PostgreSQL bulk INSERT click_events
                                        + UPDATE short_urls.click_count
```

Batch size and flush interval are configurable via `ANALYTICS_BATCH_SIZE` / `ANALYTICS_FLUSH_INTERVAL`.

---

## Caching Strategy

| Key Pattern | Content | TTL |
|---|---|---|
| `url:{short_code}` | Serialized URL payload | 1 hour (2× for hot URLs) |
| `hot:{short_code}` | Click counter | 1 hour (rolling) |
| `qr:{short_code}` | Base64 PNG | 24 hours |
| `analytics:summary:{code}` | Aggregated stats | 5 minutes |
| `ratelimit:{id}:{endpoint}` | Sorted set (timestamps) | Window duration |
| `analytics:queue` | List of click events | — |

**Hot URL detection**: when a link crosses `HOT_URL_CLICK_THRESHOLD` clicks, its Redis TTL is doubled automatically, preventing popular links from ever expiring from cache.

---

## Rate Limiting

Implemented as a **sliding window** using Redis sorted sets, which avoids the burst-at-boundary problem of fixed windows:

```
On each request:
  1. ZREMRANGEBYSCORE key -inf (now - window)   # remove stale entries
  2. ZCARD key                                  # current count
  3. If count < limit: ZADD key {now} {uuid}    # admit request
  4. Else: reject 429                           # deny request
```

Limits (configurable):
- Authenticated users: 100 req / 60s
- Anonymous: 20 req / 60s
- Registration: 10 attempts / hour
- Login: 20 attempts / 5 minutes

---

## Tech Stack

| Component | Technology |
|---|---|
| Framework | FastAPI 0.115 |
| Runtime | Python 3.12 + uvicorn |
| Database | PostgreSQL 16 via asyncpg |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Cache | Redis 7 (redis[asyncio]) |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Validation | Pydantic v2 |
| QR Codes | qrcode + Pillow |
| UA Parsing | user-agents |
| Logging | structlog (JSON in prod) |
| Testing | pytest-asyncio + httpx |
| Container | Docker + Docker Compose |

---

## Project Structure

```
app/
├── api/v1/endpoints/   # Thin route handlers — no business logic
│   ├── auth.py
│   ├── urls.py
│   ├── analytics.py
│   ├── qr.py
│   └── health.py
├── analytics/          # Event value objects + background processor
├── cache/              # Redis client, URL cache, rate limiter, analytics queue
├── core/               # Security, exceptions, structured logging
├── db/                 # SQLAlchemy base + async session factory
├── dependencies/       # FastAPI dependency injection (auth, db, cache)
├── middleware/         # Request logging with request-ID tracing
├── models/             # SQLAlchemy ORM models
├── repositories/       # Data access layer (no business logic)
├── schemas/            # Pydantic v2 request/response models
├── services/           # Business logic layer
├── tasks/              # Background worker lifecycle
├── tests/              # pytest-asyncio test suite
└── utils/              # Short code generation, URL validator, UA parser
```

---

## Quick Start

### With Docker (recommended)

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY to a strong random value

# 2. Start all services (Postgres, Redis, API)
docker compose up --build

# 3. Run migrations (first time only — handled by the `migrate` service)
docker compose run --rm migrate

# 4. API is live at http://localhost:8000
# 5. Interactive docs at http://localhost:8000/docs (DEBUG=true only)
```

### Local Development

```bash
# Requires Python 3.12, PostgreSQL, Redis

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # configure DATABASE_URL, REDIS_URL, SECRET_KEY

alembic upgrade head               # apply migrations

uvicorn app.main:app --reload --port 8000
```

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Register new user |
| POST | `/api/v1/auth/login` | Login, receive token pair |
| POST | `/api/v1/auth/refresh` | Rotate refresh token |
| POST | `/api/v1/auth/logout` | Revoke refresh token |
| GET | `/api/v1/auth/me` | Get current user |

### URLs

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/urls` | Optional | Shorten a URL |
| GET | `/api/v1/urls` | Required | List your URLs |
| GET | `/api/v1/urls/{id}` | Optional | Get URL detail |
| PATCH | `/api/v1/urls/{id}` | Required | Update URL |
| DELETE | `/api/v1/urls/{id}` | Required | Delete URL |

### Analytics

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/analytics/{short_code}/summary` | Required | 30-day analytics |

### QR Codes

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/qr/{short_code}` | Download PNG QR code |

### Redirect

| Method | Endpoint | Description |
|---|---|---|
| GET | `/{short_code}` | Redirect to original URL |

### System

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/health` | Database + Redis health check |

---

## Example Requests

```bash
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "MyPass123", "full_name": "John Doe"}'

# Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "MyPass123"}' | jq -r '.access_token')

# Shorten a URL
curl -X POST http://localhost:8000/api/v1/urls \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"original_url": "https://example.com/very/long/path", "custom_alias": "mylink"}'

# Redirect (follow with browser or -L)
curl -L http://localhost:8000/mylink

# Download QR code
curl http://localhost:8000/api/v1/qr/mylink --output mylink.png

# Analytics
curl http://localhost:8000/api/v1/analytics/mylink/summary \
  -H "Authorization: Bearer $TOKEN"
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | — | PostgreSQL async connection string |
| `REDIS_URL` | — | Redis connection string |
| `SECRET_KEY` | — | JWT signing secret (change in production) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh token TTL |
| `BASE_URL` | `http://localhost:8000` | Base URL for generated short links |
| `SHORT_CODE_LENGTH` | `7` | Auto-generated code length |
| `RATE_LIMIT_REQUESTS` | `100` | Requests per window (authenticated) |
| `RATE_LIMIT_WINDOW` | `60` | Rate limit window in seconds |
| `ANALYTICS_BATCH_SIZE` | `100` | Events per flush to Postgres |
| `ANALYTICS_FLUSH_INTERVAL` | `5` | Seconds between flushes |
| `HOT_URL_CLICK_THRESHOLD` | `100` | Clicks to extend cache TTL |
| `DEBUG` | `false` | Enable SQL echo + Swagger UI |

---

## Running Tests

```bash
pip install -r requirements.txt aiosqlite
pytest -v
```

Tests use an in-memory SQLite database and mocked Redis — no external services required.

---

## Security Notes

- Passwords are hashed with **bcrypt** (work factor 12)
- Refresh tokens are stored as **SHA-256 hashes** — raw tokens never touch the DB
- Short codes use `secrets.choice` (CSPRNG) to prevent enumeration of private links
- Incoming URLs are validated for safe scheme and blocked hosts (SSRF prevention)
- Rate limiting on auth endpoints prevents brute-force attacks
- `X-Request-ID` header on every response enables distributed log tracing
