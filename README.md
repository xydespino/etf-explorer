# ETF Explorer

A Python data pipeline and Power BI dashboard for comparing XEQT, ARKK, and SPY (S&P 500).

## What it does
- Pulls 5 years of historical price data from Yahoo Finance
- Calculates normalised returns, daily returns, drawdown, and correlation
- Serves data via a REST API built with Flask
- Connects directly to Power BI for interactive visualisation

## Tech Stack
Python · Flask · pandas · yfinance · Power BI

## API Endpoints
| Endpoint | Description |
|---|---|
| `/api/price_history` | Full OHLCV + calculated metrics for all ETFs |
| `/api/period_returns` | 1Y / 3Y / 5Y total return by ETF |
| `/api/correlation` | Pairwise return correlation matrix |
| `/api/etf_info` | ETF metadata, AUM, expense ratio *(coming soon)* |

## How to run
```bash
pip install -r requirements.txt
python main.py
```
Then open Power BI and connect via Web connector to `http://localhost:5000`

## Key Findings
- XEQT vs SPY correlation: 0.91 — highly correlated due to US equity exposure
- ARKK 5Y return: -41% vs SPY 5Y: +84% — growth vs stability tradeoff
- Normalised returns chart shows relative performance from a common $100 starting point
