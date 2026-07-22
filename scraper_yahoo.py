import requests
from bs4 import BeautifulSoup
import yfinance as yf
import pandas as pd
import time

url = "https://finance.yahoo.co.jp/stocks/ranking/up?market=tokyoAll"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

response = requests.get(url, headers=headers)
if response.status_code != 200:
    exit()

soup = BeautifulSoup(response.text, "html.parser")

# Find the ranking table
table = soup.find("table")
if not table:
    exit()

tbody = table.find("tbody")
if not tbody:
    exit()

rows = tbody.find_all("tr")
results = []

for idx, row in enumerate(rows):
    try:
        # Extract rank from th inside row
        rank_elem = row.find("th")
        if not rank_elem:
            continue
        rank = rank_elem.text.strip()

        # Extract name from anchor tag
        name_elem = row.find("a")
        if not name_elem:
            continue
        name = name_elem.text.strip()

        # Extract stock code from first list item inside supplement section
        li_elem = row.find("li")
        if not li_elem:
            continue
        code = li_elem.text.strip()

        # Get td elements (0: code/market, 1: price, 2: change percent/diff, 3: volume)
        tds = row.find_all("td")
        if len(tds) < 4:
            continue

        # Extraction of change_percent
        # The percentage value is located inside a span with secondary classes containing "+X.XX" and "%"
        change_span = tds[2].find("span", class_=lambda c: c and "secondary" in c)
        if not change_span:
            # Fallback if class changes
            change_percent_text = tds[2].text.strip()
        else:
            change_percent_text = change_span.text.strip()

        # Parse change_percent as float
        change_percent_clean = change_percent_text.replace("+", "").replace("%", "").strip()
        change_percent = float(change_percent_clean)

        # Extraction of volume today (last column)
        volume_today_text = tds[3].text.strip()
        volume_today_clean = volume_today_text.replace(",", "").replace("株", "").strip()
        volume_today = int(volume_today_clean)

    except Exception as e:
        # Silently skip rows that fail parsing
        continue

    # Filter: change percent >= 8%
    if change_percent < 8.0:
        continue

    # Query yfinance (Download 1 year of data to calculate 200-day moving average)
    ticker = f"{code}.T"
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        df = yf.download(ticker, period="1y", progress=False)

    if df.empty:
        continue

    # Get Volume mean safely handling MultiIndex/pandas Series for the last 1 month (20 trading days)
    if "Volume" in df.columns:
        vol_col = df["Volume"]
        # If it's a multi-index DataFrame (e.g. Volume is multi-level under the Ticker name)
        if isinstance(vol_col, pd.DataFrame):
            # Take the first column or locate the ticker name
            if ticker in vol_col.columns:
                vol_series = vol_col[ticker]
            else:
                vol_series = vol_col.iloc[:, 0]
        else:
            vol_series = vol_col

        # Calculate average volume over the last 20 trading days (approx. 1 month)
        avg_volume = vol_series.iloc[-20:].mean()
    else:
        continue

    # Safely convert to a single float value if it's still a Series
    if hasattr(avg_volume, "iloc"):
        avg_volume_val = avg_volume.iloc[0] if len(avg_volume) > 0 else 0
    else:
        avg_volume_val = avg_volume

    if pd.isna(avg_volume_val) or avg_volume_val <= 0:
        continue

    # Get Close series safely handling MultiIndex/pandas Series
    if "Close" in df.columns:
        close_col = df["Close"]
        if isinstance(close_col, pd.DataFrame):
            if ticker in close_col.columns:
                close_series = close_col[ticker]
            else:
                close_series = close_col.iloc[:, 0]
        else:
            close_series = close_col
    else:
        continue

    if not isinstance(close_series, pd.Series):
        close_series = close_series.iloc[:, 0]

    # We need at least 200 trading days of historical data to calculate a 200-day MA
    if len(close_series) < 200:
        continue

    # Calculate 200-day moving average and latest close price
    ma_200 = close_series.iloc[-200:].mean()
    latest_close = close_series.iloc[-1]

    # Safely convert to scalar float if needed
    if hasattr(ma_200, "iloc"):
        ma_200_val = ma_200.iloc[0] if len(ma_200) > 0 else 0
    else:
        ma_200_val = ma_200

    if hasattr(latest_close, "iloc"):
        latest_close_val = latest_close.iloc[0] if len(latest_close) > 0 else 0
    else:
        latest_close_val = latest_close

    if pd.isna(ma_200_val) or ma_200_val <= 0 or pd.isna(latest_close_val):
        continue

    # Check 200-day moving average deviation: (latest_close - ma_200) / ma_200
    # Exclude stocks that are -5% or more below their 200MA (deviation <= -0.05)
    deviation = (latest_close_val - ma_200_val) / ma_200_val
    if deviation <= -0.05:
        continue

    # Check volume condition: volume_today >= avg_volume * 1.3
    if volume_today >= avg_volume_val * 1.3:
        results.append({
            "code": code,
            "name": name,
            "change_percent": change_percent,
            "volume_today": volume_today,
            "avg_volume": int(avg_volume_val)
        })

if results:
    codes = [res["code"] for res in results]
    print(",".join(codes))
