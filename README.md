# LPP Price Monitoring

Python + MySQL pipeline that monitors marketplace listings and flags any product **advertised below its Lowest Permitted Price (LPP)**. It stores the monitoring results in MySQL and generates a professional **violation letter** (HTML email with the full CSV attached).

> All data in this repository is **synthetic**. Real client data is not included.

## The problem
Brands set a MAP (Minimum Advertised Price) and an LPP for every SKU. Sellers on marketplaces such as Amazon, Flipkart, eBay and Snapdeal sometimes advertise below LPP, across several regions and currencies. Checking this by hand is slow, so this project automates detection and reporting.

## What it does
1. Reads the source tables from MySQL: `sku`, `product_line`, `price_list`, `seller_mapping`, `promotion`, `seller`.
2. Joins them into a **`price_monitoring`** table (SKU, region, marketplace, seller, MAP, LPP, advertised price, season, promotional price).
3. Converts advertised prices from local currency to **INR**, because MAP and LPP are stored in INR.
4. Flags a **violation** when `advertised_price < LPP`, and saves these rows to a `violation` table.
5. Builds a formal violation letter (HTML) and emails it with the full violation list attached as CSV.

## Tech stack
Python, pandas, SQLAlchemy, PyMySQL, MySQL, smtplib (email), Jupyter.

## Project structure
```
.
├── notebooks/Minimum_Advertised_Price.ipynb   # step-by-step notebook
├── price_monitoring.py                        # same code as a runnable module
├── load_seller_data.py                        # bulk-load seller CSV into MySQL
├── run_demo.py                                # run everything on sample data (no MySQL)
├── schema.sql                                 # MySQL table definitions
├── sample_data/                               # synthetic input tables (CSV)
├── sample_output/                             # example results + example letter
└── requirements.txt
```

## Quick start (no database needed)
```bash
pip install -r requirements.txt
python run_demo.py
```
This reads `sample_data/` and writes the monitoring table, the violation list and an example letter to `sample_output/`. On the synthetic data it checks 300 listings and finds 91 violations.

Open `sample_output/violation_letter_example.html` in a browser to see the letter.

## Run against MySQL
1. Create the tables with `schema.sql` and load your data (`load_seller_data.py` helps with the seller table).
2. Set credentials as environment variables (never hard-code them):
   ```bash
   # Windows PowerShell
   $env:DB_USER="root"
   $env:DB_PASS="your_password"
   $env:EMAIL_USER="you@gmail.com"
   $env:EMAIL_PASS="your_gmail_app_password"
   ```
3. Edit `RECIPIENTS`, `COMPANY_NAME` and `SENDER_NAME` in the config section, then run the notebook or `price_monitoring.py`.

If email settings are left at their defaults, the script skips sending and only saves the letter as `violation_letter.html`.

## Assumptions
- MAP and LPP are in **INR**.
- `FX_TO_INR` holds placeholder exchange rates. Replace them with real rates for the data's collection date.
- `Category` is taken from `Product_Line`, as the schema has no separate category column.
- Promotion text such as "20% off" is converted to a promotional price based on MAP. It does not affect the violation rule.

## Possible improvements
- Fetch live exchange rates automatically.
- Schedule daily runs and send one letter per seller.
- Add a dashboard for violation trends by marketplace and region.
