# FLOODGUARD AI

FLOODGUARD AI is a hyperlocal flood-awareness and emergency response platform. The project includes a Vite React dashboard, a Django REST API, and a PyMongo connection to MongoDB Atlas. Citizen flood reporting, a preliminary weather-based flood-risk indicator, safe route assessments, emergency-resource directory, flood-alert centre, and the emergency assistant are available. The Alerts page checks the official NDMA SACHET Odisha RSS feed through Django. Emergency dispatch and guaranteed notifications are not implemented.

## Requirements

- Node.js 20.19+ or 22.12+
- Python 3.12

## Technology stack

- Frontend: React, Vite, and CSS.
- Backend: Python, Django, and Django REST Framework.
- Data: MongoDB Atlas through PyMongo; SQLite is used only for Django framework defaults.
- Providers: Open-Meteo weather/geocoding, OSRM routing, OpenStreetMap maps, NDMA SACHET Odisha RSS, and Google's `google-genai` SDK for the emergency assistant.

## System architecture

```text
React + Vite browser application
  ├─ FLOODGUARD API requests ───────────────> Django + Django REST Framework
  │                                              ├─ PyMongo ──> MongoDB Atlas
  │                                              ├─ Weather/geocoding ──> Open-Meteo
  │                                              ├─ Driving routes ─────> OSRM public service
  │                                              ├─ Odisha RSS alerts ──> NDMA SACHET
  │                                              └─ Emergency assistant -> Gemini API
  │                                                                     └─ curated fallback
  └─ Map tile requests ─────────────────────> OpenStreetMap tile service
```

The browser renders the dashboard and feature pages. Django validates API requests, calls the external weather, geocoding, routing, SACHET RSS, and (when configured) Gemini providers, and reads or writes operational records through PyMongo. MongoDB collections and indexes are prepared when the database is first reached; this setup does not seed facility or alert documents. Route maps use OSRM geometry displayed over OpenStreetMap tiles. The risk indicator is computed by backend weather heuristics, not by a trained model. React never fetches the SACHET feed directly.

The Emergency Resources and Flood Alerts modules use MongoDB-backed API records. Staff-managed resource and official-alert writes are protected by Django staff authentication. Empty or unavailable data is shown as such rather than populated with invented records. The SQLite database is retained only for Django framework defaults.

## Environment configuration

Copy the example files for local development. They contain placeholders, not credentials:

- `backend/.env`: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `MONGODB_URI`, `MONGODB_DATABASE`, `GEMINI_API_KEY`, and `GEMINI_MODEL`.
- `frontend/.env`: `VITE_API_BASE_URL` only. Never put backend credentials in a `VITE_` variable.

The root `.gitignore` excludes `.env` and `.env.*` while allowing `.env.example`. The workspace currently has no Git repository metadata, so tracked-file status cannot be independently checked here. Keep real environment files private and use a secrets manager in deployment.

## Frontend

```powershell
cd frontend
npm ci
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
npm run dev
```

Vite serves the app at `http://localhost:5173`. The frontend reads `VITE_API_BASE_URL` from `frontend/.env` and checks the API at `/api/health/`.

## Backend

In a second terminal, from the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
$env:DJANGO_SECRET_KEY = python -c "import secrets; print(secrets.token_urlsafe(50))"
$env:DJANGO_DEBUG = "true"
python manage.py runserver
```

The API serves at `http://127.0.0.1:8000`. Django loads `backend/.env` automatically. Keep your Atlas URI and database name there; do not place them in the frontend. Verify API and database readiness with:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health/
Invoke-RestMethod http://127.0.0.1:8000/api/health/database/
```

Expected response:

```json
{"status":"ok","service":"floodguard-api"}
```

The database health endpoint returns HTTP 200 when Atlas is reachable and HTTP 503 when it is unavailable or unconfigured. On the first successful database health check, the backend prepares `flood_reports`, `emergency_resources`, `risk_assessments`, `weather_records`, `route_assessments`, `flood_alerts`, `user_notifications`, `users`, and `chat_history` collections with their query indexes. It does not seed documents automatically; curated facility records are added only by the explicit management command described below. GeoJSON indexes expect a `location` field shaped as `{ "type": "Point", "coordinates": [longitude, latitude] }`.

`backend/.env.example` documents backend settings, and `frontend/.env.example` documents the public API base URL. The backend reads the existing `.env` without overriding variables already set in the process. Keep that file private and generate a new `DJANGO_SECRET_KEY` for each environment. Never place backend credentials in frontend variables.

If you want Django to use the MongoDB values from `backend/.env` and your current PowerShell session has different MongoDB values exported, clear those session overrides before starting Django:

```powershell
Remove-Item Env:MONGODB_URI, Env:MONGODB_DATABASE -ErrorAction SilentlyContinue
```

The backend CORS allowlist defaults to `http://localhost:5173` and `http://127.0.0.1:5173` for local development; set `CORS_ALLOWED_ORIGINS` to a comma-separated list to change it. Do not use these local origins in production. Django's SQLite database remains only for framework defaults; application data is accessed through PyMongo.

MongoDB uses `MONGODB_DATABASE` when it is set. Otherwise, the backend uses the database name in the path portion of `MONGODB_URI` (for example, `/floodguard_ai`). If the URI has no database path, set `MONGODB_DATABASE` explicitly.

### Production environment

Set production values in the hosting platform's environment or secrets manager. Do not copy a developer `.env` file into a production image. The process environment takes precedence over `backend/.env`.

```dotenv
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=api.your-domain.example
CORS_ALLOWED_ORIGINS=https://app.your-domain.example
DJANGO_SECURE_SSL_REDIRECT=<configure-for-your-HTTPS-proxy>
DJANGO_SECURE_HSTS_SECONDS=<set-after-HTTPS-verification>
DJANGO_SECRET_KEY=<unique-generated-secret>
MONGODB_URI=<production-mongodb-uri-secret>
MONGODB_DATABASE=<production-database-name>
GEMINI_API_KEY=<gemini-api-key-secret>
GEMINI_MODEL=<model-enabled-for-your-project>
```

Replace every placeholder with the actual deployment value; the `.example` hostnames above are documentation-only. `DJANGO_ALLOWED_HOSTS` takes backend hostnames only (no scheme or path). `CORS_ALLOWED_ORIGINS` takes the exact frontend origin(s), including `https://` and any non-default port, but no path; separate multiple origins with commas. Do not use wildcard hosts or origins. Production startup requires explicit `DJANGO_ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` and rejects wildcard or localhost/loopback entries. Keep local development working by retaining `DJANGO_DEBUG=true` and local CORS origins only in the ignored `backend/.env`; set `DJANGO_DEBUG=false` in the production process environment.

Configure the frontend separately with `VITE_API_BASE_URL=https://api.your-domain.example`. This is a public API URL, not a credential. Never put `DJANGO_SECRET_KEY`, `MONGODB_URI`, or `GEMINI_API_KEY` in any `VITE_` variable or frontend build input. This repository has no deployment domain configured yet, so replace the example origins with the actual frontend and API domains before release.

When `DJANGO_DEBUG=false`, session and CSRF cookies are marked secure. Django's HTTPS redirect is opt-in because it depends on whether TLS terminates in Django or at a trusted reverse proxy; configure `DJANGO_SECURE_SSL_REDIRECT` only after that topology is known. HSTS is disabled by default (`DJANGO_SECURE_HSTS_SECONDS=0`); set a positive duration only after confirming HTTPS works for every affected host and subdomain. `manage.py check --deploy` reports these transport-level settings for review.

## API overview

The frontend calls Django for application data; provider credentials remain backend-only.

| API | Purpose |
| --- | --- |
| `GET /api/health/`, `GET /api/health/database/` | API liveness and MongoDB readiness |
| `GET /api/alerts/sachet/` | Backend-refreshed official SACHET Odisha RSS entries and feed/cache status |
| `GET /api/weather/`, `GET /api/weather/locations/` | Open-Meteo weather and geocoding |
| `GET /api/reports/`, `POST /api/reports/`, `GET /api/reports/<id>/` | Citizen reports; new reports are always pending |
| `GET /api/risk/assess/` | Preliminary weather-based risk heuristic |
| `POST /api/routes/safe-route/` | OSRM route plus available report/weather context |
| `GET /api/resources/`, `/api/resources/categories/`, `/api/resources/<id>/` | Manually managed directory |
| `GET /api/alerts/`, `/api/alerts/<id>/`, `POST /api/alerts/mark-read/` | Active notices and browser-scoped read receipts |
| `POST /api/assistant/emergency/` | Gemini when a live request succeeds; otherwise curated flood-safety guidance |

Resource and official-alert write operations require a Django staff user. MongoDB-backed endpoints return service-unavailable errors when the database cannot be reached; a reachable but empty collection is returned as an empty result.

## Citizen flood reports

The Reports page uses the backend API directly and shows an explicit error if the service is unreachable; it does not fall back to demo reports. The API supports:

- `POST /api/reports/` to create a report (JSON or multipart form data).
- `GET /api/reports/` to list newest reports, with optional `severity`, `status`, `limit` (1–100), and `offset` filters.
- `GET /api/reports/<report_id>/` to retrieve a report by its UUID.

Required submission fields are `location_name`, `latitude`, `longitude`, `severity` (`low`, `moderate`, `high`, or `critical`), and `description`. `water_level` and a JPEG, PNG, or WebP photo are optional. Photos are limited to 5 MiB and saved to local `backend/media/` storage with generated filenames. Django serves these files only in `DEBUG` mode. Production deployments need persistent media storage and a web server/object store configured for media delivery; request-size limits should also be enforced at the reverse proxy. New reports always have `pending` status, and client-supplied status is rejected. No test or demo reports are inserted into Atlas.

The report collection uses indexes for newest-first creation time, severity/status plus creation time, and GeoJSON `location`. Report documents store coordinates as `[longitude, latitude]` in a GeoJSON Point. Run backend tests and dependency validation from `backend/`:

```powershell
.\.venv\Scripts\python.exe manage.py test api.tests
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe -m pip check
```

## Live weather

The Overview page selects locations through the backend's Open-Meteo geocoder and retrieves model-based current conditions and forecasts through Django. Open-Meteo's free non-commercial endpoints require no API key. The backend uses an 8-second request timeout and returns provider failures as HTTP 502. Current conditions are model-based and may not match ground-station observations. The provider-local timestamp and application fetch timestamp are displayed separately. Forecast precipitation is labelled as forecast data; weather alone does not confirm flooding.

Weather endpoints:

- `GET /api/weather/?latitude=20.2961&longitude=85.8245` retrieves current, 24-hour hourly, and 7-day daily data. Optional `timezone` and `location_name` query parameters carry the selected geocoder result into the forecast and stored snapshot.
- `GET /api/weather/locations/?q=Bhubaneswar` searches for up to eight locations and returns name, region, country, coordinates, country code, and timezone.

The backend requests temperature in °C, precipitation in mm, and wind speed in km/h. Successful responses are saved in `weather_records`; repeated requests for the same rounded coordinates within ten minutes do not insert another snapshot, while the response still contains newly fetched provider data. MongoDB storage failures return HTTP 503 with the weather response and explicit unsaved status. The collection index covers latitude, longitude, and `fetched_at`. Atlas must be reachable for successful weather API responses.

No extra backend dependency was added for HTTP requests; the weather service uses Python's standard library. Open-Meteo is attributed in the weather panel. Run the mocked weather and report API tests with `backend/.venv/Scripts/python.exe manage.py test api.tests`; tests do not write sample weather to Atlas.

Run frontend weather state and WMO mapping tests from `frontend/` with `npm test`; create a production bundle with `npm run build`.

## Preliminary weather-based risk indicator

The AI Flood Risk page calls `GET /api/risk/assess/?latitude=20.2961&longitude=85.8245&location=Bhubaneswar` (optional `timezone` is accepted). Django reuses the Task 5 Open-Meteo client and evaluates current precipitation, available hourly precipitation in the next 6 and 24 hours, and maximum available hourly precipitation probability in the next 24 hours. Provider or malformed-weather errors return HTTP 502. Missing measurements are omitted, never imputed; stale weather (>3 hours from provider current time or >15 minutes since fetch) and unavailable inputs do not receive a risk score.

The indicator uses a configurable heuristic: current precipitation has a maximum of 25 points (<0.1 mm: 0; <2: 5; <10: 15; otherwise 25); next-6-hour rain has 35 points (<1 mm: 0; <5: 7; <20: 18; <50: 27; otherwise 35); next-24-hour rain has 30 points (<5 mm: 0; <20: 8; <50: 18; otherwise 30); and precipitation probability has 10 points (<30%: 0; <50%: 3; <70%: 6; <85%: 8; otherwise 10). The score is the earned points divided by the maximum points of available factors, scaled to 0–100. Bands are Low (<20), Moderate (20–39), High (40–69), and Very High (70–100). The exact thresholds and weights are in `backend/api/services/risk_assessment.py`.

These simple thresholds are not scientifically validated flood thresholds, do not account for terrain, drainage, river levels, soil saturation, or local impacts, and are not an ML model or an official flood warning. This is only a preliminary weather-based indicator; use official local authority guidance for emergencies. Fresh risk snapshots are best-effort writes to the existing `risk_assessments` collection and identical assessment data at the same location is deduplicated for ten minutes. A MongoDB persistence failure does not prevent returning an assessment and is reported in its `snapshot` status.

Backend tests (including risk assessment, stale/missing provider data, API errors, and mocked snapshot persistence) use mocked provider/database calls and do not write test records to Atlas:

```powershell
.\.venv\Scripts\python.exe manage.py test api.tests
.\.venv\Scripts\python.exe manage.py check
```

## Safe Route Finder

The sidebar's Safe Route Finder searches locations through the existing Open-Meteo geocoder. It requests browser location only when the user explicitly selects **Use my current location**. The map uses OpenStreetMap tiles and the backend requests driving geometry, provider-estimated distance and duration, and up to two alternatives from OSRM.

The route API is:

```http
POST /api/routes/safe-route/
Content-Type: application/json
```

Example request:

```json
{
  "origin": { "latitude": 20.2961, "longitude": 85.8245 },
  "destination": { "latitude": 19.8135, "longitude": 85.8312 }
}
```

The endpoint validates finite latitude/longitude ranges and returns the OSRM route geometry as GeoJSON, distance in metres and kilometres, estimated duration, alternatives, risk classification, available evidence, and data-source limitations. It reuses the Task 5 Open-Meteo client and Task 6 weather-risk assessment at up to three route points. It checks up to the 100 newest reports marked `verified` in `flood_reports`, and flags verified reports within 500 metres of the route. Pending or rejected reports are never shown as verified observations.

Route risk is **High** when a verified report is near the route or an available sampled weather indicator is High/Very High; **Moderate** when a sampled weather indicator is Moderate; **Low** only when all sampled weather assessments are Low and the verified-report query is complete; otherwise it is **Unknown**. If the database has more than 100 verified reports, only the 100 newest are checked and a route with no match is classified Unknown. These are transparent heuristics, not an AI/ML prediction. Weather is model-based and sampled at only a few points; reports may be absent, old, or geographically sparse. An absence of reports does not establish safety. OSRM alternatives are displayed as not separately risk-assessed.

OSRM's public demo routing service and OpenStreetMap's public tile service may impose availability and usage limits; their route/time estimates do not verify live closures or flooding. The public OSRM endpoint receives the submitted coordinates. Use a properly provisioned routing service for production usage. The frontend displays this warning: “Route suggestions are informational and may not reflect current road closures or rapidly changing flood conditions. Follow official evacuation instructions and avoid entering floodwater.”

Assessments are saved best-effort to MongoDB's `route_assessments` collection with origin/destination coordinates, assessment time, route distance/duration, risk class/factors, and provider names only. No account or personal identity is collected. If MongoDB cannot be reached, the route response includes `history.status: "unavailable"` and the page explains that the history was not saved; route planning still returns with its flood-data status marked unavailable where applicable. No additional backend environment variables are required; the frontend uses the existing `VITE_API_BASE_URL`.

Run the API and frontend checks from their respective directories using the commands in the Backend and Frontend sections. Safe-route tests mock OSRM, weather, flood-report storage, and MongoDB; they do not call external providers or write test records to Atlas.

## Emergency resources and flood alerts

The sidebar includes an Emergency Resources directory and a Flood Alerts centre. The dashboard and notification popover use backend responses only; they do not display fabricated facility records or sample notification counts. The existing `emergency_resources` MongoDB collection currently contains eight curated entries: one verified Capital Hospital entry, four unverified CMRF shelter-list entries, and three unverified police-station entries. No facility is claimed to be open or accepting evacuees. An empty or unverified-only directory is shown honestly. The public directory supports search by name and location, category and district filters, verified/unverified filters, detail lookup, and pagination. Only records marked verified with a verification date expose map coordinates, clickable telephone numbers, or published operating hours. Operating hours, contacts, and capacity are not live availability checks.

### Emergency resource API

- `GET /api/resources/` lists active physical facilities. Optional query parameters: `category`, `district`, `search`, `verification_status`, `is_active` (`true`/`false`), `limit` (1–100), and `offset`. Public responses always omit inactive records; requesting `is_active=false` requires staff authentication. Legacy helpline-category records remain in MongoDB but are excluded from the physical-facility API.
- `GET /api/resources/<resource_id>/` returns one record.
- `GET /api/resources/categories/` returns supported categories, districts, total records, and verified-record count.
- `POST /api/resources/` and `PATCH /api/resources/<resource_id>/` are staff-only directory management operations. Supported physical categories include hospitals, fire stations, police stations, multipurpose flood/cyclone shelters, and relief centres. A record can include state, district, block, Gram Panchayat, village, address/location, coordinates, contact, capacity, source, verification date, and active status.
- `python manage.py import_official_facilities` runs a dry run. Add `--apply` to import the curated public-source records. The command is repeatable, uses stable source IDs, creates no network requests, does not delete records, preserves existing verified records, and does not replace existing fields with missing values.

The source review found: (1) the CMRF Odisha page publicly lists 158 MFS/MCS entries; four representative rows were imported as **unverified** because their locations are descriptive and the page does not provide verified coordinates, contacts, capacity, or current operating status; (2) the Government of Odisha emergency page lists Capital Hospital with a phone number and a direct map link, used for the single verified hospital record (the source does not state its district, so that field is blank); (3) the Odisha Police page lists model police station names and districts, but not facility addresses or contacts, so three entries are **unverified**; (4) the OSDMA shelter page was accessible but exposed only district/block selectors, not a facility list in the retrieved page; and (5) ODRN's public page presents a username/password/CAPTCHA login and no public facility data or API was used. The Odisha government page's `112` fire/police number is a helpline, not a station, and was not imported as a facility. No relief-centre records were found in the accessible sources. The populated category set is therefore hospital, police station, multipurpose flood shelter, and multipurpose cyclone shelter; fire station and relief centre categories are supported but empty.

Verification means the listed facility details were checked against the cited source; it does not mean that the facility is open, reachable, or currently accepting people. The Capital Hospital map coordinates and phone are those published through the Government of Odisha page; the page's district field was not inferred. The UI displays the required availability disclaimer. Emergency helpline contacts are kept separate from physical resource records.

The page provides official reference links even when MongoDB is unavailable or the directory is empty. The OSDMA emergency-contacts page requires district selection for district contacts. Its listed OSDMA office numbers `0674-2395398` and `0674-2395531` are identified as office contacts, not confirmed 24-hour emergency hotlines; current availability is not confirmed. SRC Odisha and the Odisha Government emergency directory remain reference links; the SACHET portal is also linked for direct verification of the integrated RSS entries. Always open the official site and confirm current details.

### Flood alert API and sources

- `GET /api/alerts/` returns active alert records with pagination. Optional filters: `severity` (`Information`, `Advisory`, `Warning`, `Emergency`), `district`, `search`, `source_type`, and `verification_status`. Optional `client_id` returns browser-scoped read state. Supplying `latitude` and `longitude` requests a current location-specific weather assessment; optional `location_name` labels it.
- `GET /api/alerts/sachet/` refreshes and returns the official Odisha RSS snapshot, including `status` (`available`, `empty`, `stale`, or `unavailable`), last successful check/update times, cached entries, and the verified feed URL. Network or XML failures leave the previous MongoDB snapshot intact.
- `GET /api/alerts/<alert_id>/` returns alert details; optional `client_id` includes read state.
- `POST /api/alerts/mark-read/` accepts `{ "alert_id": "...", "client_id": "UUID" }` and stores a browser-scoped read receipt in `user_notifications`. The random UUID is not an account identifier or contact detail; receipts expire after 90 days.
- `POST /api/alerts/` creates a manually managed notice and requires an authenticated Django staff user. Emergency-severity records require an approved official government source, source verification, and publication timestamp. Warnings require a verified source.

The `flood_alerts` collection stores manually managed records and short-lived generated advisories. Weather alerts use the existing Open-Meteo weather and risk-assessment services and are always labelled **Advisory**, never an official government warning. The service can create a **Warning** record from a recent verified high/critical citizen report or a cluster of nearby verified reports; the UI labels these as community reports, not government alerts. Report-derived alerts expire after 24 hours, and weather advisories after one hour. If report data, weather data, or MongoDB is unavailable, the source status is reported and no missing warning is invented.

Severity is explicit: **Information** is general preparedness content, **Advisory** is a potentially concerning condition such as the weather-based estimate, **Warning** is verified significant risk information, and **Emergency** requires a verified official government source and publication timestamp. Weather estimates are never automatically promoted to Warning or Emergency.

The official CapFeed page lists Odisha as state ID `1312` and links its RSS at `https://sachet.ndma.gov.in/cap_public_website/rss/rss_odisha.xml`. This URL was verified from the official page code and returned HTTP 200 with an RSS 2.0 document; a conditional request with its ETag returned HTTP 304. FLOODGUARD uses this RSS feed through a Django-only service, not the guide's separate CAP XML endpoint. The supplied CAP XML guide describes ETag caching and HTTP 200/304 behavior; the RSS feed also supports those validators.

The observed RSS items provide a stable `guid`, headline, original link, author, category, and publication date. In the verified response, descriptions were empty and no severity, urgency, affected area, effective time, or expiry fields were supplied. FLOODGUARD leaves those values missing rather than deriving or inventing them. Feed entries are labelled as entries, not confirmed-current warnings; explicit expiries are excluded after expiry, and items without an expiry carry a validity-check caveat and original-source link. During an outage, previously stored entries are returned as stale when available and are never deleted by the failed refresh. The official portal remains the authority for current validity.

There is **no live OSDMA, SRC Odisha, or Odisha Government alert feed** connected. Those government pages are linked for manual checking; the application does not scrape them. Manual official alerts must be entered by authorized staff with the official source URL, publication time when available, and verification timestamp. External requests in automated tests are mocked.

No additional environment variables or notification provider are required. The browser notification centre only stores read/unread state in MongoDB; it does not send SMS, WhatsApp, push messages, dispatch an ambulance/rescue team, or contact a shelter. Database errors return HTTP 503 and are displayed instead of pretending records were saved.

Emergency resource and alert data may be incomplete, stale, or unavailable. The application does not confirm shelter capacity, facility opening status, emergency-service availability, or that responders were contacted. **Route suggestions are informational and may not reflect current road closures or rapidly changing flood conditions. Follow official evacuation instructions and avoid entering floodwater.**

## Emergency assistant

The Emergency Assistant page sends flood-safety questions to Django at `POST /api/assistant/emergency/` as JSON:

```json
{
  "message": "What should I pack in an emergency kit?",
  "history": [{"role": "user", "content": "We may need to evacuate."}]
}
```

Messages must contain 1–1000 non-whitespace characters. Optional conversation context is limited to the last ten user/assistant turns and 5,000 characters; it is sent to Gemini for context when configured. The application does not persist chat history.

### Configure Gemini

The backend uses Google's maintained `google-genai` Python SDK. Put credentials only in `backend/.env` or the backend process environment:

```dotenv
GEMINI_API_KEY=your-google-ai-studio-api-key
GEMINI_MODEL=gemini-3.8-flash
```

`GEMINI_API_KEY` is required for model responses. `GEMINI_MODEL` is optional and defaults to `gemini-3.8-flash`; set it to a model available to your Gemini API project to change models. `backend/.env.example` contains a placeholder key, not a usable credential. Never put this key in `frontend/.env`, Vite variables, or browser code. The backend passes it directly to the SDK; it is not returned in API responses or logged.

Install the backend dependencies after setting up the virtual environment with `python -m pip install -r requirements.txt`. Start Django from `backend/` with `python manage.py runserver`; start Vite from `frontend/` with `npm run dev`. The existing Frontend and Backend sections above contain the full PowerShell setup and startup commands.

The backend sends the current question and bounded recent context to Gemini with a flood-safety system instruction and a 15-second per-attempt request timeout. It retries timeouts and temporary 503/`UNAVAILABLE` errors at most twice, with 0.5- and 1-second delays; invalid credentials, quota, model, and other errors are not retried. The API returns `answer`, `mode` (`gemini` or `curated_fallback`), `fallback_reason`, and a disclaimer. If the key is missing or Gemini remains unavailable, returns another error/quota response, or supplies no usable text, the existing curated safety guidance is returned instead. The interface labels Gemini-generated and fallback responses distinctly.

The latest real Gemini request checked on 2026-11-20 returned HTTP 503 `UNAVAILABLE`. Successful live Gemini generation has not been verified; mock tests verify only application behavior and do not establish provider connectivity.

Gemini answers are generated text, not official guidance. The assistant has no live flood, weather, incident, rescue, or shelter data; it cannot determine a user's exact danger or contact responders. It must not invent phone numbers, warnings, incidents, or shelter availability, and must never recommend entering or crossing floodwater. In immediate danger, contact local emergency services and follow official local authority instructions. Recent context sent to Google is subject to Google's Gemini API data terms; avoid sharing unnecessary sensitive information.

Run Django checks and all backend tests from `backend/`, and frontend tests and a production build from `frontend/`:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test api.tests
npm test
npm run build
```

## Hackathon submission summary

### Problem statement

People in flood-prone communities may need to make time-sensitive decisions while weather information, local observations, route conditions, emergency contacts, and official guidance are scattered across different sources. Incomplete or stale data can make it difficult to understand what is known and what still needs direct confirmation.

### Proposed solution

FLOODGUARD AI brings weather context, a preliminary flood-risk indicator, citizen-submitted observations, route assessments, emergency-resource records, alerts, and flood-safety guidance into one web application. It presents source and data limitations alongside results and directs users to official channels for decisions that require authority confirmation.

### Innovation

The project combines multiple practical flood-awareness workflows and makes uncertainty visible: the risk indicator identifies its weather-based inputs, route assessment distinguishes checked reports from missing or incomplete evidence, and empty resource or alert collections remain explicitly empty. The current risk score is a transparent heuristic, not machine learning.

### Social impact

The platform is intended to improve access to preparedness information and make it easier for residents to submit observations and review available local records. Its potential impact depends on accurate, current, and sufficiently populated data and on coordination with local authorities; no impact has yet been measured.

### Target users

Residents and community reporters in flood-prone areas, local disaster-management teams, and authorized staff responsible for maintaining verified resource and alert records.

### Key features

- Location-based Open-Meteo current weather and forecast display.
- Preliminary weather-based flood-risk assessment.
- Citizen flood reports, including optional photos, submitted as pending review.
- OSRM driving-route geometry with available verified-report and sampled weather context.
- Manually managed emergency-resource directory and flood-alert centre.
- Gemini emergency assistant integration with clearly identified curated safety guidance when Gemini is unavailable.

### Technology stack

React, Vite, JavaScript, Django, Django REST Framework, PyMongo, MongoDB Atlas, Open-Meteo, OSRM, OpenStreetMap tiles, and Google's `google-genai` SDK.

### Future scope

- Evaluate locally appropriate risk indicators with flood, river, terrain, drainage, and ground-observation data; validate any predictive model before presenting it as operational.
- Extend verified SACHET RSS support to additional states only after confirming each official feed URL and its data contract; evaluate whether CAP XML details are needed to obtain expiry or affected-area data.
- Populate the facility directory only with verified, maintained records and confirm availability with responsible authorities.
- Assess accessibility, language coverage, offline resilience, and low-bandwidth use with target communities.
- Explore notifications or dispatch only with appropriate agency partnerships, consent, safeguards, and operational procedures.

## Demo walkthrough

Before presenting, configure the local frontend and backend, make sure the required MongoDB Atlas database is reachable, and check whether Open-Meteo and OSRM are responding. Do not pre-populate fabricated reports, facilities, alerts, or provider responses. If a service is unavailable, demonstrate the visible error or empty state rather than claiming a successful result.

1. **Dashboard overview** — Open Situation overview, select a location, and show the displayed weather-based indicator and backend record counts. Point out empty states and the distinction between verified reports and other backend records. Values depend on live provider and database availability.
2. **Live weather** — Show the current conditions and forecast for a selected location, including the Open-Meteo attribution and provider/fetch timestamps. These are model-based conditions and forecasts, not ground-station confirmation or proof of flooding.
3. **AI Flood Risk assessment** — Open the risk page, request an assessment for a location, and review its inputs, score, and limitations. State clearly that the score is a weather-based heuristic, not a trained ML model, validated flood threshold, or official warning. If provider data is missing or stale, the result may be unavailable.
4. **Citizen Flood Reporting** — Submit only a genuine observation with its location, severity, and description; an optional supported photo can also be attached. Show that a successful submission enters pending review. Do not present a pending report as verified or create fictional data for the demo. This flow requires the backend and MongoDB to be available.
5. **Safe Route Finder** — Search for real origin and destination locations, request a route, and explain the OSRM geometry, sampled weather context, report evidence status, and risk classification if a response is returned. The public routing service and map tiles may be unavailable; alternatives are not separately risk-assessed, reports may be sparse, and no live road closures or flood depth are verified. A low or unknown classification is not a safety guarantee.
6. **Emergency Resources** — Show the sourced facilities, category/district/search filters, verification labels, official links, and the availability disclaimer. Explain that seven entries remain unverified and one source-checked hospital record is verified; none of these labels indicates that a facility is currently open or accepting evacuees. No capacity or live availability check is implemented.
7. **Flood Alerts** — Show the backend-checked SACHET Odisha RSS panel, feed freshness, original links, and any returned feed entries, then review the separate stored-alert list. The observed RSS payload omitted description, area, severity, and expiry; the UI marks these as unprovided and warns that feed entries are not confirmed current. If a refresh fails, show stale cached entries or an unknown-status state. Weather-derived items remain advisories, not government warnings.
8. **AI Emergency Assistant** — Ask a general preparedness question and show whether the response is labelled Gemini or curated fallback. Real Gemini connectivity has not been verified and a recent request returned HTTP 503; the curated fallback works. Neither response is an official instruction or live situational assessment, and the assistant does not contact emergency services.

## Deployment preparation and known limitations

- The flood-risk result is a weather-based heuristic, not a trained or scientifically validated ML model or an official warning.
- The Odisha SACHET RSS feed is integrated through Django. The observed feed did not provide description, severity, urgency, affected area, effective time, or expiry; verify the original item and its validity through SACHET. Other state feeds are not integrated. No emergency dispatch, SMS, or push-notification integration is connected.
- The emergency resource directory contains a small, curated initial set; four CMRF shelters and three police-station names remain unverified due to missing address/contact/location detail. Fire-station and relief-centre categories are supported but not populated from these sources. Confirm each record with the responsible authority before travel.
- Gemini has not passed a real connectivity check and most recently returned HTTP 503. Keep the curated fallback and do not present mocked test success as live AI availability.
- Before deployment, configure the production environment described above, use HTTPS and a managed secrets store, and review Django security headers/cookie settings, CSRF behavior, staff-account provisioning, rate limiting, request-size limits, persistent media storage, database backups, and monitoring.
- Configure production MongoDB access with least privilege and verify the database health endpoint in the target environment. Do not copy local `.env` files into deployment artifacts.
- Open-Meteo and OSRM public endpoints and OpenStreetMap tiles have their own availability and usage limits. Route estimates do not verify live closures or water conditions.

The project is suitable for **deployment preparation**, but is not yet verified as production-ready. Complete the environment-specific security, provider-availability, database, storage, and operational checks before release.
