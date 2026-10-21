# CYBER-MI6

**Detect. Analyze. Respond. Secure.**

CYBER-MI6 is a network and web-application threat detection prototype. It ingests metadata from authorized live network observations and security events from our own instrumented web application, evaluates transparent detection rules, stores events and alerts, and presents them in a real-time dashboard.

> **Project setup:** CYBER-MI6 runs directly on Windows and Linux computers. Virtual machines are not required. Network visibility is limited to traffic the selected computer/interface can observe; a normal laptop cannot automatically see all traffic from every device on a Wi-Fi network.

> **Authorized use only:** use only networks and applications the team owns or has explicit permission to monitor. Detections are indicators of possible threats, not proof of an attack.

---

## Table of Contents

1. [Goals](#1-goals)
2. [MVP Features](#2-mvp-features)
3. [Technology Stack](#3-technology-stack)
4. [Architecture](#4-architecture)
5. [Repository Structure](#5-repository-structure)
6. [Backend Specification](#6-backend-specification)
7. [Frontend Specification](#7-frontend-specification)
8. [Detection Rules and Limitations](#8-detection-rules-and-limitations)
9. [Team Structure and Tasks (6 Members)](#9-team-structure-and-tasks-6-members)
10. [Timeline](#10-timeline)
11. [Getting Started](#11-getting-started)
12. [Testing and Definition of Done](#12-testing-and-definition-of-done)
13. [Security and Privacy Rules](#13-security-and-privacy-rules)
14. [Git Workflow](#14-git-workflow)
15. [After the MVP](#15-after-the-mvp)
16. [Glossary](#16-glossary)

---

## 1. Goals

- Collect a small, documented set of network and application security events.
- Detect suspicious patterns with **explainable rules before introducing machine learning**.
- Show events, alerts, severity, evidence, and alert status in a browser dashboard.
- Keep the prototype portable across Windows and Linux.
- Use only networks and applications the team owns or has explicit permission to monitor.

---

## 2. MVP Features

| # | Feature | Where |
|---|---|---|
| 1 | FastAPI event ingestion and validation at `POST /api/events` | `app/` |
| 2 | SQLite persistence for events and alerts | `app/` |
| 3 | WebSocket messages for live dashboard updates | `app/`, `web/` |
| 4 | Dashboard for recent activity, alert history, and alert status | `web/` |
| 5 | Rule-based detection: possible port scans, unusual DNS labels, repeated authentication failures, suspicious web paths | `app/` |
| 6 | Cross-platform Scapy sensor that sends TCP initial-SYN connection metadata and DNS query names. **It does not store packet payloads.** | `collectors/scapy_collector.py` |
| 7 | Synthetic event generator for safe, repeatable tests | `tools/send_demo_events.py` |
| 8 | Example helper for reporting events from an application the team owns | `examples/webapp_event_reporting.py` |

Optional: a Zeek JSON log forwarder in `sensor/`.

---

## 3. Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 or newer |
| API | FastAPI and Uvicorn |
| Validation | Pydantic |
| Storage | SQLite |
| Frontend | HTML, CSS, JavaScript, WebSockets |
| Packet metadata capture | Scapy (cross-platform) |
| Windows capture backend | Npcap |
| Linux capture backend | Compatible libpcap/packet-capture backend and appropriate privileges |
| Optional sensor | Zeek JSON log forwarder |

---

## 4. Architecture

```
Windows/Linux computer                         Team-owned web application
  Scapy sensor                                  security-event helper
  (TCP SYN + DNS metadata)                       (auth failures, HTTP metadata)
           |                                                |
           +---------------------- HTTPS/HTTP API -----------+
                                  |
                           FastAPI ingestion
                                  |
                         Event validation/storage
                                  |
                          Rule-based detection
                                  |
                            SQLite database
                                  |
                    WebSocket + REST API endpoints
                                  |
                        Browser security dashboard
```

### Data flow in plain language
1. The Scapy sensor (network) and the web app helper (application) send events to `POST /api/events`.
2. FastAPI validates each event with Pydantic and stores it in SQLite.
3. The rule engine evaluates the new event against recent events. A match creates an alert.
4. New events and alerts are pushed to connected dashboards over WebSocket. The dashboard also reads history through REST endpoints.

---

## 5. Repository Structure

```
CYBER-MI6/
├── app/                    # FastAPI API, event models, storage, detection rules
├── web/                    # Browser dashboard
├── collectors/
│   └── scapy_collector.py  # Native Windows/Linux metadata sensor
├── sensor/                 # Optional Zeek JSON log forwarder
├── tools/                  # Synthetic event generator
├── examples/               # Own-web-application event reporting example
├── docs/
│   ├── ARCHITECTURE.md
│   └── TEAM_TASKS.md
├── .env.example
├── requirements.txt
└── README.md
```

### Suggested internals (to agree on in week 1)

```
app/
├── main.py                 # FastAPI app, routes registered, static files, startup
├── config.py               # settings loaded from .env
├── models.py               # Pydantic models: EventIn, Event, Alert, AlertUpdate
├── db.py                   # SQLite connection and table creation
├── storage.py              # insert/query functions for events and alerts
├── routes/
│   ├── events.py           # POST /api/events, GET /api/events
│   ├── alerts.py           # GET /api/alerts, PATCH /api/alerts/{id}
│   ├── stats.py            # GET /api/stats
│   └── ws.py               # WebSocket /ws and connection manager
└── detection/
    ├── engine.py           # runs rules on each new event, creates alerts, dedup
    ├── port_scan.py
    ├── dns_anomaly.py
    ├── auth_failures.py
    └── web_paths.py

web/
├── index.html              # dashboard (live feed, stats, alerts)
├── alert.html              # alert detail (optional, can be a modal)
├── css/
│   └── style.css
└── js/
    ├── api.js              # fetch wrapper
    ├── ws.js               # WebSocket client with reconnect
    ├── dashboard.js        # rendering feed, tiles, charts
    └── alerts.js           # alert table, filters, status actions

tests/                      # suggested addition: unit tests for rules and API
```

Keep detection rules in separate files so each can be tested and tuned on its own. Do not commit the SQLite database file, `.env`, or virtual environments.

---

## 6. Backend Specification

### 6.1 Event format

Every event shares common fields; the `type` decides which extra fields are used.

| Field | Description |
|---|---|
| `type` | `network_connection`, `dns_query`, `auth_failure`, `http_request` |
| `timestamp` | UTC, ISO 8601 |
| `source` | Name of the sensor or application that reported it |
| `src_ip` | Source IP |
| `dst_ip` | Destination IP (network events) |
| `dst_port` | Destination port (`network_connection`) |
| `protocol` | `tcp` for the SYN sensor |
| `dns_name` | Queried name (`dns_query`) |
| `username` | Account name or identifier (`auth_failure`) |
| `http_method`, `http_path`, `http_status` | Request metadata (`http_request`) |
| `user_agent` | Optional |
| `details` | Optional small object for extra context |

Rules for events:
- **No packet payloads, request bodies, passwords, cookies, or tokens.** Metadata only.
- Reject oversized or malformed events with a clear 422 response.
- Redact query strings from `http_path` before sending.

### 6.2 API endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/events` | Ingest and validate an event (or a small batch). Requires the ingestion API key |
| GET | `/api/events` | Recent events with filters: `type`, `src_ip`, `from`, `to`, `limit` |
| GET | `/api/alerts` | Alerts with filters: `severity`, `status`, `rule`, `limit` |
| GET | `/api/alerts/{id}` | Alert detail with evidence events |
| PATCH | `/api/alerts/{id}` | Change status (`new`, `investigating`, `resolved`, `false_positive`) |
| GET | `/api/stats` | Counts for the dashboard (events, alerts by severity, top source IPs) |
| WS | `/ws` | Live stream of new events and alerts |
| GET | `/docs` | Auto-generated OpenAPI documentation (the API contract) |

Example ingestion request:
```http
POST /api/events
X-API-Key: <value from .env>
Content-Type: application/json

{
  "type": "network_connection",
  "timestamp": "2026-10-19T09:15:02Z",
  "source": "laptop-sensor-1",
  "src_ip": "192.168.1.25",
  "dst_ip": "192.168.1.1",
  "dst_port": 445,
  "protocol": "tcp"
}
```

Example WebSocket message:
```json
{ "kind": "alert", "data": { "id": 17, "rule": "port_scan", "severity": "medium",
  "title": "Possible port scan from 192.168.1.25", "status": "new" } }
```

### 6.3 Database (SQLite)

| Table | Key columns |
|---|---|
| `events` | id, type, timestamp, source, src_ip, dst_ip, dst_port, dns_name, username, http_path, details (JSON) |
| `alerts` | id, created_at, rule, severity, title, status, src_ip, evidence_event_ids (JSON), count, updated_at |
| `alert_notes` (optional) | id, alert_id, note, created_at |

- Add indexes on `timestamp`, `src_ip`, and `type`.
- Enable WAL mode for better concurrent reads while writing.
- Add a retention job that deletes events older than a configured number of days.

### 6.4 Sensor: Scapy collector (`collectors/scapy_collector.py`)

- Sniffs on a chosen interface using Scapy with a BPF filter.
- Reports **initial TCP SYN** packets (SYN set, ACK not set) as `network_connection` events: source IP, destination IP, destination port.
- Reports **DNS query names** as `dns_query` events.
- Never stores or sends payloads.
- Batches events and sends them to the API with retry and backoff; if the API is down, keeps a small bounded buffer and drops the oldest.
- Command-line options (suggested): `--iface`, `--api-url`, `--api-key`, `--source-name`, `--list-ifaces`.
- **Windows:** install Npcap (WinPcap API-compatible mode) and run the terminal as Administrator.
- **Linux:** install libpcap and run with `sudo`, or grant `CAP_NET_RAW` to the Python binary.
- Sees only traffic the chosen computer/interface can observe. Packet loss or interface visibility can affect results.

### 6.5 Optional Zeek forwarder (`sensor/`)

Reads Zeek JSON `conn.log` and `dns.log` and converts them into the same event format. Build this only after the Scapy sensor works.

### 6.6 Tools and examples

- **`tools/send_demo_events.py`:** sends synthetic events (normal traffic plus scenarios: port scan, long DNS label, repeated login failures, suspicious paths) so the whole system can be tested safely without real traffic.
- **`examples/webapp_event_reporting.py`:** a small helper that a team-owned web app imports to report `auth_failure` and `http_request` events to the API (non-blocking, with timeouts so the app never slows down if CYBER-MI6 is down).

---

## 7. Frontend Specification

### 7.1 Dashboard (`web/`)

Plain HTML, CSS, and JavaScript. FastAPI serves the files, so the dashboard and API share one origin.

| Section | Contents |
|---|---|
| **Header** | CYBER-MI6 name, connection status (WebSocket connected or disconnected) |
| **Stat tiles** | Events today, alerts by severity, open alerts, top source IP |
| **Live activity feed** | New events and alerts appear instantly via WebSocket |
| **Alert history** | Table with severity, rule, title, source IP, time, status. Filters by severity, status, rule |
| **Alert detail** | Explanation of why the rule fired, thresholds, evidence events, status buttons |
| **Recent events** | Table of recent events with a type filter |

### 7.2 Behavior and UI rules

- `ws.js` reconnects automatically with backoff and falls back to polling `/api/alerts` every 10 seconds when the socket is down.
- Severity: low = green, medium = amber, high = orange, critical = red, always with a text label (not color alone).
- **Insert API data with `textContent`, never `innerHTML`.** Domains, paths, usernames, and user agents are attacker-controlled strings.
- Loading, empty, and error states on every table.
- Responsive layout that works on a laptop and a phone browser.
- Status changes call `PATCH /api/alerts/{id}` and update the row immediately.
- Design source is Canva; exports go in `docs/` or a `web/assets/` folder.

---

## 8. Detection Rules and Limitations

Rules are transparent: each alert states which rule fired, the threshold, and the evidence events. Thresholds are starting values stored in config and tuned with real data.

| Rule | How it works (starting values) | Limitation |
|---|---|---|
| **Possible port scan** | Many distinct destination ports (for example 20 or more) from one source within a time window (for example 30 seconds) | A heuristic, not proof of malicious intent. The Scapy sensor reports initial TCP SYN attempts, and packet loss or interface visibility can affect results |
| **DNS anomaly** | Flags unusually long (for example 40 or more characters) or high-entropy DNS labels | CDNs and legitimate encoded names can trigger false positives |
| **Repeated authentication failures** | For example 5 or more failures for one IP or username within 5 minutes | Requires events sent by our own instrumented application |
| **Suspicious web request path** | Simple pattern matching on paths such as `../`, `/etc/passwd`, `/.env`, `/phpmyadmin`, and common SQL injection or script fragments | Requires application events. HTTPS packet capture alone cannot reveal encrypted paths |

**Alert behavior**
- **Severity:** low, medium, high, critical, assigned per rule and escalated by count.
- **Deduplication:** the same rule and source IP within a cooldown window updates one alert (count increases) instead of creating many.
- **Status:** `new`, `investigating`, `resolved`, `false_positive`.
- **Explainability:** every alert stores the rule name, the numbers that triggered it, and the supporting event IDs.

---

## 9. Team Structure and Tasks (6 Members)

**4 backend and 2 frontend.** Each member owns specific files to reduce merge conflicts.

| # | Role | Side | Owns |
|---|---|---|---|
| 1 | API and Storage Lead | Backend | `app/` (main, models, db, storage, routes, websocket), `.env.example`, `requirements.txt` |
| 2 | Sensor Engineer | Backend | `collectors/scapy_collector.py`, `sensor/` |
| 3 | Detection Engineer | Backend | `app/detection/` and detection tests |
| 4 | Integration and Test Engineer | Backend | `tools/`, `examples/`, `tests/`, sample web app for testing |
| 5 | Dashboard Lead | Frontend | `web/` (HTML, JS) |
| 6 | UI/UX and Documentation | Frontend | Canva designs, `web/css/`, `docs/`, README, demo and slides |

### Member 1: API and Storage Lead (Backend)
**Goal:** a stable ingestion API and data layer everyone builds on.
- [ ] Set up repo, `requirements.txt`, `.env.example`, `.gitignore`, and the folder structure
- [ ] Define Pydantic models for events, alerts, and updates in `models.py` (agree on fields with the team in week 1)
- [ ] Create SQLite tables, indexes, and WAL mode in `db.py`; write insert/query functions in `storage.py`
- [ ] Implement `POST /api/events` with validation, size limits, and API key check
- [ ] Implement `GET /api/events`, `GET /api/alerts`, `GET /api/alerts/{id}`, `PATCH /api/alerts/{id}`, `GET /api/stats`
- [ ] Implement the WebSocket endpoint and connection manager; broadcast new events and alerts
- [ ] Call the detection engine after each stored event and save/broadcast the alerts it returns
- [ ] Serve `web/` as static files from FastAPI
- [ ] Add rate limiting on ingestion and an event retention cleanup job
- **Deliverable:** by end of week 1 to 2, a running API with `/docs` and demo data so frontend and detection can start. Provide a stub detection interface first.

### Member 2: Sensor Engineer (Backend)
**Goal:** reliable, safe network metadata from a real Windows or Linux computer.
- [ ] Build `scapy_collector.py`: interface selection, `--list-ifaces`, BPF filter
- [ ] Capture initial TCP SYN packets and DNS query names; convert to the event format
- [ ] Guarantee no payloads are stored or sent
- [ ] Batch and send events to the API with API key, timeouts, retry, backoff, and a bounded buffer
- [ ] Handle errors cleanly (missing Npcap, no privileges, wrong interface) with helpful messages
- [ ] Test on both Windows (Npcap, Administrator) and Linux (libpcap, sudo or `CAP_NET_RAW`)
- [ ] Write setup instructions for both platforms in `docs/`
- [ ] Optional after the sensor works: Zeek JSON log forwarder in `sensor/`
- **Deliverable:** run the sensor on a team laptop, scan a team-owned test machine, and see events arrive in the API.

### Member 3: Detection Engineer (Backend)
**Goal:** explainable, tunable rules.
- [ ] Build `engine.py`: receive a new event, run relevant rules against recent events, create or update alerts, deduplicate with a cooldown
- [ ] Implement `port_scan.py` (distinct ports per source in a time window)
- [ ] Implement `dns_anomaly.py` (label length and Shannon entropy)
- [ ] Implement `auth_failures.py` (failures per IP or username in a window)
- [ ] Implement `web_paths.py` (pattern list for traversal, sensitive files, admin panels, injection fragments)
- [ ] Put all thresholds and patterns in config so they can be tuned without code changes
- [ ] Store the explanation (rule, thresholds, counts) and evidence event IDs in every alert
- [ ] Write unit tests: each rule has a should-fire case and a should-not-fire case
- [ ] Document each rule, its thresholds, and known false positives in `docs/ARCHITECTURE.md`
- **Deliverable:** four working rules with tests by week 4; tuned thresholds by week 6.

### Member 4: Integration and Test Engineer (Backend)
**Goal:** safe, repeatable testing and the web app event source.
- [ ] Build `tools/send_demo_events.py`: normal traffic plus scenarios (port scan, long DNS label, repeated login failures, suspicious paths) with options for rate and scenario
- [ ] Build `examples/webapp_event_reporting.py`: a helper that reports auth failures and HTTP metadata without blocking the app and with path redaction
- [ ] Build a tiny team-owned test web app (login form plus a few routes) that uses the helper
- [ ] Write API tests (valid, invalid, oversized, missing key) and end-to-end tests: event in, alert out, WebSocket message received
- [ ] Set up CI (GitHub Actions) to run lint and tests
- [ ] Create the final demo scenario script for the presentation
- [ ] Track false positives from real test runs and feed them to Member 3
- **Deliverable:** one command that produces a full demo of all four detections.

### Member 5: Dashboard Lead (Frontend)
**Goal:** the live dashboard.
- [ ] Build `api.js` (fetch wrapper, error handling) and `ws.js` (WebSocket with auto-reconnect and polling fallback)
- [ ] Build the stat tiles and the live activity feed
- [ ] Build the alert history table with filters (severity, status, rule) and pagination
- [ ] Build alert detail: explanation, thresholds, evidence events, status buttons that call `PATCH`
- [ ] Build the recent events table with a type filter
- [ ] Render all data with `textContent`; add loading, empty, and error states
- [ ] Show WebSocket connection status in the header
- [ ] Work against demo data from week 1
- **Deliverable:** full dashboard working on demo data by week 3, then on real sensor data.

### Member 6: UI/UX and Documentation (Frontend)
**Goal:** a consistent design and a clear presentation.
- [ ] Define the style kit (colors, font, spacing, severity palette) and make Canva mockups for the dashboard and alert detail
- [ ] Write `style.css` (layout, cards, badges, tables, buttons, dark theme) for Member 5 to use
- [ ] Responsive and accessibility checks (contrast, labels, keyboard navigation)
- [ ] Write `docs/ARCHITECTURE.md` (diagram, data flow, event format, rules) and `docs/TEAM_TASKS.md`
- [ ] Write setup guides for Windows and Linux and keep the README current
- [ ] Prepare the slides, demo script, and screenshots
- [ ] Write the authorized-use and privacy notes
- **Deliverable:** style kit and mockups in week 1 to 2, CSS by week 2, docs and slides by week 7.

### Cross-team responsibilities
- Every pull request gets one review from another member.
- Everyone writes tests for their own code.
- Weekly 30-minute sync: demo, blockers, next steps.
- **Week 1 agreements:** event format and API contract (Members 1, 2, 3, 4, 5) and the style kit (Member 6, 5).

### Dependencies
```
Week 1:  M1 API + demo data ──────────► M5 dashboard starts
         M1 models agreed ────────────► M2 sensor, M3 rules, M4 tools
         M6 style kit ────────────────► M5 CSS
Week 2+: M4 demo events ──► M3 tunes rules ──► M1 alerts ──► M5 live feed
         M2 real sensor events ───────────────► final demo
```

---

## 10. Timeline

About 8 weeks. The MVP is demonstrable by week 5.

| Week | Milestone |
|---|---|
| 1 | Repo, structure, event format, API contract, models, demo events, style kit |
| 2 | `POST /api/events` and SQLite working, sensor prints events, dashboard skeleton, demo generator |
| 3 | WebSocket live feed, port scan and DNS rules, dashboard feed and alert table |
| 4 | Auth failure and web path rules, web app helper and test app, alert detail and status actions |
| 5 | **MVP demo:** real sensor on a team laptop plus the test web app, alerts live on the dashboard |
| 6 | Tune thresholds, fix false positives, retention job, rate limiting, UI polish |
| 7 | Windows and Linux testing, docs, setup guides, optional Zeek forwarder |
| 8 | Final testing, slides, rehearsal, final demo |

---

## 11. Getting Started

### Prerequisites
- Python 3.11 or newer
- Windows: [Npcap](https://npcap.com) (WinPcap API-compatible mode)
- Linux: libpcap and permission to capture (`sudo` or `CAP_NET_RAW`)
- A modern browser

### Install and run the API (Windows and Linux)
```bash
git clone <repo-url> CYBER-MI6
cd CYBER-MI6

python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# Linux/macOS:           source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
uvicorn app.main:app --reload
```
Open the dashboard at http://localhost:8000 and the API docs at http://localhost:8000/docs.

### Send safe demo events
```bash
python tools/send_demo_events.py
```
Add options (suggested) such as `--scenario port_scan` to run one scenario.

### Run the Scapy sensor (own computer or network only)
```bash
# Linux
sudo .venv/bin/python collectors/scapy_collector.py --list-ifaces
sudo .venv/bin/python collectors/scapy_collector.py --iface eth0 --api-url http://localhost:8000

# Windows (terminal as Administrator, Npcap installed)
python collectors\scapy_collector.py --list-ifaces
python collectors\scapy_collector.py --iface "Wi-Fi" --api-url http://localhost:8000
```

### Report events from your own web app
Import the helper from `examples/webapp_event_reporting.py` and call it on login failures and requests. See the file for a short usage example.

### Configuration (`.env`)
| Variable | Purpose |
|---|---|
| `API_KEY` | Key required by sensors and apps sending events |
| `DATABASE_PATH` | SQLite file location (default `data/cybermi6.db`) |
| `EVENT_RETENTION_DAYS` | How long events are kept |
| `PORT_SCAN_PORTS`, `PORT_SCAN_WINDOW_SECONDS` | Port scan thresholds |
| `DNS_MAX_LABEL_LENGTH`, `DNS_MIN_ENTROPY` | DNS anomaly thresholds |
| `AUTH_FAIL_COUNT`, `AUTH_FAIL_WINDOW_SECONDS` | Authentication failure thresholds |
| `ALERT_COOLDOWN_SECONDS` | Deduplication window |
| `ALLOWED_ORIGINS` | CORS origins if the dashboard is hosted separately |

Never commit `.env`.

---

## 12. Testing and Definition of Done

### Test levels
| Level | What |
|---|---|
| Unit | Each rule (fire and no-fire cases), entropy function, models validation |
| API | Valid, invalid, oversized events; missing or wrong API key; filters on `GET` endpoints |
| End to end | Demo event generator to API to alert to WebSocket message on the dashboard |
| Sensor | Manual test on Windows and Linux against a team-owned machine |
| Frontend | Checklist per section, error states when the API is down |

### Definition of done
- Merged through a reviewed pull request
- Tests added and passing in CI
- Docs updated if behavior, config, or API changed
- No secrets or database files committed
- Works with demo events and with real sensor events

### MVP acceptance checklist
- [ ] `POST /api/events` validates and stores events; bad input returns a clear error
- [ ] A simulated port scan creates a "possible port scan" alert
- [ ] A long or high-entropy DNS label creates a DNS anomaly alert
- [ ] Repeated login failures on the test web app create an alert
- [ ] A suspicious path request creates a web path alert
- [ ] Alerts and events appear live on the dashboard without refreshing
- [ ] An alert's status can be changed from the dashboard and persists
- [ ] The sensor runs on both Windows and Linux without storing payloads
- [ ] Requests without a valid API key are rejected

---

## 13. Security and Privacy Rules

- **Authorized use only.** Monitor only systems and networks the team owns or has explicit permission to monitor. Do not capture other people's traffic.
- **Metadata only.** The sensor sends source, destination, port, and DNS names. No payloads, bodies, cookies, passwords, or tokens.
- Redact query strings in `http_path` before sending.
- DNS names can reveal browsing habits. Keep retention short and do not share the database.
- Require an API key on ingestion; keep keys in `.env`, not in code.
- Validate all input with Pydantic and cap batch and field sizes.
- Use parameterized SQL only.
- Treat all event fields as untrusted. The dashboard must escape or use `textContent`.
- Bind the API to `localhost` by default; expose it on a network only deliberately, and use HTTPS if the API leaves the machine.
- Do not run the sensor against, or generate attack-like traffic toward, systems you do not own. The demo generator sends events directly to the API, so it needs no real attacks.

---

## 14. Git Workflow

- **Branches:** `main` is protected. Use `feature/<area>-<description>` and `fix/<description>`.
- **Commits:** conventional style, for example `feat(detection): add dns anomaly rule`.
- **Pull requests:** small, one purpose, one reviewer from another member, CI green.
- **Code style:** Python with `ruff` and `black`; JavaScript with `eslint` and `prettier`.
- **Planning:** GitHub Issues and a Projects board (Backlog, In progress, In review, Done), labeled `api`, `sensor`, `detection`, `testing`, `dashboard`, `docs`.
- **Decisions:** record anything affecting more than one person in `docs/ARCHITECTURE.md`.

---

## 15. After the MVP

Only after the rules are working and tuned:

1. Optional Zeek JSON forwarder (`sensor/`) for richer `conn.log` and `dns.log` data
2. Beaconing detection (regular repeated connections) and data exfiltration indicators (unusual outbound volume)
3. Threat intelligence matching (known-bad IPs and domains)
4. Per-host baselines, then an Isolation Forest anomaly model, trained and validated on collected data
5. Notifications (Slack or email) for high-severity alerts
6. Login and roles for the dashboard
7. Move from SQLite to PostgreSQL if concurrent use or volume grows
8. Suricata or WAF event ingestion
9. Mobile triage app

---

## 16. Glossary

| Term | Meaning |
|---|---|
| **Scapy** | Python library for capturing and building network packets |
| **Npcap / libpcap** | Packet capture backends for Windows / Linux |
| **SYN** | First packet of a TCP connection attempt |
| **Port scan** | Probing many ports on a host to find open services |
| **DNS label** | One dot-separated part of a domain name |
| **Entropy** | Randomness measure; high values suggest generated or encoded names |
| **WebSocket** | Persistent connection that lets the server push live updates to the browser |
| **SQLite** | File-based database, no separate server needed |
| **BPF filter** | Packet filter expression used by capture tools |
| **WAL mode** | SQLite journal mode that allows reads during writes |
| **Deduplication** | Merging repeated detections into one alert |
| **False positive** | An alert for harmless activity |
| **Zeek** | Network analysis tool that writes structured logs |

---


