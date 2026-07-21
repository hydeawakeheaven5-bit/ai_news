import requests
from bs4 import BeautifulSoup
import yfinance as yf
import pandas as pd
import time

url = "https://finance.yahoo.co.jp/stocks/ranking/up?market=tokyoAll"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

print("Fetching data from Yahoo! Finance Japan...")
response = requests.get(url, headers=headers)
if response.status_code != 200:
    print(f"Failed to fetch. Status code: {response.status_code}")
    exit()

soup = BeautifulSoup(response.text, "html.parser")

# Find the ranking table
table = soup.find("table")
if not table:
    print("Could not find the ranking table.")
    exit()

tbody = table.find("tbody")
if not tbody:
    print("Could not find the table body.")
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

    # Query yfinance
    ticker = f"{code}.T"
    print(f"Downloading historical data for {ticker} ({name})...")
    df = yf.download(ticker, period="1mo", progress=False)

    if df.empty:
        continue

    # Get Volume mean safely handling MultiIndex/pandas Series
    if "Volume" in df.columns:
        vol_col = df["Volume"]
        # If it's a multi-index DataFrame (e.g. Volume is multi-level under the Ticker name)
        if isinstance(vol_col, pd.DataFrame):
            # Take the first column or locate the ticker name
            if ticker in vol_col.columns:
                avg_volume = vol_col[ticker].mean()
            else:
                avg_volume = vol_col.iloc[:, 0].mean()
        else:
            avg_volume = vol_col.mean()
    else:
        continue

    # Safely convert to a single float value if it's still a Series
    if hasattr(avg_volume, "iloc"):
        avg_volume_val = avg_volume.iloc[0] if len(avg_volume) > 0 else 0
    else:
        avg_volume_val = avg_volume

    if pd.isna(avg_volume_val) or avg_volume_val <= 0:
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

df_out = pd.DataFrame(results)
print("\n--- RESULTS ---")
print(df_out)
