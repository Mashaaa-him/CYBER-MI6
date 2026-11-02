# API Layer (Macharia)

This documents the API layer I've written for CYBER-MI6: the settings, the API key check, the rate limiter, the WebSocket manager, and the app skeleton. It covers what each file does, how to test it, and what's still to come.

## Status

| Component | File | Status |
|---|---|---|
| Settings | `app/config.py`, `.env.example` | Merged |
| API key check | `app/security.py` | Merged |
| Rate limiter | `app/ratelimit.py` | Merged |
| WebSocket manager | `app/routes/ws.py` | Merged |
| App factory, error format, static mount | `app/main.py` | Merged (startup fix in review) |
| Dependency helpers | `app/deps.py` | Merged with `main.py` |
| Events route | `app/routes/events.py` | Not started |
| Alerts route | `app/routes/alerts.py` | Not started |
| Stats route | `app/routes/stats.py` | Not started |

Routes for events, alerts, and stats depend on Lee's data layer (`db.py`, `storage.py`, `models.py`), which is not yet on `main`.

## Files

### `app/config.py`

Loads settings from environment variables and `.env`, using the names in the handbook. Every field has a default, so the app can be imported without a `.env` file.

- `API_KEY`: the key that sensors and apps send. Empty means ingestion is disabled.
- `DATABASE_PATH`, `EVENT_RETENTION_DAYS`: storage settings.
- `INGEST_MAX_BATCH`, `INGEST_RATE_LIMIT`, `INGEST_RATE_WINDOW_SECONDS`: ingestion limits.
- `PORT_SCAN_*`, `DNS_*`, `AUTH_FAIL_*`, `ALERT_COOLDOWN_SECONDS`: detection thresholds, read by the detection engine.
- `ALLOWED_ORIGINS`: comma-separated list for CORS.

`get_settings()` is cached. Tests clear the cache when they change settings.

### `app/security.py`

`require_api_key` is a FastAPI dependency. It reads the `X-API-Key` header and compares it with `API_KEY` using a constant-time check.

- Missing or wrong key: **401**
- `API_KEY` not configured: **503**

### `app/ratelimit.py`

`SlidingWindowLimiter` allows a fixed number of calls per key (the client IP) within a time window. It's thread-safe, because FastAPI runs synchronous dependencies in a thread pool.

Known limitations:
- It keeps an entry for every IP it has seen and never removes idle ones.
- Behind a reverse proxy, every request shares one IP, so the limit applies to everyone at once.

### `app/routes/ws.py`

The `/ws` endpoint and `ConnectionManager`.

- `connect` and `disconnect` track live clients.
- `broadcast` sends a message to every client. A client that fails or takes longer than two seconds to accept a message is removed, so it can't hold up the others.
- `broadcast_event(event)` and `broadcast_alert(alert)` send messages in the format the dashboard expects:

```json
{"kind": "event", "data": { ... }}
{"kind": "alert", "data": { ... }}
```

### `app/deps.py`

`get_db` and `get_ingest_limiter` return the database and rate limiter that the app stores on `app.state` at startup. Routes use these through `Depends`, so tests can replace them.

### `app/main.py`

`create_app()` builds the FastAPI app. It:

- opens the database and starts the hourly retention job in the lifespan,
- returns every error as `{"error": ..., "detail": ...}`,
- adds CORS only when `ALLOWED_ORIGINS` is set,
- mounts the frontend's static files last, so they can't hide API routes.

The database, storage, and retention imports are inside the functions that use them, so `main.py` loads before the data layer is merged. Move them to the top of the file once `db.py` is on `main`.

Any new router must be included before the static mount.

## Tests

Tests are in `tests/`. Run them from the folder that contains `pytest.ini`:

```bash
pytest -q
```

Current result: **230 passed, 1 skipped**. The skipped test checks that startup creates the database file, and it runs once `app/db.py` is merged.

| File | What it checks |
|---|---|
| `test_auth.py` | 401 for missing or wrong key, 200 for correct key, 503 when unconfigured, non-ASCII key returns 401 |
| `test_ratelimit.py` | Limits per key, recovery after the window, expiry of old hits, thread safety under 500 concurrent calls |
| `test_ws.py` | Connect and disconnect counts, broadcast to multiple clients, 50 connect-and-disconnect cycles, dropping broken and slow clients |
| `test_app.py` | `/docs` loads, unknown API paths return the standard error shape, validation errors return 422 in that shape |

Tests never use the real `data/` folder. Database tests use a temporary file.

## Blocked

- **Server startup:** the lifespan opens the database, so `uvicorn` fails until `app/db.py` is on `main`. The error is `No module named 'app.db'`.
- **Events, alerts, and stats routes:** these call storage functions, so they can't be finished until the data layer is merged.
- **Dashboard data:** the frontend can load once the server starts, but live data needs the routes above.

## Next

1. Confirm the folder layout with the team. Import paths depend on the `app` package being importable from where the server runs.
2. Once `db.py`, `models.py`, and `storage.py` are on `main`, pull `main`, start the server, and run the tests. Turn on the skipped startup test.
3. Build `routes/events.py`: `POST /api/events` with the API key, batch limit, rate limit, and broadcast, then `GET /api/events` with filters.
4. Build `routes/alerts.py`: list, detail, and status changes with the transition rules.
5. Build `routes/stats.py`.
6. Replace the literal batch limit in `config.py` with `models.MAX_BATCH_SIZE`.
7. Make the PATCH status change atomic by running the check and write inside one database transaction.

## Known issues

- **Batch limit:** `config.py` hard-codes 500 to match `models.MAX_BATCH_SIZE`. Switch to the import once `models.py` is merged.
- **Rate limiter memory:** idle IP entries are never removed. Acceptable for a small network, but it needs a cleanup pass.
- **Rate limiting behind a proxy:** all clients share one address behind a proxy. Read the real client address from a trusted proxy header if deployment changes.
- **Test deprecation warning:** `starlette`'s test client warns about `httpx`. The tests still pass.