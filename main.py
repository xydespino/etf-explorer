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

print(price_data["ARKK"][["date", "label", "close", "normalised"]].head())