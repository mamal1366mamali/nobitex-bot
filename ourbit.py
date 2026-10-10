import json
import os
import requests
import jdatetime
from datetime import datetime, timedelta

BOT_TOKEN = "2097163505:AAHR9MPkRd8uxOeYf35qsV1ZNRFmkz8kUCo"
CHANNEL_ID = "-1003961062602"
DATA_FILE = "ourbit_data.json"

API_URL = "https://api.ourbit.com/api/v3/ticker/24hr"
KLINES_URL = "https://api.ourbit.com/api/v3/klines"

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
        tickers = response.json()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return

    # Process all tickers
    for ticker in tickers:
        try:
            symbol_raw = ticker.get("symbol", "")
            symbol = symbol_raw.upper()
            if not symbol.endswith("USDT"):
                continue
            
            import re
            name = symbol.replace("USDT", "").lower()
            
            # Skip prediction tokens like 10964yes or 10964no
            if re.match(r'^\d+(yes|no)$', name):
                continue
                
            current_price = float(ticker.get("lastPrice", 0))
            low_price = float(ticker.get("lowPrice", 0))
            high_price = float(ticker.get("highPrice", 0))
            day_change = float(ticker.get("priceChangePercent", 0)) * 100
            
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
                                k_resp = requests.get(f"{KLINES_URL}?symbol={symbol_raw}&interval=15m&limit=32", timeout=10)
                                k_data = k_resp.json()
                                if len(k_data) > 0:
                                    # the last 16 are current rolling 4h
                                    curr_list = k_data[-16:]
                                    # the up to 16 before that are previous rolling 4h
                                    prev_list = k_data[:-16] if len(k_data) > 16 else []
                                    
                                    curr_4h_vol = sum([float(k[7]) for k in curr_list])
                                    prev_4h_vol = sum([float(k[7]) for k in prev_list])
                            except:
                                pass
                            
                            # Fake vs Real logic
                            if prev_4h_vol == 0:
                                vol_status = "⚠️ پامپ فیک (حجم قبلی نامشخص است)"
                            elif day_change > 15.0:
                                vol_status = "⚠️ روند کلی به شدت صعودی است. کاهش حجم به معنی اصلاح موقت است، به هیچ وجه شورت نگیرید!"
                            elif curr_4h_vol > prev_4h_vol * 2.5:
                                vol_status = "✅ پامپ واقعی (ورود پول هوشمند - مناسب برای لانگ / خطرناک برای شورت)"
                            elif curr_4h_vol <= prev_4h_vol * 1.5:
                                if day_change < 10.0:
                                    vol_status = "⚠️ پامپ فیک قطعی (بدون ورود پول در روند خنثی/نزولی - عالی برای شورت)"
                                else:
                                    vol_status = "⚠️ پامپ ضعیف (حجم پایین است اما روند تابلو صعودی است - احتیاط برای شورت)"
                            else:
                                vol_status = "⚠️ پامپ مشکوک (رشد حجم متوسط - نیازمند احتیاط)"

                            data["daily_count"] += 1
                            sign = "+" if day_change > 0 else ""
                            
                            msg = (
                                f"{data['daily_count']}\n"
                                f"نام: {name}\n"
                                f"درصد رشد (۴ ساعته): +{growth:.2f}%\n"
                                f"درصد تابلو: {sign}{day_change:.2f}%\n"
                                f"حجم ۴ ساعت اخیر: {format_volume(curr_4h_vol)} usdt\n"
                                f"حجم ۴ ساعت قبل: {format_volume(prev_4h_vol)} usdt\n"
                                f"تحلیل حجم: {vol_status}\n"
                                f"قیمت: {current_price} usdt\n"
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
