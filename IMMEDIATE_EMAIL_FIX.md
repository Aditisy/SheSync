# Immediate Send Test Email repair — 14 October 2026

## Email root causes and final behavior

The old button posted `{}` and never saved the address being edited. It therefore acted on the previous saved recipient. The previous confirmation/test endpoints also shared a 60-second application cooldown, so a confirmation request could block a legitimate test immediately after verification. This was the application's rate limiter, not a Gmail error. Existing Resend errors were historical logs, mixed into a provider-neutral display. The current running provider is Gmail SMTP with its configured app password.

The button now submits the current email, consent and preferences to authenticated POST /api/reminders/test. The backend validates and saves that exact trimmed address. If ownership is unverified, it directly sends a confirmation email and explains the next step. Once verified, it directly invokes Gmail during that HTTP request. No test or confirmation is enqueued in the scheduled outbox. Separate email_actions records are an audit and idempotency ledger; the worker never reads or retries them. Automatic daily, upcoming, prediction and wellness jobs keep their persistent scheduled outbox.

Requests carry a unique ID. The frontend blocks concurrent clicks and preserves an uncertain request ID across refresh; the backend replays that ID's recorded result instead of sending twice. SMTP/API acceptance is shown as “Email accepted for sending”. Provider errors include actionable SMTP details. A lost submission response is held for review, never labelled successful or automatically resent. A 90-second email-specific browser timeout avoids the previous short generic timeout.

Cooldowns are now separate: verification 300 seconds, test 60 seconds. Verification followed by an immediate verified test is allowed. Daily/user/IP/recipient and provider budgets remain enforced in SQLite. HTTP 429 returns Retry-After, retry_after_seconds and cooldown_until; the button displays a countdown. Existing rate records were not erased. Provider and historical-provider labels distinguish older Resend failures from current Gmail requests. Unsent historical manual jobs are retired so the worker cannot later send an old manual test.

Configuration is read from the repository .env with explicit precedence over stale inherited shell variables. Gmail credentials remain backend-only; Resend remains an explicit optional provider. No domain purchase or recipient allowlist is required. Gmail's legitimate quotas and recipient-server policies still apply.

## Actual browser test

See tests/IMMEDIATE_EMAIL_BROWSER_REPORT.json. At http://localhost:5000, a disposable authenticated account first saved a different address without consent, then entered the previously authorized real recipient and clicked the actual button. Gmail accepted the ownership email to the current form address. Its generated confirmation route was opened in Chrome as part of the authorized test. The real button then sent a test immediately after verification, with scheduled hour set to 23:00. Gmail accepted it; two button invocations produced only one HTTP request for each action. The SQLite audit showed two accepted direct actions and zero scheduled test/verification jobs. Cooldown text was visible; no JavaScript errors occurred. Test profile consent was disabled afterwards.

This proves Gmail submission acceptance, not independently inspected inbox delivery. No second real inbox delivery is claimed. Dynamic Gmail/Outlook/Yahoo recipients and per-user isolation use explicitly mocked transports in the 13 automated integration tests. Existing PCOS RF/XGBoost inference and SHAP tests run real models.

## Current Maps investigation

See tests/MAPS_CURRENT_REPORT.json and tests/MAPS_REST_DIAGNOSTIC.json. The running key exactly matches current repository/.env (value never printed). Browser origin is http://localhost:5000; the actual Places request referrer is http://localhost:5000/. Both the supported Places JavaScript searchByText request and a same-key Places API (New) REST diagnostic returned HTTP 403 / PERMISSION_DENIED / “The caller does not have permission”. No clinics were returned. The earlier explicit “referrer blocked” error is no longer the response; repeating the same referrer changes is not justified.

There is no authorized Cloud Console session among the available browser surfaces. The generic response provides no project number, billing reason or API restriction detail. Therefore the exact remaining Cloud setting cannot be honestly identified or verified from these responses. One external diagnostic action: open Places API (New) in the Google Cloud project that owns this exact key and inspect the failed-request metrics/configuration there. Check the key's project, enabled places.googleapis.com service, API restriction and active linked billing using that project’s Console evidence. No new key should be pasted into chat and existing referrers should not be repeatedly changed. Real clinic discovery remains externally blocked; no live appointment/booking success is claimed.

## Calendar date

The existing sender-account backend history contained only 13 October 2026. With no observed interval it correctly used the 29-day default, producing 11 November. The 18 September 2026 start supplied in the user's request was missing from the saved account. That explicitly supplied start was added without replacing any existing records or inventing an end date. The account now has a 25-day observed interval and next estimate 7 November 2026. See tests/CYCLE_CURRENT_REPORT.json.

Authenticated hydration now refreshes period history from the backend even when empty, avoiding stale browser calendar records. Dashboard, calendar and reminders use the same date calculation; the scheduler reads the same SQLite history. Genuine additional history is preserved.

## Changed files and operation

backend_api.py, email_providers.py, SheSync_Website.html and its two identical HTML mirrors, tests/test_integration.py, and this report. The earlier Gmail configuration and appointment workflow remain intact. Backend and worker run from the existing repository. Nothing has been pushed to GitHub.
