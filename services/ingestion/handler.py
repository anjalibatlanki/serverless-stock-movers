import os
import json
import time
import datetime as dt
from decimal import Decimal
import urllib.request
import urllib.parse
import boto3

#initialization
dynamodb = boto3.resource("dynamodb")

#environment variables for configuration
TABLE_NAME = os.environ["MOVERS_TABLE_NAME"]
PK_VALUE = os.environ.get("MOVERS_TABLE_PK", "MOVERS")
API_KEY = os.environ.get("MASSIVE_API_KEY", "")
WATCHLIST = [t.strip() for t in os.environ.get("WATCHLIST", "").split(",") if t.strip()]

BASE_URL = "https://api.massive.com"

#standardizes error handling for network/API failures.
def http_get_json(url: str, max_retries: int = 4) -> dict:
    last_err = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except Exception as e:
            last_err = e
            # simple exponential backoff for rate limits/transient failures
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise last_err

#fetches market data for a specific ticker and date.
def fetch_open_close_for_date(ticker: str, date_str: str) -> tuple[Decimal, Decimal]:
    """
    Massive daily open/close endpoint example format:
    https://api.massive.com/v1/open-close/<TICKER>/<YYYY-MM-DD>?apiKey=YOUR_API_KEY
    """
    if not API_KEY:
        raise RuntimeError("Missing MASSIVE_API_KEY env var")

    url = f"{BASE_URL}/v1/open-close/{ticker}/{date_str}?{urllib.parse.urlencode({'apiKey': API_KEY})}"
    data = http_get_json(url)

    # Be tolerant to field naming (docs/examples typically return open/close)
    # Common keys: open/close OR o/c
    o = data.get("open", data.get("o"))
    c = data.get("close", data.get("c"))

    # If Massive returns status/error, surface it
    if o is None or c is None:
        status = data.get("status")
        message = data.get("message") or data.get("error")
        raise RuntimeError(f"No open/close for {ticker} on {date_str}. status={status} msg={message}")

    return (Decimal(str(o)), Decimal(str(c)))
#handles market closures (weekends/holidays) by stepping backward from start_date until valid data is found.
def fetch_latest_trading_day_open_close(ticker: str, start_date: dt.date, lookback_days: int = 7):
    """
    Try start_date, then go backwards until we find a day with data (weekends/holidays safe).
    """
    for i in range(lookback_days + 1):
        d = start_date - dt.timedelta(days=i)
        date_str = d.isoformat()
        try:
            o, c = fetch_open_close_for_date(ticker, date_str)
            return d, o, c
        except Exception:
            continue
    raise RuntimeError(f"No trading data found for {ticker} within {lookback_days} days of {start_date.isoformat()}")

def percent_change(o: Decimal, c: Decimal) -> Decimal:
    # ((Close - Open) / Open) * 100
    return ((c - o) / o) * Decimal("100")

def http_get_json(url: str, max_retries: int = 2) -> dict:
    last_err = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=8) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(1 + attempt)  # small backoff
            else:
                raise last_err
#Lambda entry point. Iterates through the watchlist, identifies the 'biggest mover', and saves that record to DynamoDB.
def main(event, context):
    table = dynamodb.Table(TABLE_NAME)

    if not WATCHLIST:
        raise RuntimeError("WATCHLIST env var is empty")

    # Use UTC date for consistency
    today = dt.datetime.utcnow().date()

    best = None
    used_date = None
    errors = []
# Find the most recent active trading day for this ticker
    for ticker in WATCHLIST:
        try:
            d, o, c = fetch_latest_trading_day_open_close(ticker, today, lookback_days=7)
            pct = percent_change(o, c)

            if best is None or abs(pct) > abs(best["percentChange"]):
                best = {
                    "ticker": ticker,
                    "percentChange": pct,
                    "closePrice": c,
                }
                used_date = d
        except Exception as e:
            errors.append(f"{ticker}: {str(e)}")
            continue

    if best is None or used_date is None:
        raise RuntimeError(f"All tickers failed. Errors: {errors}")
# Prepare DynamoDB item
    item = {
        "pk": PK_VALUE,
        "date": used_date.isoformat(),
        "ticker": best["ticker"],
        "percentChange": best["percentChange"],  # Decimal ok for DynamoDB
        "closePrice": best["closePrice"],        # Decimal ok for DynamoDB
    }

    table.put_item(Item=item)
	# Return summary
    return {"statusCode": 200, "body": json.dumps({
        "saved": {
            "pk": item["pk"],
            "date": item["date"],
            "ticker": item["ticker"],
            "percentChange": str(item["percentChange"]),
            "closePrice": str(item["closePrice"]),
        },
        "errors": errors
    })}
