"""
Run the full pipeline on the bundled SYNTHETIC sample data - no MySQL needed.
Writes price_monitoring.csv, violations.csv and an example violation letter
into sample_output/.

    python run_demo.py
"""
import os
import pandas as pd

import price_monitoring as pm

DATA_DIR, OUT_DIR = "sample_data", "sample_output"
os.makedirs(OUT_DIR, exist_ok=True)


def read_csv_table(table: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(DATA_DIR, f"{table}.csv"))
    df.columns = [c.strip().lower() for c in df.columns]
    return df


pm.read = read_csv_table                      # read CSVs instead of MySQL
pm.COMPANY_NAME = "Example Company"
pm.SENDER_NAME = "Pricing Analyst"

monitor = pm.build_price_monitoring()
violations = pm.find_violations(monitor)

monitor.to_csv(os.path.join(OUT_DIR, "price_monitoring.csv"), index=False)
violations.to_csv(os.path.join(OUT_DIR, "violations.csv"), index=False)
with open(os.path.join(OUT_DIR, "violation_letter_example.html"), "w", encoding="utf-8") as f:
    f.write(pm.build_letter_html(violations, "VN-DEMO"))

print(f"listings monitored : {len(monitor)}")
print(f"violations (< LPP) : {len(violations)}")
print(violations.groupby("marketplace").size().to_string())
