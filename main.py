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
# def clean_price_data(df, label):
#     # Handle both tuple and string column names from yfinance
#     df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
#     df.columns = [c.lower() for c in df.columns]
#     df["date"] = df["date"].astype(str)
#     df["label"] = label
#     df["daily_return"] = df["close"].pct_change() * 100
#     df["normalised"] = (df["close"] / df["close"].iloc[0]) * 100
#     df["rolling_max"] = df["close"].cummax()
#     df["drawdown"] = ((df["close"] - df["rolling_max"]) / df["rolling_max"]) * 100
#     return df

def clean_price_data(df, label):
    df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
    df.columns = [c.lower() for c in df.columns]
    print(f"{label} after lowercase: {list(df.columns)}")
    print(f"{label} close tail: {df['close'].tail(3)}")
    df["date"] = df["date"].astype(str)
    df["label"] = label
    df["daily_return"] = df["close"].pct_change() * 100
    df["normalised"] = (df["close"] / df["close"].iloc[0]) * 100
    df["rolling_max"] = df["close"].cummax()
    df["drawdown"] = ((df["close"] - df["rolling_max"]) / df["rolling_max"]) * 100
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
        # Drop NaN rows before getting end price — yfinance appends empty rows
        clean_df = df.dropna(subset=["close"])
        end_price = float(clean_df["close"].iloc[-1])
        for period_label, days in periods.items():
            cutoff = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
            subset = clean_df[clean_df["date"] >= cutoff]
            start_price = float(subset["close"].iloc[0])
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

# Fetches ETF metadata from Yahoo Finance for each ETF
# Returns key stats: name, AUM, expense ratio, YTD return, 52 week range
def fetch_etf_info():
    rows = []
    for label, ticker in ETFS.items():
        try:
            t = yf.Ticker(ticker)
            # fast_info is more reliable than info on newer Python versions
            fi = t.fast_info
            rows.append({
                "label":        label,
                "ticker":       ticker,
                "currency":     fi.get("currency", "N/A"),
                "52w_high":     fi.get("year_high", None),
                "52w_low":      fi.get("year_low", None),
                "aum_billions": round(fi.get("total_assets", 0) / 1e9, 2) if fi.get("total_assets") else None,
            })
        except Exception as e:
            print(f"Could not fetch info for {label}: {e}")
            rows.append({"label": label, "ticker": ticker})
    return pd.DataFrame(rows)

# Fetches top holdings and sector weights for each ETF
def fetch_holdings():
    rows = []
    for label, ticker in ETFS.items():
        try:
            t = yf.Ticker(ticker)
            # Get sector weightings
            sector_weights = t.funds_data.sector_weightings
            for sector, weight in sector_weights.items():
                rows.append({
                    "label": label,
                    "sector": sector,
                    "weight": round(weight * 100, 2)
                })
        except Exception as e:
            print(f"Could not fetch holdings for {label}: {e}")
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["label", "sector", "weight"]
    )

# Combine all three ETF DataFrames into one table for the API
combined = pd.concat(price_data.values(), ignore_index=True)
period_returns = calculate_period_returns()
correlation = calculate_correlation()
etf_info = fetch_etf_info()
holdings = fetch_holdings()
print("Done!")

# API endpoint: returns full price history for all ETFs
# NaN values replaced with None so JSON serialization works
@app.route("/api/price_history", methods=["GET"])
def price_history():
    data = combined.copy()
    # Replace all NaN/inf values with None for clean JSON serialization
    data = data.where(pd.notnull(data), None)
    data = data.replace([float('inf'), float('-inf')], None)
    records = data.to_dict(orient="records")
    # Final safety pass — replace any remaining float NaN
    import math
    cleaned = []
    for row in records:
        cleaned.append({
            k: None if isinstance(v, float) and math.isnan(v) else v
            for k, v in row.items()
        })
    return jsonify(cleaned)

# API endpoint: returns 1Y, 3Y, 5Y total returns per ETF
@app.route("/api/period_returns", methods=["GET"])
def api_period_returns():
    records = period_returns.to_dict(orient="records")
    cleaned = []
    for row in records:
        clean_row = {}
        for k, v in row.items():
            if v is None:
                clean_row[k] = None
            elif isinstance(v, float):
                import math
                clean_row[k] = None if math.isnan(v) or math.isinf(v) else round(v, 4)
            else:
                clean_row[k] = v
        cleaned.append(clean_row)
    return jsonify(cleaned)

# API endpoint: pairwise correlation matrix between ETF daily returns
@app.route("/api/correlation", methods=["GET"])
def api_correlation():
    return jsonify(correlation.to_dict(orient="records"))

@app.route("/api/etf_info", methods=["GET"])
def api_etf_info():
    data = etf_info.where(pd.notnull(etf_info), None)
    return jsonify(data.to_dict(orient="records"))

@app.route("/api/holdings", methods=["GET"])
def api_holdings():
    import math
    records = holdings.to_dict(orient="records")
    cleaned = []
    for row in records:
        clean_row = {}
        for k, v in row.items():
            if isinstance(v, float):
                clean_row[k] = None if math.isnan(v) else round(v, 4)
            else:
                clean_row[k] = v
        cleaned.append(clean_row)
    return jsonify(cleaned)

if __name__ == "__main__":
    print("API running at http://localhost:5000")
    app.run(debug=True, port=5000)