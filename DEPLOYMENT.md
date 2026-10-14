# Deploy SheSync

The application needs a Python web service and a continuously running reminder worker. GitHub Pages alone cannot host its sessions, SQLite database, clinic search endpoint, email sender, or scheduler.

## Render blueprint

1. Sign in to [Render](https://render.com/) with the GitHub account that owns `Aditisy/SheSync`.
2. Select **New + → Blueprint**, choose the repository, and approve the included `render.yaml`.
3. Render creates `shesync-web`. Its start command launches the reminder worker alongside the single Gunicorn web worker so both use the same attached SQLite disk at `/var/data`.
4. In the service environment, set `PUBLIC_BASE_URL` to the HTTPS service URL and add that exact origin to `ALLOWED_ORIGINS`. Set the Gmail configuration and `SHESYNC_DB=/var/data/shesync.sqlite3`.
5. Deploy, open `/api/health`, then share the web service HTTPS URL. The browser asks for location only after the visitor chooses **Use my location**.

The Maps button works without Google billing. In-page clinic records use OpenStreetMap public listings and can omit phone, website, or full address when the source has no tag. SheSync does not create a booking confirmation. It saves a private **Request prepared** record; only an independently verified external booking URL may show a booking button.
