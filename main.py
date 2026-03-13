import yfinance as yf
import pandas as pd
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta   

# Create the Flask app and enable CORS so Power BI can connect
app = Flask(__name__)
CORS(app)

# ETF labels mapped to their Yahoo Finance ticker symbols
# .TO suffix means Toronto Stock Exchange (required for Canadian ETFs)
ETFS = {
    "XEQT": "XEQT.TO",
    "ARKK": "ARKK",
    "SPY":  "SPY",
}

# Fetches raw OHLCV price history from Yahoo Finance for a single ticker
# Default is 5 years of data
def fetch_price_history(ticker, days=365*5):
    end = datetime.today()
    start = end - timedelta(days=days)
    df = yf.download(ticker, start=start, end=end, progress=False)
    df = df.reset_index()
    return df

# Cleans raw data and adds calculated columns
# - Flattens multi-level column headers from yfinance
# - Adds daily_return: % change from previous day's close
# - Adds normalised: growth indexed to 100 from day 1 (for fair comparison)
def clean_price_data(df, label):
    df.columns = [col[0] for col in df.columns]
    df.columns = [c.lower() for c in df.columns]
    df["date"] = df["date"].astype(str)
    df["label"] = label
    df["daily_return"] = df["close"].pct_change() * 100
    df["normalised"] = (df["close"] / df["close"].iloc[0]) * 100
    return df

# Fetch and clean data for all three ETFs, store in a dictionary
price_data = {}
for label, ticker in ETFS.items():
    print(f"Fetching {label}...")
    df = fetch_price_history(ticker)
    df = clean_price_data(df, label)
    price_data[label] = df

# Calculates total return over 1Y, 3Y and 5Y periods for each ETF
# Compares most recent close price against the close price at each period start
def calculate_period_returns():
    periods = {"1Y": 365, "3Y": 365*3, "5Y": 365*5}
    rows = []
    for label, df in price_data.items():
        # End price is always the most recent row
        end_price = df["close"].iloc[-1]
        for period_label, days in periods.items():
            cutoff = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
            subset = df[df["date"] >= cutoff]
            start_price = subset["close"].iloc[0]
            total_return = ((end_price - start_price) / start_price) * 100
            rows.append({
                "label": label,
                "period": period_label,
                "start_price": round(start_price, 2),
                "end_price": round(end_price, 2),
                "total_return": round(total_return, 2)
            })
    return pd.DataFrame(rows)

# Calculates pairwise correlation between ETF daily returns
# Uses long/melted format so Power BI can render it as a heatmap
def calculate_correlation():
    # Pull just the daily_return column from each ETF and put side by side
    returns = pd.DataFrame({
        label: df.set_index("date")["daily_return"]
        for label, df in price_data.items()
    })
    # .corr() calculates correlation between every column pair
    corr = returns.corr().reset_index().rename(columns={"index": "etf"})
    # Melt converts wide matrix into long format: etf, vs_etf, correlation
    corr_melted = corr.melt(id_vars="etf", var_name="vs_etf", value_name="correlation")
    corr_melted["correlation"] = corr_melted["correlation"].round(4)
    return corr_melted

period_returns = calculate_period_returns()

# Combine all three ETF DataFrames into one table for the API
combined = pd.concat(price_data.values(), ignore_index=True)

print("Done!")

# API endpoint: returns full price history for all ETFs
# NaN values replaced with None so JSON serialization works
@app.route("/api/price_history", methods=["GET"])
def price_history():
    data = combined.where(pd.notnull(combined), None)
    return jsonify(data.to_dict(orient="records"))

# API endpoint: returns 1Y, 3Y, 5Y total returns per ETF
@app.route("/api/period_returns", methods=["GET"])
def api_period_returns():
    return jsonify(period_returns.to_dict(orient="records"))

if __name__ == "__main__":
    print("API running at http://localhost:5000")
    app.run(debug=False, port=5000)