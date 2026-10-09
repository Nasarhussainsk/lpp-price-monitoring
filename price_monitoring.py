"""
LPP price monitoring + violation letter (MySQL: map_projectdb)

Flow
 1. Read tables: seller, seller_mapping, price_list, product_line, promotion, sku
 2. Build and load the price_monitoring table
 3. Violation rule: advertised price must NEVER be below LPP
 4. Save violations to the `violation` table + violations.csv
 5. Email a professional violation letter (CSV attached)

Install:  pip install pandas sqlalchemy pymysql
Table names are lowercase, exactly as MySQL Workbench shows them.
All column names are lower-cased after reading, so case never causes errors.
"""

import smtplib
import os
import re
from datetime import date
from email.message import EmailMessage

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = "localhost"
DB_PORT = 3306
DB_NAME = "map_projectdb"

FX_TO_INR = {"IND": 1.0, "USA": 90.0, "CAN": 65.0, "UK": 120.0, "UAE": 24.5}

SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 587
EMAIL_USER = os.getenv("EMAIL_USER", "your_email@gmail.com")
EMAIL_PASS = os.getenv("EMAIL_PASS", "your_gmail_app_password")
RECIPIENTS = ["recipient@example.com"]

COMPANY_NAME = "Your Company Name"
SENDER_NAME = "Your Name"
SENDER_TITLE = "Pricing & Compliance Team"
CORRECTION_DEADLINE_HOURS = 48
MAX_ROWS_IN_EMAIL = 50     
# full list will be given in CSV

engine = create_engine(URL.create(
    "mysql+pymysql", username=DB_USER, password=DB_PASS,
    host=DB_HOST, port=DB_PORT, database=DB_NAME,
))


def read(table: str) -> pd.DataFrame:
    df = pd.read_sql(f"SELECT * FROM `{table}`", engine)
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def promo_price(map_price, promotion):
    """'20% off ink' or '$10 off laser jet' -> price based on MAP."""
    if not isinstance(promotion, str) or pd.isna(map_price):
        return None
    m = re.match(r"\s*(\$)?(\d+(?:\.\d+)?)(%)?\s*off", promotion, re.I)
    if not m:
        return None
    amt = float(m.group(2))
    return map_price * (1 - amt / 100) if m.group(3) else map_price - amt


def build_price_monitoring() -> pd.DataFrame:
    sku = read("sku")
    seller = read("seller")
    smap = read("seller_mapping").drop_duplicates("seller_name")
    plist = read("price_list").drop_duplicates("sku")
    pline = read("product_line").drop_duplicates("sku")[["sku", "sub_category"]]
    promo = read("promotion").rename(columns={"pl": "product_line"})

    df = seller.merge(smap, on="seller_name", how="left")
    df = df.merge(plist[["sku", "product_line", "map", "lpp"]], on="sku", how="left")
    df = df.merge(pline, on="sku", how="left")

    when = pd.to_datetime(df["last_time_collected"], errors="coerce")
    when = when.fillna(pd.Timestamp.today().normalize())
    df["violation_date"] = when.dt.date
    df["season"] = when.dt.quarter.map(lambda q: f"Q{q}")

    if {"sku", "season", "promotion"}.issubset(promo.columns):
        promo = promo.drop_duplicates(["sku", "season"])[["sku", "season", "promotion"]]
        df = df.merge(promo, on=["sku", "season"], how="left")
    else:
        df["promotion"] = None

    df = df.rename(columns={"map": "map_price"})

    # Convert advertised price of every region into INR (MAP / LPP are in INR)
    rate = df["region"].map(FX_TO_INR)
    if rate.isna().any():
        print("WARNING: no FX rate for regions:", df.loc[rate.isna(), "region"].unique())
    df["advertised_price"] = (df["advertised_price"] * rate).round(2)
    df["promotional_price"] = [promo_price(m, p) for m, p in zip(df["map_price"], df["promotion"])]
    df["category"] = df["product_line"]          # no separate category column in schema

    cols = ["sku", "violation_date", "product_line", "category", "sub_category",
            "region", "marketplace", "seller_name", "homologated_name",
            "map_price", "lpp", "advertised_price", "season", "promotional_price"]
    df = df[cols]
    return df[df["sku"].isin(sku["sku"])]        # price_monitoring has FK to sku

def find_violations(pm: pd.DataFrame) -> pd.DataFrame:
    # advertised_price is already in INR, same as LPP
    v = pm[pm["advertised_price"] < pm["lpp"]].copy()
    v = v.rename(columns={"lpp": "lpp_price"})
    cols = ["sku", "violation_date", "marketplace", "region", "category", "sub_category",
            "map_price", "lpp_price", "advertised_price", "seller_name", "homologated_name"]
    return v[cols].sort_values(["marketplace", "region", "sku"]).reset_index(drop=True)


def save_to_db(pm: pd.DataFrame, v: pd.DataFrame):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM price_monitoring"))
    pm.rename(columns={"lpp": "lpp"}).to_sql(
        "price_monitoring", engine, if_exists="append", index=False, chunksize=1000)
    v.to_sql("violation", engine, if_exists="replace", index=False, chunksize=1000)

def build_letter_html(v: pd.DataFrame, ref: str) -> str:
    shown = v.head(MAX_ROWS_IN_EMAIL)
    by_market = v.groupby("marketplace").size().to_dict()
    summary = ", ".join(f"{k}: {n}" for k, n in by_market.items())
    more = ""
    if len(v) > len(shown):
        more = (f"<p><i>Showing the first {len(shown)} of {len(v)} violations. "
                f"The complete list is in the attached file.</i></p>")
    table = shown.to_html(index=False, border=1, na_rep="-",
                          float_format=lambda x: f"{x:,.2f}")
    return f"""
<div style="font-family:Calibri,Arial,sans-serif;font-size:14px;color:#222">
<p><b>Ref:</b> {ref}<br><b>Date:</b> {date.today():%d %B %Y}</p>
<p><b>Subject: Notice of Price Violation - Advertised Price Below Lowest Permitted Price (LPP)</b></p>
<p>Dear Sir/Madam,</p>
<p>During our routine price monitoring conducted on behalf of {COMPANY_NAME}, we identified
<b>{len(v)}</b> listing(s) advertised at a price below the Lowest Permitted Price (LPP)
for the respective product(s). This is a breach of our pricing policy, under which no
product may be advertised below its LPP on any marketplace.</p>
<p><b>Violations by marketplace:</b> {summary}</p>
<p>The details of the affected listings are given below:</p>
{table}
{more}
<p>We request you to:</p>
<ol>
<li>Correct the advertised price of each listing above to at least the LPP within
<b>{CORRECTION_DEADLINE_HOURS} hours</b> of receiving this notice.</li>
<li>Confirm the corrective action to us in writing by replying to this email.</li>
</ol>
<p>Please note that continued non-compliance may lead to further action as permitted under
our agreement and policies. If you believe any listing has been flagged in error, kindly
share the supporting details and we will review it promptly.</p>
<p>Thank you for your prompt attention to this matter.</p>
<p>Yours sincerely,<br><b>{SENDER_NAME}</b><br>{SENDER_TITLE}<br>{COMPANY_NAME}</p>
</div>"""


def send_violation_email(v: pd.DataFrame):
    ref = f"VN-{date.today():%Y%m%d}"
    html = build_letter_html(v, ref)
    with open("violation_letter.html", "w", encoding="utf-8") as f:
        f.write(html)

    msg = EmailMessage()
    msg["Subject"] = f"Notice of Price Violation - Below LPP [{ref}]"
    msg["From"] = EMAIL_USER
    msg["To"] = ", ".join(RECIPIENTS)
    msg.set_content("Please view this email in an HTML-capable email client.")
    msg.add_alternative(html, subtype="html")
    msg.add_attachment(v.to_csv(index=False).encode("utf-8"), maintype="text",
                       subtype="csv", filename=f"violation_details_{ref}.csv")

    if "your_email" in EMAIL_USER or "recipient@example" in RECIPIENTS[0]:
        print("Email not sent: set EMAIL_USER, EMAIL_PASS and RECIPIENTS first. "
              "Letter saved to violation_letter.html")
        return
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(EMAIL_USER, EMAIL_PASS)
        s.send_message(msg)
    print("Violation email sent to", RECIPIENTS)


if __name__ == "__main__":
    pm = build_price_monitoring()
    v = find_violations(pm)
    save_to_db(pm, v)
    v.to_csv("violations.csv", index=False)
    print(f"price_monitoring rows: {len(pm)} | violations: {len(v)}")
    if len(v):
        send_violation_email(v)
    else:
        print("No violations found. No email sent.")
