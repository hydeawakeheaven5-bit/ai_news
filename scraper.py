import requests
from bs4 import BeautifulSoup

url = "https://finviz.com/screener.ashx?v=411&s=ta_topgainers&f=cap_microover,ta_change_u7&ft=4"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def parse_market_cap(text):
    if not text:
        return None
    text = text.upper().replace(",", "")
    if "B" in text:
        try:
            return float(text.replace("B", "")) * 1000  # Convert to millions
        except ValueError:
            return None
    elif "M" in text:
        try:
            return float(text.replace("M", ""))
        except ValueError:
            return None
    else:
        try:
            # Maybe it's just a number (millions) or something else
            return float(text)
        except ValueError:
            return None

response = requests.get(url, headers=headers)
if response.status_code != 200:
    print(f"Failed to fetch the page. Status code: {response.status_code}")
    exit()

soup = BeautifulSoup(response.text, "html.parser")

# <span>タグからティッカーとMarket Capを抽出
filtered = []
spans = soup.find_all("span", {"data-boxover-ticker": True})

for span in spans:
    ticker = span.get("data-boxover-ticker")
    cap_text = span.get("data-boxover-value")

    if ticker and cap_text:
        cap = parse_market_cap(cap_text)
        # フィルタ処理：Market Cap ≥ 100M and ≤ 30B (30000M)
        if cap is not None and 100 <= cap <= 30000:
            filtered.append(ticker)

# 結果表示
ticker_string = ",".join(filtered)
print("📊 Market Cap 100M〜30B のティッカー:")
print(ticker_string)
