import requests
from bs4 import BeautifulSoup
import yfinance as yf
import pandas as pd
import contextlib
import io
import os
import json
import re

url = "https://finviz.com/screener.ashx?v=411&s=ta_topgainers&f=cap_microover,ta_change_u7&ft=4"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def parse_market_cap(text):
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    text_str = str(text).upper().replace(",", "")
    if "B" in text_str:
        try:
            return float(text_str.replace("B", "")) * 1000  # Convert to millions
        except ValueError:
            return None
    elif "M" in text_str:
        try:
            return float(text_str.replace("M", ""))
        except ValueError:
            return None
    else:
        try:
            return float(text_str)
        except ValueError:
            return None

response = requests.get(url, headers=headers)
if response.status_code != 200:
    print(f"Failed to fetch the page. Status code: {response.status_code}")
    exit()

soup_text = response.text

# Extract tickers and Market Cap
filtered_by_cap = []

# Method 1: Parse embedded JSON script tag data (new Finviz layout)
scripts = re.findall(r'<script[^>]*>(.*?)</script>', soup_text, re.DOTALL)
for s in scripts:
    if '"rows"' in s and '"ticker"' in s:
        try:
            data = json.loads(s)
            rows = data.get("data", {}).get("rows", [])
            for r in rows:
                ticker = r.get("text", {}).get("ticker")
                cap = r.get("numbers", {}).get("marketCap")
                if ticker and cap is not None:
                    cap_val = parse_market_cap(cap)
                    # Filter: Market Cap ≥ 100M and ≤ 30B (30000M)
                    if cap_val is not None and 100 <= cap_val <= 30000:
                        filtered_by_cap.append(ticker)
        except Exception:
            pass

# Method 2: Fallback to HTML span attributes (traditional Finviz layout)
if not filtered_by_cap:
    soup = BeautifulSoup(soup_text, "html.parser")
    spans = soup.find_all("span", {"data-boxover-ticker": True})

    for span in spans:
        ticker = span.get("data-boxover-ticker")
        cap_text = span.get("data-boxover-value")

        if ticker and cap_text:
            cap = parse_market_cap(cap_text)
            if cap is not None and 100 <= cap <= 30000:
                filtered_by_cap.append(ticker)

# 200日移動平均線の乖離が-5％以上のものは除外する
# (つまり、(Close - MA200)/MA200 * 100 が -5% 未満は除外、-5%以上は維持)
filtered = []
for ticker in filtered_by_cap:
    f_io = io.StringIO()
    try:
        with contextlib.redirect_stdout(f_io), contextlib.redirect_stderr(f_io):
            t = yf.Ticker(ticker)
            # period='1y' ensures we have at least 200 trading days
            hist = t.history(period="1y")

        if hist.empty:
            continue

        # Handle cases where the DataFrame might have MultiIndex columns (safely extract Series)
        close_col = hist['Close']
        if isinstance(close_col, pd.DataFrame):
            close_series = close_col.iloc[:, 0]
        else:
            close_series = close_col

        if len(close_series) < 200:
            ma200 = close_series.mean()
        else:
            ma200 = close_series.tail(200).mean()

        # extract last close safely
        if isinstance(close_series, pd.Series):
            last_close = close_series.iloc[-1]
        else:
            last_close = close_series[-1]

        # Handle cases where ma200 or last_close might be Series/DataFrame instead of scalars
        if isinstance(ma200, (pd.Series, pd.DataFrame)):
            ma200 = ma200.iloc[0]
        if isinstance(last_close, (pd.Series, pd.DataFrame)):
            last_close = last_close.iloc[0]

        if ma200 and ma200 > 0:
            deviation = ((last_close - ma200) / ma200) * 100
            if deviation >= -5.0:
                filtered.append(ticker)
    except Exception as e:
        continue

# 結果表示
ticker_string = ",".join(filtered)
print("🟩 Market Cap 100M〜30B のティッカー:")
print(ticker_string)

# ログファイル出力
log_path = "C:\\Users\\hydea\\OneDrive\\デスクトップ\\Finviz_log.txt"
try:
    if os.path.dirname(log_path):
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("🟩 Market Cap 100M〜30B のティッカー:\n")
        f.write(ticker_string)
except Exception:
    # Quietly pass if the path is completely unavailable/invalid (e.g. on Linux sandbox)
    pass
