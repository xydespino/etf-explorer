import yfinance as yf
import pandas as pd
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta   

app = Flask(__name__)
CORS(app)

ETFS = {
    "XEQT": "XEQT.TO",
    "ARKK": "ARKK",
    "SPY":  "SPY",
}

def fetch_price_history(ticker, days=365*5):
    end = datetime.today()
    start = end - timedelta(days=days)
    df = yf.download(ticker, start=start, end=end, progress=False)
    df = df.reset_index()
    return df

# Test
# df = fetch_price_history("SPY")
# print(df.head())

def clean_price_data(df, label):
    df.columns = [col[0] for col in df.columns]
    df.columns = [c.lower() for c in df.columns]
    df["date"] = df["date"].astype(str)
    df["label"] = label
    df["daily_return"] = df["close"].pct_change() * 100
    df["normalised"] = (df["close"] / df["close"].iloc[0]) * 100
    return df

price_data = {}

for label, ticker in ETFS.items():
    print(f"Fetching {label}...")
    df = fetch_price_history(ticker)
    df = clean_price_data(df, label)
    price_data[label] = df

print("Done!")

combined = pd.concat(price_data.values(), ignore_index=True)

@app.route("/api/price_history", methods=["GET"])
def price_history():
    data = combined.where(pd.notnull(combined), None)
    return jsonify(data.to_dict(orient="records"))

if __name__ == "__main__":
    print("API running at http://localhost:5000")
    app.run(debug=False, port=5000)
