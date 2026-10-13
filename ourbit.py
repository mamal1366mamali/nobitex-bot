import json
import os
import requests
import jdatetime
from datetime import datetime, timedelta

BOT_TOKEN = os.environ.get("ROSHD_BOT_TOKEN", "")
CHANNEL_ID = "-1003961062602"
DATA_FILE = "ourbit_data.json"

API_URL = "https://futures.ourbit.com/api/v1/contract/ticker"
KLINES_URL = "https://futures.ourbit.com/api/v1/contract/kline"

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"history": {}, "alerted": {}, "daily_count": 0, "last_date": ""}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def format_volume(val):
    if val >= 1_000_000_000:
        return f'{val / 1_000_000_000:.2f}B'
    elif val >= 1_000_000:
        return f'{val / 1_000_000:.2f}M'
    elif val >= 1_000:
        return f'{val / 1_000:.0f}K'
    else:
        return f'{int(val)}'

def main():
    data = load_data()
    
    iran_time = datetime.utcnow() + timedelta(hours=3, minutes=30)
    today_str = jdatetime.datetime.fromgregorian(datetime=iran_time).strftime("%Y/%m/%d")
    
    if data.get("last_date") != today_str:
        data["daily_count"] = 0
        data["last_date"] = today_str
        data["alerted"] = {}

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(API_URL, headers=headers, timeout=15)
        res_json = response.json()
        tickers = res_json.get("data", []) if isinstance(res_json, dict) else res_json
    except Exception as e:
        print(f"Error fetching data: {e}")
        return

    # Process all tickers
    for ticker in tickers:
        try:
            symbol_raw = ticker.get("symbol", "")
            symbol = symbol_raw.upper()
            if not symbol.endswith("_USDT") and not symbol.endswith("USDT"):
                continue
            if symbol_raw.startswith("~~"):
                continue
            
            import re
            name = symbol.replace("_USDT", "").replace("USDT", "").lower()
            
            # Skip prediction tokens like 10964yes or 10964no
            if re.search(r'\d+(yes|no)', name) or name.endswith("yes") or name.endswith("no"):
                continue
                
            current_price = float(ticker.get("lastPrice", 0))
            low_price = float(ticker.get("lower24Price", 0))
            high_price = float(ticker.get("high24Price", 0))
            day_change = float(ticker.get("riseFallRate", 0)) * 100
            
            if name not in data.get("history", {}):
                if "history" not in data:
                    data["history"] = {}
                data["history"][name] = []
                
            # Append current price
            data["history"][name].append(current_price)
            
            # Keep only last 16 (4 hours of 15m intervals)
            if len(data["history"][name]) > 16:
                data["history"][name] = data["history"][name][-16:]
                
            # Check growth
            if len(data["history"][name]) > 1:
                min_price_4h = min(data["history"][name])
                if min_price_4h > 0:
                    growth = ((current_price - min_price_4h) / min_price_4h) * 100
                    
                    if growth >= 8.0:
                        # Check if already alerted today
                        if data.get("alerted", {}).get(name) != today_str:
                            
                            # Calculate rolling volume from klines
                            curr_4h_vol = 0
                            prev_4h_vol = 0
                            try:
                                k_url = f"{KLINES_URL}/{symbol_raw}?interval=Min15"
                                k_resp = requests.get(k_url, headers=headers, timeout=10)
                                k_res = k_resp.json()
                                if k_res.get("success") and "data" in k_res:
                                    amounts = k_res["data"].get("amount", [])
                                    if len(amounts) >= 16:
                                        curr_4h_vol = sum([float(v) for v in amounts[-16:]])
                                        prev_4h_vol = sum([float(v) for v in amounts[-32:-16]]) if len(amounts) >= 32 else 0
                            except:
                                pass
                            
                            # Fake vs Real logic based on user rules
                            if prev_4h_vol == 0:
                                vol_status = "ریسک برای معامله"
                            elif curr_4h_vol > prev_4h_vol * 2.0:
                                vol_status = "مناسب معامله لانگ"
                            elif curr_4h_vol <= prev_4h_vol * 1.3:
                                vol_status = "پامپ فیک عالی (مناسب معامله شورت)"
                            else:
                                vol_status = "ریسک برای معامله"

                            data["daily_count"] += 1
                            sign = "+" if day_change > 0 else ""
                            
                            msg = (
                                f"{data['daily_count']}\n"
                                f"نام: {name}\n"
                                f"درصد رشد (۴ ساعته): +{growth:.2f}%\n"
                                f"درصد تابلو: {sign}{day_change:.2f}%\n"
                                f"قیمت: {current_price} usdt\n"
                                f"حجم ۴ ساعت فعلی {format_volume(curr_4h_vol)} usdt\n"
                                f"حجم ۴ ساعت گذشته {format_volume(prev_4h_vol)} usdt\n"
                                f"تحلیل {vol_status}\n"
                                f"کمترین قیمت: {low_price} usdt\n"
                                f"بیشترین قیمت: {high_price} usdt"
                            )
                            send_telegram_message(msg)
                            
                            if "alerted" not in data:
                                data["alerted"] = {}
                            data["alerted"][name] = today_str
                            
        except Exception as e:
            continue

    save_data(data)

if __name__ == "__main__":
    main()
