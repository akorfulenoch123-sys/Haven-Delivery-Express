# Haven Delivery Express — Delivery Booking Platform

A starter Flask + SQLite web application for Haven Delivery Express.

## Features
- Responsive landing page inspired by the supplied flyer
- Customer registration and login
- Delivery request form
- Automatic tracking code generation
- Public tracking lookup by code
- Starter delivery-fee estimate in GH₵
- Customer dashboard with their bookings
- Admin dashboard to view bookings, change status and adjust fees
- WhatsApp link for contacting the business
- Password hashing and basic CSRF protection for POST forms

## Run locally (Windows)
1. Install Python 3.10 or newer.
2. Extract this ZIP.
3. Double-click `run_windows.bat`, or open a terminal in this folder and run:
   ```bash
   python -m venv .venv
   .venv\\Scripts\\activate
   pip install -r requirements.txt
   python app.py
   ```
4. Open `http://127.0.0.1:5000`.

## Run locally (macOS/Linux)
```bash
chmod +x run_mac_linux.sh
./run_mac_linux.sh
```
Then visit `http://127.0.0.1:5000`.

## Initial administrator login
- Email: `admin@havendelivery.local`
- Password: `ChangeMe123!`

**Security:** This is a development starter login. Before hosting publicly, set a strong `HAVEN_ADMIN_EMAIL`, `HAVEN_ADMIN_PASSWORD`, and `SECRET_KEY` environment variable, and change/remove the default administrator account. The app only creates the default admin if that email does not already exist.

Example (macOS/Linux):
```bash
export HAVEN_ADMIN_EMAIL="your-admin-email@example.com"
export HAVEN_ADMIN_PASSWORD="use-a-long-unique-password"
export SECRET_KEY="a-long-random-secret-value"
python app.py
```
PowerShell example:
```powershell
$env:HAVEN_ADMIN_EMAIL="your-admin-email@example.com"
$env:HAVEN_ADMIN_PASSWORD="use-a-long-unique-password"
$env:SECRET_KEY="a-long-random-secret-value"
python app.py
```

## Important before real business use
- The current pricing logic is a **sample estimate only**, not a verified price list. Edit `calculate_fee()` in `app.py` for your actual zones, distances and fees.
- The app does not calculate routes, accept online payments, send automatic SMS/email, or provide GPS/live-driver tracking.
- WhatsApp opens a prefilled message; it does not automatically send it.
- Use HTTPS, secure environment variables, backups, and a production WSGI server when deploying. Do not use Flask's development server for production.
- The site does not verify medicine prescriptions or enforce regulated-product delivery rules. Establish proper procedures before offering pharmacy deliveries.


## Business configuration (edit before launch)

Open `business_config.json` to change:
- Business name and WhatsApp number
- Operating hours
- Service areas
- Base delivery estimates and outside-area surcharge by service

The included prices and coverage are **draft defaults only**, not confirmed business terms. Update them to your real rates and actual delivery coverage before accepting paid orders. Pricing uses simple address text matching; it is not distance-based routing.

### Suggested first setup
- Service area draft: Tema, Tema Communities 1–25, Sakumono and Spintex
- Draft estimates: food GH₵18, pharmacy GH₵22, parcel/document GH₵25
- Draft outside-area surcharge: GH₵12

### Before putting the site online
1. Set a unique `SECRET_KEY`, `HAVEN_ADMIN_EMAIL`, and `HAVEN_ADMIN_PASSWORD`.
2. Remove/change the default administrator account before real use.
3. Confirm the WhatsApp number, opening hours, delivery rates and areas.
4. Use a production WSGI server and HTTPS; do not expose Flask's development server.


## Render deployment (starter setup)
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Set `SECRET_KEY`, `HAVEN_ADMIN_EMAIL`, and `HAVEN_ADMIN_PASSWORD` in the Render environment.
- Do not use the default administrator credentials for a public website.
- Important: SQLite stored in the app folder may be lost when a hosted instance is replaced or redeployed. Configure persistent storage or migrate to PostgreSQL before relying on real customer orders.
- Confirm actual delivery fees, service coverage, WhatsApp number, and business hours before launch.


## Review and deployment notes
- Final delivery prices were not supplied, so the customer form now says the fee is confirmed manually. An administrator can enter the confirmed fee in the admin dashboard.
- For Render, set `SECRET_KEY`, `HAVEN_ADMIN_EMAIL`, and `HAVEN_ADMIN_PASSWORD` as environment variables. Production startup refuses to use the known development admin credentials.
- If using a Render persistent disk mounted at `/var/data`, set `DATABASE_PATH=/var/data/haven_delivery.db`. Without persistent storage, SQLite data can be lost when the service is replaced or redeployed.
- Render build command: `pip install -r requirements.txt`
- Render start command: `gunicorn app:app`
- Security and feature checks performed here are static checks only; this environment has no network access to install Flask, so a full live Flask integration test could not be run.


## Additional review fixes
- Tracking codes use a longer random token.
- Public tracking no longer displays pickup/drop-off street addresses.
- Login redirects are restricted to same-site paths.
- Admin fee input rejects negative, NaN, and infinite values.
- No final delivery rates have been supplied; the customer sees a manual fee confirmation notice.
