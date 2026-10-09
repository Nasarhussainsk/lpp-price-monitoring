"""
Load a seller-listings CSV into the MySQL table `seller`.
Avoids the Workbench import wizard stopping early on foreign-key errors.

Usage:
    set DB_USER=root & set DB_PASS=...            (Windows CMD)
    python load_seller_data.py path\to\sellers.csv 2025-12-21

CSV columns: SKU, Marketplace, Seller_name, region, adv_price, Screenshot, live_link
(sample_data/seller.csv uses the already-cleaned column names - both work).
"""
import os
import sys

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

csv_path = sys.argv[1]
collected_on = sys.argv[2] if len(sys.argv) > 2 else str(pd.Timestamp.today().date())

engine = create_engine(URL.create(
    "mysql+pymysql", username=os.environ["DB_USER"], password=os.environ["DB_PASS"],
    host="localhost", port=3306, database="map_projectdb"))

df = pd.read_csv(csv_path, encoding="utf-8")
df.columns = [c.strip().lower() for c in df.columns]
df = df.rename(columns={"adv_price": "advertised_price"})
if "last_time_collected" not in df.columns:
    df["last_time_collected"] = collected_on
for c in ("screenshot", "live_link"):
    if c not in df.columns:
        df[c] = None
df = df[["seller_name", "sku", "region", "advertised_price", "marketplace",
         "screenshot", "live_link", "last_time_collected"]]
print("rows in CSV:", len(df))

# 1) SKUs must exist in the sku table (foreign key)
sku_ok = set(pd.read_sql("SELECT sku FROM sku", engine)["sku"])
n = len(df)
df = df[df["sku"].isin(sku_ok)]
print("dropped, SKU not in sku table:", n - len(df))

# 2) Seller names must exist in seller_mapping (foreign key).
#    Missing names are added with an empty Homologated_Name.
known = {x.lower() for x in pd.read_sql("SELECT seller_name FROM seller_mapping", engine)["seller_name"]}
missing = sorted({x for x in df["seller_name"] if x.lower() not in known})
print("sellers added to seller_mapping:", len(missing))
if missing:
    pd.DataFrame({"seller_name": missing}).to_sql(
        "seller_mapping", engine, if_exists="append", index=False)

# 3) Reload seller
with engine.begin() as conn:
    conn.execute(text("DELETE FROM seller"))
df.to_sql("seller", engine, if_exists="append", index=False, chunksize=1000)
print("rows now in seller:", pd.read_sql("SELECT COUNT(*) AS n FROM seller", engine)["n"][0])
