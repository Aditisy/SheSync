> Current button repair and live test: [IMMEDIATE_EMAIL_FIX.md](IMMEDIATE_EMAIL_FIX.md).

# SheSync — local competition build

**Latest: dynamic Gmail recipients and private appointment requests implemented; see [EMAIL_AND_APPOINTMENTS.md](EMAIL_AND_APPOINTMENTS.md). 14 October repair verified. See [URGENT_FIXES.md](URGENT_FIXES.md) for real Resend acceptance evidence, the remaining Google referrer action, the one-click demo and exact commands.**

The main entry point is `SheSync_Website.html` (HTML, CSS and JavaScript in one self-contained file). `index.html` and the legacy FIXED filename mirror it. The full app is served by `backend_api.py` at http://localhost:5000; double-clicking the HTML supports the offline demo, but secure account, email, Google Places and model API features need the HTTP backend.

## Install and run

From the repository directory, with Python 3.11+:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python backend_api.py
```

Open **http://localhost:5000**. In another terminal, using the same environment:

```powershell
python reminder_worker.py
```

The installed Desktop SheSync environment can also run this build. Additional packages are installed inside `.runtime-deps` in this workspace and are loaded automatically; they are ignored by Git.

For the preserved Streamlit demo:
```powershell
python -m streamlit run app/app.py --server.port 8501
```

For notebooks:
```powershell
python -m pip install jupyterlab
python -m jupyterlab
```
Open `01_EDA_PCOS.ipynb` for original SHAP, or `notebooks/02_Reproducible_Model_Comparison.ipynb` for new experiments.

## What changed

- Cycle tracking now stores start/end records with edit/delete, duplicate and overlap protection, and start-to-start intervals. All UI views derive from one calculation. Dates are calendar ordinals; time-of-day does not shift the result. Default estimate is explicitly labelled and configurable; actual intervals take priority. Backend uses Asia/Kolkata for reminder timing.
- Exact required example: 18 September 2026 → 13 October 2026 = 25 days → estimated 7 November 2026.
- Both baseline model files and original notebook are preserved. Inference now uses exact 41-feature names and does not zero-fill missing measurements. Real SHAP contributions are returned. The public demo runs the original model on one documented historical dataset example, not on user-entered health data.
- Accounts use Werkzeug scrypt hashes in SQLite, signed HttpOnly session cookies, request-header/origin checks, and basic login throttling. Old local plaintext passwords are removed when the UI opens; old profile health records remain local. Create a secure account using the same email to retain local history, and use “Sync local history for reminders”.
- Daily logs are date-upserts and escaped before rendering; notes cannot execute HTML. Secure account logs persist in SQLite and are merged with the local cache on refresh.
- Doctor discovery works without Google billing: requested browser geolocation or city/area is sent to the authenticated backend, which queries OpenStreetMap public listings and shows only source-supplied name, address, phone and website fields. The page always includes a no-key Google Maps search link. Static invented doctors and booking results are removed.
- Reminders use opt-in plus recipient confirmation, durable SQLite preferences/outbox, a separate India-time scheduler, provider idempotency keys, attempt logs and unsubscribe. A provider-accepted request is labelled accepted, never “delivered”. Interrupted sends require provider reconciliation; retries stop outside the provider's idempotency window.
- Sensor simulation is clearly identified as demonstration data. Initial readings are blank; charts retain ten generated values. The weekly chart shows actual saved pain check-ins, not fabricated temperature/ovulation evidence. Live ingestion is separate from PCOS inference.
- Seven model experiments, actual evaluation JSON, saved pipelines, plots, dataset audits and a new notebook are available. Experiments are not promoted based on holdout scores; the original baseline remains active.

## Configure real email without buying a domain

Gmail is selected in the private backend `.env`. It sends to each authenticated user's dynamically supplied, confirmed address; Gmail, Outlook, Yahoo and other providers are not restricted by an application allowlist. Resend remains available as an alternative. See [EMAIL_AND_APPOINTMENTS.md](EMAIL_AND_APPOINTMENTS.md) for configuration, provider comparison, limits, verification and actual test evidence.

## Configure real Google Places

The legacy HTML contained an embedded browser key; its Cloud permissions and billing restrictions could not be inspected from this workspace. The new primary app uses a key supplied through `/api/config` from `.env`, and no private server key is sent to the browser.

1. In Google Cloud, enable **Maps JavaScript API** and **Places API (New)** and review billing, budgets and quota limits.
2. Use a separate browser API key. Restrict application use to exact website referrers, e.g. `http://localhost:5000/*`, `http://127.0.0.1:5000/*`, and the actual deployed website host. Restrict API usage to the enabled Maps JS / Places APIs. Do not make an unrestricted key public. See [Google key security guidance](https://developers.google.com/maps/api-security-best-practices).
3. Set `GOOGLE_MAPS_BROWSER_KEY` in `.env`; restart backend. The browser SDK necessarily receives this restricted browser key.
4. Serve via HTTP localhost or HTTPS, not file://, so referrer restrictions and geolocation behave consistently.
5. Use “Find doctors near me”, grant permission, or enter a city. Confirm results and clinic details directly. Enable a production map ID instead of Google's demo map ID before deployment.

Google Places can incur billed requests depending on selected fields/quota. Billing and actual key restrictions are external configuration; no claim is made that they were verified here.

## Wearable ingestion readiness

`POST /api/wearable` requires `X-Device-Key` equal to `WEARABLE_INGEST_KEY`. It persists separate live/demo records with timezone-aware timestamps. Supported measurements include heart_rate, temperature, gsr, steps, motion, ecg and research estradiol values. This is ingestion readiness, not hardware calibration or validated hormone sensing. Values are never added to the clinical PCOS model.

```json
{"device_id":"ESP32-S3-001","source":"live","timestamp":"2026-10-13T09:00:00+05:30","heart_rate":72,"temperature":36.6,"gsr":0.34,"steps":4821}
```

ESP32-S3 firmware can post MAX86150 ECG/PPG, MAX30205 temperature, GSR/EDA and BMI270 motion values through this endpoint. Firmware, BLE transport, device-to-person ownership and estradiol prototype validation remain separate future integration work; no hardware is claimed connected.

## Competition demonstration (about four minutes)

1. Open localhost:5000 and choose **Explore the demo**. It labels sample data clearly.
2. Cycle Tracking: add starts 18 September and 13 October 2026. Show 25 days and 7 November, the calendar legend, history and an edit/delete action. Refresh to demonstrate persistence.
3. Daily Log: select symptoms and mood, save, show the streak/calendar and the diary chart. Re-saving updates the same date.
4. PCOS: load the historical example and run assessment. Show original RF/XGBoost outputs and actual XGBoost SHAP; clearly state this is screening research support, not diagnosis or a calibrated individual risk.
5. Model Performance: show measured experiment metrics, ROC, confusion matrix and confidence intervals. Explain why the original baseline was retained.
6. Find Doctors: grant permission or enter a city once Maps is configured. Otherwise use the clearly labelled real Google Maps search link.
7. Reminders: show provider configuration state, opt-in and delivery logs. Only demonstrate actual sending after recipient confirmation and provider configuration.

## Tests actually executed

- `python tests/test_integration.py`: cycle example, invalid/duplicate records, edit/delete, backend persistence, hashed passwords and auth boundaries, date-upsert logs, actual original model predictions/SHAP, mocked provider scheduling/idempotency/unsubscribe, authenticated wearable ingestion.
- `node tests/browser.cjs` with Playwright/Chrome: all eight tabs, exact cycle example, refresh persistence, duplicate handling, escaped notes, actual model + SHAP through the website, experiment graphs, real account login/refresh, saved reminder consent, missing-Maps configuration and mocked geolocation denial, ten-reading simulation, and no overflow at 360, 390, 768, 1024, 1440 pixels.
- Original 13 October tests used mocked email only. On 14 October, real confirmation, test and worker-scheduled emails were accepted by Resend; inbox placement was not independently verified and delivery lookup returned HTTP 401. Google requests were tested with the recovered key and returned referrer denials; real clinics/markers remain unverified until referrers are updated. Hardware was not connected.

## Review and deployment

The repository includes a [Render blueprint](DEPLOYMENT.md) for an HTTPS web service and reminder worker with a persistent database disk. Static GitHub Pages cannot run Python, SQLite, sessions or the scheduler. Configure `COOKIE_SECURE=true`, a strong `SECRET_KEY`, allowed origins, a production WSGI server, restricted keys, TLS, DB access controls and backups before hosting real health records. SQLite and browser caches are not encrypted medical-record storage; this remains a competition/research prototype.
