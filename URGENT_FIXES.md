> Latest update: Gmail now supports dynamic verified recipients without a purchased domain. The Resend evidence below is historical. See [EMAIL_AND_APPOINTMENTS.md](EMAIL_AND_APPOINTMENTS.md) for the current provider and appointment implementation.

# SheSync — competition-day repair, 14 October 2026

Use **http://localhost:5000**, not file://, for model, Maps and email features. No changes were committed or pushed.

## What was actually fixed

**PCOS:** Quick Research Demo and Clinical Input Assessment are separate. Demo runs the actual models directly on one of four complete records from the existing workbook, so clinical required-field checks cannot block it. Historical records 1, 2, 3 and 13 come from `Full_new`; source SHA-256, recorded labels and exact 41 feature values are available through `/api/pcos-examples`. No measurements were invented. The old loader tied sample availability to the state of a 41-field form; the new demo is independent, works signed in or in demo mode, and has its own button and progress state. Clinical inputs are grouped into body/vitals, history, laboratory/hormones, symptoms/lifestyle, and ultrasound sections. The example-copy action was verified to populate all 41 exact named inputs. Results now show actual RF/XGBoost classifications, uncalibrated probabilities and XGBoost SHAP contributions.

**Email:** A real Resend request initially failed with HTTP 403 and Cloudflare error 1010. It was the default Python urllib User-Agent, not a demonstrated sender/recipient restriction. Adding a normal SheSync application User-Agent fixed the actual request. Missing configuration no longer consumes send attempts. Queue rows snapshot recipients and confirmation/unsubscribe paths to avoid sending stale jobs to a changed address. Configuration is loaded beside the backend; relative DB paths are resolved relative to that same project. Worker heartbeats are stored in the database and shown in the UI, confirming that backend and scheduler use the same DB. Provider acceptance and provider delivery events have different labels. Config and failures list required variable names without exposing keys.

**Maps:** The previously used browser key was recovered into ignored local `.env`, and `/api/config` supplies it to the SDK. Actual live Places requests from both local origins were rejected by Google with `PERMISSION_DENIED: Requests from referer ... are blocked`. This is an external key referrer restriction, not missing credentials. The UI now gives precise instructions, clears stale results on each search, keeps current-location/manual-location paths, and does not substitute invented clinics.

## Live email evidence

Authorized recipient: syaranaladiti@gmail.com. A separate disposable test profile was used so the user's normal account/preferences were not modified.

- Confirmation accepted by Resend: `01a13979-412c-7613-b808-517e8a9bf53a`.
- User reported confirmation; because SQLite still showed unconfirmed, the actual generated confirmation URL was exercised in the browser and verified=1 persisted.
- Real test email accepted: `01a1397e-7fda-7ea0-ac33-0a534d27d225`.
- Daily reminder accepted by the worker with the page closed: `01a1397f-fdc4-70b1-8339-cba414709ecb`. India-time scheduling and worker heartbeat verified.
- The disposable test profile was disabled afterward to prevent subsequent daily test emails. Normal account settings were left alone.
- Delivery-event lookup returned HTTP 401 with the current key. API acceptance is verified; provider-delivered status and inbox placement were not independently verified. Do not relabel accepted as delivered. The user reported confirmation; the agent did not read the inbox.

Logs and scoped live evidence: `tests/LIVE_EMAIL_REPORT.json`. The API key is in ignored `.env` only; it was not printed, committed or placed in the frontend.

## Remaining Maps action — exact referrers

Open [Google Cloud Credentials](https://console.cloud.google.com/apis/credentials), choose the existing Maps browser key, and edit **Application restrictions → Websites**. Add exactly:

```text
http://localhost:5000/*
http://127.0.0.1:5000/*
```

Keep API restrictions on **Maps JavaScript API** and **Places API (New)**. Confirm both APIs and billing are enabled. Save, allow propagation, then retry `Mallathahalli, Bengaluru` or current location. Keep localhost restrictions; do not switch to an unrestricted key. See [Google's key guidance](https://developers.google.com/maps/api-security-best-practices).

No authenticated Google Cloud console session was available to change these settings here. Real clinic results, markers and directions cannot be claimed verified while Google's requests are blocked. Geolocation denial and supplied-coordinate paths were tested; actual device coordinates were not claimed.

## Run the backend and worker

In PowerShell, from the repo directory:

```powershell
cd 'C:\Users\scyya\OneDrive\Documents\ChatGPT\Shesync\repository'
& '..\.venv\Scripts\python.exe' backend_api.py
```

In another terminal:

```powershell
cd 'C:\Users\scyya\OneDrive\Documents\ChatGPT\Shesync\repository'
& '..\.venv\Scripts\python.exe' reminder_worker.py
```

The existing Desktop SheSync environment is an alternative if desired. The hidden currently running backend/worker use that environment with absolute paths to these same source files. Do not launch duplicate copies on port 5000. Stop existing copies before a manual restart. Both processes must load the same `.env` and SQLite DB. Always restart both after changing provider configuration.

Resend testing uses `EMAIL_FROM=onboarding@resend.dev` and the allowed account recipient. The Resend onboarding sender restricts recipients; select the configured Gmail provider for dynamic verified recipients without a custom domain. `PUBLIC_BASE_URL=http://localhost:5000` is appropriate when the email is opened on this same computer; other devices require a reachable HTTPS backend. Refer to [Resend send API](https://resend.com/docs/api-reference/emails/send-email) and [idempotency behavior](https://resend.com/docs/dashboard/emails/idempotency-keys).

## Executed tests

- Nine Python integration tests passed, covering cycles, schema/models/SHAP, invalid inputs, real historical examples, reminder queue behavior, missing configuration without consuming retries, and mocked HTTP confirmation/test/delivery/scheduling. Mocked-provider tests are explicitly separate from live evidence.
- Actual browser: four historical examples through both models and SHAP; signed-in and anonymous demo; 41-field historical copy; model comparison charts; saved preferences after refresh; disable function; same-DB worker heartbeat; all eight tabs at widths 360, 390, 768, 1024 and 1440. No JavaScript errors.
- Actual Google requests for the requested manual location and supplied test coordinates returned real referrer denials. No fake results or marker success were reported.
- Real Resend confirmation, test email and background-scheduled reminder were accepted. Delivery lookup was attempted and its HTTP 401 limitation is recorded.

Reports: `tests/URGENT_BROWSER_REPORT.json`, `tests/LIVE_EMAIL_REPORT.json`. Screenshots were captured in the workspace.

## Model promotion decision

The completed experiment's highest training-CV F1 candidate is LightGBM (0.856); its CV recall is 0.844 and CV AUC 0.947. Gradient Boosting has the highest CV recall, Random Forest the highest CV AUC. The already inspected test split is not a new untouched final test. LightGBM's test recall was 0.750, below the user-reported baseline 0.83, so no replacement was justified. The original models remain active. Other experiments' 90.8% test accuracy is not used to retroactively change selection or claim a matched improvement over the reported 83.4% baseline. See `experiments/COMPETITION_SELECTION_REVIEW.md` and the dataset provenance audit; synthetic/republication candidates were not merged.

## Files changed this round

- `backend_api.py`: documented examples, source-aligned demo inference, actual classifications, configuration diagnostics, queue fixes, User-Agent repair, worker health and delivery lookup.
- `reminder_worker.py`: same-DB persistent heartbeat.
- `SheSync_Website.html`, `index.html`, legacy FIXED alias: separated assessment workflows, grouped clinical form, actual classifications/SHAP, precise Maps errors, email setup and worker/delivery states.
- `.env.example`, setup/testing documentation, scoped reports and regression tests.
- Local ignored `.env`: recovered existing Maps key plus user-provided Resend settings. No secret appears in reports or source.
- Original dataset, original RF/XGBoost model files and original notebook were preserved. No push was performed.
