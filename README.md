# MailScope — ICS Microproject

A local Flask dashboard for analyzing sent and received email message-trace CSVs. Includes email filtering, charts, heuristic risk indicators, and PDF report export. It works with fictional sample data and does not require a Microsoft 365 subscription.

## Requirements
- Python 3.10 or newer
- Internet connection only for loading Chart.js and Google Fonts from CDNs (the app itself and data processing run locally).

## Run on Windows
1. Extract the ZIP.
2. Open Command Prompt or PowerShell inside the `mailscope_ics` folder.
3. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\activate
   ```

4. Install packages:

   ```powershell
   pip install -r requirements.txt
   ```

5. Start the app:

   ```powershell
   python app.py
   ```

6. Open http://127.0.0.1:5000 in your browser.

## Run on macOS/Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Then open http://127.0.0.1:5000.

## Demo steps
1. Open the dashboard; it loads the fictional sample CSV automatically.
2. Search for `urgent`, choose a risk level, or filter by sent/received and status.
3. Upload another CSV using the upload panel.
4. Click **Export PDF report** to download a report using the current filters.
5. Click **Reset sample** to restore the bundled fictional data.

## CSV format
Required columns:
- `Timestamp` — e.g. `2026-10-12 09:30:00`
- `Sender` — email address
- `Recipient` — email address
- `Direction` — `Sent` or `Received` (also accepts `Outbound`, `Inbound`, `Incoming`)
- `Subject`
- `Status` — e.g. `Delivered`, `Failed`, `Rejected`, `Quarantined`

Optional columns:
- `SizeKB` — message size in kilobytes
- `SenderDomain` — sender domain; if omitted it is derived from Sender

The uploader also recognizes common alternatives such as `Date`, `From`, `To`, `Delivery Status`, and `Sender Domain`.

## How the demo risk rules work
The demo marks messages for review if the subject contains urgent/sensitive terms, a sender domain is on a small demo watchlist, a sender has a high message volume, the delivery status indicates failure/rejection/quarantine, or the message is unusually large. Each trigger adds to a simple score:
- `Low`: score 0–1
- `Review`: score 2–3
- `High`: score 4+

These are transparent classroom heuristics, not a real phishing classifier and not proof that an email is malicious. In a real organization, correlate message trace with Microsoft Defender, anti-phishing detections, authentication results, and administrator review.

## Important notes
- All bundled data is fictional and uses reserved `.example` domains.
- The prototype does not connect to Microsoft 365, Microsoft Graph, Exchange Online, or any real mailbox.
- The uploaded CSV is stored locally as `data/current_emails.csv`; clicking Reset sample removes it and returns to the bundled sample.
- This is a classroom prototype. Before deployment, use environment-based secrets, add authentication/authorization, validate uploads more strictly, and avoid uploading confidential organizational mail data to an unapproved system.
