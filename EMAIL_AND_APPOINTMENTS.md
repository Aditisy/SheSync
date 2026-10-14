> Latest: the actual button now submits its current address and sends synchronously, with separate confirmation/test cooldowns. See [IMMEDIATE_EMAIL_FIX.md](IMMEDIATE_EMAIL_FIX.md). Earlier queue-based manual-action descriptions below are superseded.

# Dynamic email and private appointment requests — 14 October 2026

## Current operation

Open http://localhost:5000. The backend and reminder worker are running. No changes were pushed to GitHub. The three HTML entry points remain identical self-contained files; private sending and persistence use Flask.

Gmail SMTP with the existing authenticated app password is selected. Its credentials are in ignored repository/.env, never JavaScript. The authentication actually tested is an app password, not OAuth. Gmail API OAuth refresh-token sending is also implemented as a selectable backend alternative; no existing OAuth credential is removed or printed. OAuth live authorization was not tested.

Registered users save their own address and opt in. The backend validates a single address and rejects header injection. The user requests a confirmation email, opens its random ownership link (24-hour lifetime), then may send a test email. Tests and reminders go to that user's verified saved recipient, without any application recipient allowlist or hardcoded personal address. An address change revokes verification and cancels queued old-recipient messages. Unsubscribe disables consent. Authentication, origin checks and fixed server-generated message content apply; users cannot supply arbitrary email subjects, recipients to the test endpoint, or email bodies.

SQLite persists per-user preferences and sending jobs. The worker schedules in Asia/Kolkata independently of browser activity. Keep both backend_api.py and reminder_worker.py running. Daily jobs are deduplicated per user/day; upcoming jobs per user/estimated date. Unknown SMTP/API outcomes are held for operator review, rather than blindly retried. Provider acceptance is displayed accurately and does not claim inbox delivery.

Persistent limits: one email action per user/minute, eight per user and recipient/day, twenty per IP/hour; registration eight/IP/hour. Worker/provider submission budgets: ten/minute, ten/user/day, twenty/recipient/day and EMAIL_DAILY_LIMIT (default 100 total/day). Deferred jobs remain queued. Provider quotas can be stricter and apply across every use of the sender account.

## Provider comparison and one-time configuration

| Option | Domain purchase needed for this approach? | Assessment |
| --- | --- | --- |
| Gmail SMTP + app password | No | Selected: existing account authentication worked; simplest local student demo. TLS, backend-only credential. 2-Step Verification required. |
| Gmail API OAuth | No | Implemented alternative. More setup, narrower gmail.send permission; refresh token stays backend-only. Not live-tested. |
| Resend onboarding sender | No, but sandbox recipient restriction | Kept working as an alternative for its permitted testing recipient. Does not meet arbitrary-recipient requirement with onboarding@resend.dev. |
| Mailjet free | Additional account and sender validation | Free SMTP/API budget currently 200/day and 6,000/month; not selected because Gmail already authenticates and avoids a new sender setup. No Mailjet delivery tested. |
| Brevo free-email sender | Sender replacement/deliverability constraints | Its documentation describes replacing unauthenticated free-email senders and recommends domain authentication. Not selected for this no-domain project. |

References: [Google app passwords](https://support.google.com/accounts/answer/185833), [Gmail sending limits](https://support.google.com/mail/answer/22839/limits-for-sending-and-receiving-emails?hl=en-GB), [Gmail API scopes](https://developers.google.com/workspace/gmail/api/auth/scopes), [Mailjet pricing](https://www.mailjet.com/pricing/), [Brevo free-email sender restrictions](https://help.brevo.com/hc/en-us/articles/14925263522578-Comply-with-Gmail-Yahoo-and-Microsoft-s-requirements-for-email-senders).

Google documents approximately 500 messages/day for personal Gmail and can temporarily block sending for limits, bounces or suspicious activity. Inbox placement is never guaranteed. This implementation cannot bypass provider policy.

No new Gmail authorization is currently needed. If the app password is revoked: enable Google 2-Step Verification, create an app password named SheSync at https://myaccount.google.com/apppasswords, put it only in GMAIL_APP_PASSWORD in repository/.env and set GMAIL_USERNAME to the account you control. Set EMAIL_PROVIDER=gmail, then restart both processes. App passwords may be unavailable for certain organization/Advanced Protection accounts.

Optional OAuth: enable Gmail API in a Google Cloud project, configure an OAuth client and consent screen, authorize only the sender using gmail.send with offline access, then put client ID/secret/refresh token in GMAIL_OAUTH_CLIENT_ID, GMAIL_OAUTH_CLIENT_SECRET and GMAIL_OAUTH_REFRESH_TOKEN. Set EMAIL_PROVIDER=gmail_oauth. Recipient users do not need Google authorization or OAuth test-user registration; ownership confirmation is an application email link, regardless of their mailbox provider. A consent-screen application in Testing can have refresh-token expiry constraints; treat revocation/expiry as a setup error, not a successful send.

PUBLIC_BASE_URL=http://localhost:5000 makes confirmation/unsubscribe links usable on this computer. Opening that link on another device targets that device's localhost; cross-device use needs a reachable backend URL. No purchased domain is required to run or test on this computer.

## Google Maps one-time action

Real browser requests still return PERMISSION_DENIED with “Requests from referer http://localhost:5000/ are blocked.” Maps JavaScript loads but Places searches are denied. This verifies a referrer restriction is a current blocker; successful searches cannot be claimed until it is removed. No authorized Cloud Console session was available to change it. Other errors, if any, can only be assessed after the current denial is resolved.

Google Cloud → APIs & Services → Credentials → the existing Maps browser key → Application restrictions → Websites. Add exactly:

- http://localhost:5000/*
- http://127.0.0.1:5000/*

Keep API restrictions to Maps JavaScript API and Places API (New), ensure these APIs and billing are enabled, Save, wait for propagation, then retry. Do not remove all restrictions. The existing key stays in backend configuration; it is a browser key and is necessarily delivered to Maps JavaScript.

“Find doctors near me” explicitly requests browser geolocation and uses the coordinates to bias/rank Google Places results. Permission refusal offers manual city search and a genuine Google Maps search fallback. The UI uses real Google display names, addresses, available phone numbers, ratings, websites and directions. No fixture doctors are shipped as search results. Specialty and appointment availability must be checked with the clinic.

## Appointment behavior

A Google result offers Call clinic, Visit website and Get directions where information exists, plus Prepare appointment request for signed-in users. Date/time are user preferences in India time, never invented clinic slots. The saved record is always “Request prepared”; it sends nothing to a clinic and never claims confirmation. My appointments is backed by authenticated, user-scoped SQLite queries, including deletion. Refresh preserves requests. Private notes are rendered as text.

“Book appointment” appears only for a configured operator-verified URL. Google websiteURI alone is not treated as booking evidence. No verified booking destination is currently configured, so no Book action is shown. Optional instance/verified_booking_links.json maps an actual Google place ID to {"url":"https://actual-clinic-booking-url", "verified":true, "verified_at":"YYYY-MM-DD", "evidence":"How the clinic's ownership and booking destination were verified"}. Do not add entries without verification. A link is a contact route, not a booking confirmation API.

Clinic snapshots saved in requests originate from browser Places results; the backend validates format and scopes storage but does not independently authenticate the snapshot against a server Places key. Stored requests therefore remain personal preferences, not evidence of a confirmed clinic booking.

## Actual test evidence

- Twelve automated backend tests passed. Actual RF/XGBoost inference and SHAP execute; email transport and second-user accounts in these tests are mocked. Isolation covers Gmail and Outlook mock recipients, address change, consent/unsubscribe, rate limits, private requests, expired confirmation and transport failures. Mock mailbox domains are never transmitted to a real provider.
- Live Gmail SMTP authenticated. Confirmation and test email were accepted for the previously authorized inbox. A worker upcoming reminder using an explicitly synthetic cycle in the disposable test account was accepted after Chrome closed. Test profile consent was disabled afterwards. See tests/GMAIL_LIVE_REPORT.json. This is submission evidence; inbox delivery was not independently inspected. No second real inbox delivery is claimed.
- Browser tests passed one-click PCOS research examples, both models and SHAP, clinical sample population, persistence and five responsive widths (1440, 1024, 768, 390, 360), with no JavaScript errors. See tests/URGENT_BROWSER_REPORT.json.
- Appointment form, save, reload, contact actions and removal were browser-tested using an explicitly mocked clinic snapshot. No fake clinic is part of live discovery. No live booking provider was tested.
- Live manual city and nearby-coordinate searches were attempted; Google denied the localhost referrer. Permission-denial and supplied-coordinate branches were tested; actual device geolocation, real clinic results and markers remain unverified. Existing loopback tests also observed the restriction.

## Commands

Run from repository: python backend_api.py in one terminal and python reminder_worker.py in another. Tests: python -m unittest discover -s tests -p test_integration.py. Browser scripts require Playwright and Chrome. Private .env, instance DB/session/confirmation tokens and runtime caches are ignored by Git.
