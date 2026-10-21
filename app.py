from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from pathlib import Path
from io import BytesIO
from datetime import datetime
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import inch

app = Flask(__name__)
app.secret_key = "mailscope-demo-key-change-for-real-deployment"
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
UPLOAD_DIR = ROOT / "uploads"
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
SAMPLE_FILE = DATA_DIR / "sample_emails.csv"
CURRENT_FILE = DATA_DIR / "current_emails.csv"

REQUIRED_COLUMNS = ["Timestamp", "Sender", "Recipient", "Direction", "Subject", "Status", "SizeKB", "SenderDomain"]

def load_data():
    path = CURRENT_FILE if CURRENT_FILE.exists() else SAMPLE_FILE
    try:
        df = pd.read_csv(path)
    except Exception:
        df = pd.read_csv(SAMPLE_FILE)
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    df["SizeKB"] = pd.to_numeric(df["SizeKB"], errors="coerce").fillna(0)
    for col in ["Sender", "Recipient", "Direction", "Subject", "Status", "SenderDomain"]:
        df[col] = df[col].fillna("").astype(str)
    df["Direction"] = df["Direction"].str.title()
    df["Status"] = df["Status"].str.title()
    return df

def analyze(df):
    if df.empty:
        return df.assign(RiskScore=[], RiskLevel=[], RiskReasons=[])
    flagged = []
    scores = []
    reasons_col = []
    sender_counts = df["Sender"].str.lower().value_counts().to_dict()
    for _, row in df.iterrows():
        reasons = []
        score = 0
        domain = str(row["SenderDomain"]).lower().strip()
        sender = str(row["Sender"]).lower()
        subject = str(row["Subject"]).lower()
        status = str(row["Status"]).lower()
        # Heuristic demo rules; these are indicators, not a verdict.
        if any(term in subject for term in ["urgent", "password", "verify account", "invoice overdue", "wire transfer", "gift card"]):
            score += 2
            reasons.append("Urgent or sensitive wording in subject")
        if domain in {"unknown.example", "mail-secure.example", "paypaI.example"} or domain.endswith(".invalid"):
            score += 2
            reasons.append("Domain is in the demo watchlist / invalid namespace")
        if sender_counts.get(sender, 0) >= 8:
            score += 1
            reasons.append("High message volume from sender")
        if status in {"failed", "rejected", "quarantined"}:
            score += 1
            reasons.append("Delivery failed, rejected, or quarantined")
        if float(row["SizeKB"]) > 15000:
            score += 1
            reasons.append("Unusually large message attachment/size")
        scores.append(score)
        reasons_col.append("; ".join(reasons) if reasons else "No demo rule triggered")
    result = df.copy()
    result["RiskScore"] = scores
    result["RiskLevel"] = ["High" if s >= 4 else "Review" if s >= 2 else "Low" for s in scores]
    result["RiskReasons"] = reasons_col
    return result

def filtered_data(args):
    df = analyze(load_data())
    q = (args.get("q") or "").strip().lower()
    direction = args.get("direction", "All")
    status = args.get("status", "All")
    risk = args.get("risk", "All")
    start = args.get("start", "")
    end = args.get("end", "")
    if q:
        mask = df[["Sender", "Recipient", "Subject", "SenderDomain"]].astype(str).apply(
            lambda col: col.str.lower().str.contains(q, regex=False, na=False)
        ).any(axis=1)
        df = df[mask]
    if direction in {"Sent", "Received"}:
        df = df[df["Direction"] == direction]
    if status != "All":
        df = df[df["Status"].str.lower() == status.lower()]
    if risk in {"High", "Review", "Low"}:
        df = df[df["RiskLevel"] == risk]
    if start:
        df = df[df["Timestamp"] >= pd.to_datetime(start, errors="coerce")]
    if end:
        df = df[df["Timestamp"] < (pd.to_datetime(end, errors="coerce") + pd.Timedelta(days=1))]
    return df.sort_values("Timestamp", ascending=False, na_position="last")

@app.route("/")
def index():
    df = analyze(load_data())
    summary = {
        "total": int(len(df)),
        "sent": int((df["Direction"] == "Sent").sum()),
        "received": int((df["Direction"] == "Received").sum()),
        "failed": int(df["Status"].str.lower().isin(["failed", "rejected", "quarantined"]).sum()),
        "flagged": int((df["RiskLevel"].isin(["High", "Review"])).sum()),
        "high": int((df["RiskLevel"] == "High").sum()),
    }
    return render_template("index.html", summary=summary, source="Uploaded report" if CURRENT_FILE.exists() else "Fictional sample data")

@app.route("/api/emails")
def api_emails():
    df = filtered_data(request.args)
    safe = df.copy()
    safe["Timestamp"] = safe["Timestamp"].dt.strftime("%Y-%m-%d %H:%M").fillna("")
    rows = safe[REQUIRED_COLUMNS + ["RiskScore", "RiskLevel", "RiskReasons"]].to_dict(orient="records")
    summary = {
        "total": int(len(df)),
        "sent": int((df["Direction"] == "Sent").sum()),
        "received": int((df["Direction"] == "Received").sum()),
        "failed": int(df["Status"].str.lower().isin(["failed", "rejected", "quarantined"]).sum()),
        "flagged": int(df["RiskLevel"].isin(["High", "Review"]).sum()),
        "high": int((df["RiskLevel"] == "High").sum()),
    }
    by_day = df.dropna(subset=["Timestamp"]).assign(Day=lambda x: x["Timestamp"].dt.strftime("%b %d")).groupby(["Day", "Direction"]).size().unstack(fill_value=0)
    daily = [{"day": str(idx), "sent": int(row.get("Sent", 0)), "received": int(row.get("Received", 0))} for idx, row in by_day.iterrows()]
    risk_counts = df["RiskLevel"].value_counts().to_dict()
    status_counts = df["Status"].value_counts().to_dict()
    return jsonify({"rows": rows, "summary": summary, "daily": daily,
                    "risk": {k: int(v) for k, v in risk_counts.items()},
                    "statuses": {k: int(v) for k, v in status_counts.items()}})

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("report")
    if not file or not file.filename:
        flash("Choose a CSV file first.", "error")
        return redirect(url_for("index"))
    if not file.filename.lower().endswith(".csv"):
        flash("Only CSV files are supported.", "error")
        return redirect(url_for("index"))
    try:
        df = pd.read_csv(file)
        # Accept common column-name variations.
        rename = {}
        aliases = {
            "Timestamp": ["timestamp", "date", "datetime", "received time", "date time"],
            "Sender": ["sender", "from", "sender address", "from address"],
            "Recipient": ["recipient", "to", "recipient address", "to address"],
            "Direction": ["direction", "mail direction", "type"],
            "Subject": ["subject", "message subject"],
            "Status": ["status", "delivery status", "result"],
            "SizeKB": ["sizekb", "size kb", "message size kb", "size"],
            "SenderDomain": ["senderdomain", "sender domain", "domain"],
        }
        lookup = {str(c).strip().lower(): c for c in df.columns}
        for target, variants in aliases.items():
            for v in [target.lower()] + variants:
                if v in lookup:
                    rename[lookup[v]] = target
                    break
        df = df.rename(columns=rename)
        missing = [c for c in ["Timestamp", "Sender", "Recipient", "Direction", "Subject", "Status"] if c not in df.columns]
        if missing:
            flash("CSV is missing required columns: " + ", ".join(missing), "error")
            return redirect(url_for("index"))
        if "SizeKB" not in df.columns:
            df["SizeKB"] = 0
        if "SenderDomain" not in df.columns:
            df["SenderDomain"] = df["Sender"].astype(str).str.rsplit("@", n=1).str[-1]
        df["Direction"] = df["Direction"].astype(str).str.title().replace({"Outbound": "Sent", "Incoming": "Received", "Inbound": "Received"})
        df[REQUIRED_COLUMNS].to_csv(CURRENT_FILE, index=False)
        flash(f"Successfully loaded {len(df)} email records.", "success")
    except Exception as exc:
        flash(f"Could not read CSV: {exc}", "error")
    return redirect(url_for("index"))

@app.route("/reset")
def reset():
    if CURRENT_FILE.exists():
        CURRENT_FILE.unlink()
    flash("Restored the fictional sample dataset.", "success")
    return redirect(url_for("index"))

@app.route("/report.pdf")
def report_pdf():
    df = filtered_data(request.args)
    summary = {
        "Total emails": len(df),
        "Sent": int((df["Direction"] == "Sent").sum()),
        "Received": int((df["Direction"] == "Received").sum()),
        "Delivery failures": int(df["Status"].str.lower().isin(["failed", "rejected", "quarantined"]).sum()),
        "Flagged for review": int(df["RiskLevel"].isin(["High", "Review"]).sum()),
        "High risk": int((df["RiskLevel"] == "High").sum()),
    }
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=32, leftMargin=32, topMargin=32, bottomMargin=32)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("MailScope — Email Traffic & Security Report", styles["Title"]),
        Paragraph("Demonstration report based on a CSV email message trace. Risk flags are heuristic indicators, not proof of malicious activity.", styles["BodyText"]),
        Spacer(1, 12),
        Paragraph("Summary", styles["Heading2"]),
    ]
    summary_data = [["Metric", "Count"]] + [[k, str(v)] for k, v in summary.items()]
    table = Table(summary_data, colWidths=[2.5*inch, 1.1*inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#172B4D")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), .4, colors.HexColor("#d9dfeb")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f5f7fb")]),
        ("PADDING", (0,0), (-1,-1), 6),
    ]))
    story += [table, Spacer(1, 14), Paragraph("Flagged messages (up to 40)", styles["Heading2"])]
    flagged = df[df["RiskLevel"].isin(["High", "Review"])].head(40)
    data = [["Timestamp", "Sender", "Recipient", "Subject", "Status", "Risk", "Reason"]]
    for _, r in flagged.iterrows():
        data.append([
            str(r["Timestamp"].strftime("%Y-%m-%d %H:%M") if pd.notna(r["Timestamp"]) else ""),
            str(r["Sender"])[:32], str(r["Recipient"])[:32], str(r["Subject"])[:38],
            str(r["Status"]), str(r["RiskLevel"]), str(r["RiskReasons"])[:65]
        ])
    if len(data) == 1:
        data.append(["—", "No flagged messages", "", "", "", "", ""])
    t = Table(data, repeatRows=1, colWidths=[1.05*inch, 1.35*inch, 1.35*inch, 1.7*inch, .75*inch, .65*inch, 2.2*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#172B4D")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 7),
        ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#d9dfeb")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f5f7fb")]),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("PADDING", (0,0), (-1,-1), 4),
    ]))
    story += [t, Spacer(1, 10), Paragraph("Generated by MailScope demo • Use verified security tooling and administrator review before taking action.", styles["Italic"])]
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="mailscope_email_report.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    app.run(debug=True)
