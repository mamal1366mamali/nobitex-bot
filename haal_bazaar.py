import os
import json
import requests
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')

# Config
BOT_TOKEN = "8619739965:AAHa3Y3LGY7evTYDgTsqWR8UxidsCbQLU6w"
ALERT_CHANNEL = "-1004462898426"
DATA_FILE = "haal_data.json"

# Nobitex API
STATS_URL = "https://apiv2.nobitex.ir/market/stats"
ORDERBOOK_URL = "https://apiv2.nobitex.ir/v3/orderbook/all"

def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception:
        pass

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"timeout": 10}
    if offset:
        params["offset"] = offset
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            return r.json().get("result", [])
    except Exception:
        pass
    return []

def get_market_data():
    ob = {}
    stats = {}
    try:
        r1 = requests.get(ORDERBOOK_URL, timeout=15)
        if r1.status_code == 200:
            ob = r1.json()
    except:
        pass
        
    try:
        r2 = requests.post(STATS_URL, json={"srcCurrency": "", "dstCurrency": "usdt"}, timeout=15)
        if r2.status_code == 200:
            stats = r2.json()
    except:
        pass
        
    return ob, stats

def main():
    # Load data
    data = {"last_update_id": 0, "alerts": []}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            pass
    
    ob, stats = get_market_data()
    prices = {}
    for k, v in ob.items():
        if k.endswith('USDT'):
            sym = k.replace('USDT', '').lower()
            prices[sym] = float(v.get('lastTradePrice', 0))

    # Process new messages
    updates = get_updates(offset=data["last_update_id"] + 1)
    for update in updates:
        update_id = update["update_id"]
        if update_id > data["last_update_id"]:
            data["last_update_id"] = update_id
        
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "").strip().lower()
        
        if not text or not chat_id:
            continue

        # Keyboard for easy access
        keyboard = {
            "keyboard": [
                [{"text": "حال بازار 📊"}],
                [{"text": "هشدار قیمت 🔔"}],
                [{"text": "لیست هشدارها 📝"}]
            ],
            "resize_keyboard": True
        }

        if text == "/start":
            msg = "سلام! به دستیار حال بازار و هشدار قیمت خوش آمدید.\nبرای دریافت قیمت لحظه‌ای، فقط نام ارز را به تنهایی بفرستید (مثلا xrp یا btc)."
            send_message(chat_id, msg, keyboard)
            
        elif text == "حال بازار 📊" or text == "حال بازار":
            if stats.get("status") != "ok":
                send_message(chat_id, "متاسفانه دریافت اطلاعات بازار با مشکل مواجه شد.", keyboard)
                continue
            
            pos_count = 0
            neg_count = 0
            for stat in stats.get("stats", {}).values():
                try:
                    change = float(stat.get("dayChange", 0))
                    if change > 0:
                        pos_count += 1
                    elif change < 0:
                        neg_count += 1
                except:
                    pass
                    
            total = pos_count + neg_count
            if total > 0:
                pos_pct = (pos_count / total) * 100
                if pos_pct >= 60:
                    mood = "صعودی 🚀"
                elif pos_pct <= 40:
                    mood = "نزولی 🔻"
                else:
                    mood = "رنج (Range) ⚖️"
                    
                msg = f"وضعیت حال بازار:\n\nروند کلی: {mood}\nدرصد ارزهای مثبت: {pos_pct:.1f}٪\n\nتعداد ارزهای مثبت: {pos_count}\nتعداد ارزهای منفی: {neg_count}"
                send_message(chat_id, msg, keyboard)
                
        elif text == "هشدار قیمت 🔔" or text == "هشدار قیمت":
            msg = "لطفاً نام ارز، تارگت اول و تارگت دوم را با فاصله بنویسید (مثلاً: xrp 1.5 0.4):"
            force_reply_markup = {"force_reply": True, "input_field_placeholder": "xrp 1.5 0.4"}
            send_message(chat_id, msg, force_reply_markup)
            
        elif text == "لیست هشدارها 📝" or text == "لیست":
            my_alerts = [a for a in data["alerts"] if a["chat_id"] == chat_id]
            if not my_alerts:
                send_message(chat_id, "شما هیچ هشدار فعالی ندارید.", keyboard)
            else:
                msg = "لیست هشدارهای فعال شما:\n\n"
                for i, a in enumerate(my_alerts, 1):
                    msg += f"{i}. ارز {a['symbol'].upper()} | حد ۱: {a['tp']} | حد ۲: {a['stop']}\n"
                send_message(chat_id, msg, keyboard)

        elif text.startswith("هشدار") or "تارگت اول و تارگت دوم" in message.get("reply_to_message", {}).get("text", ""):
            parts = text.replace("هشدار", "").strip().split()
            if len(parts) == 3:
                try:
                    sym = parts[0].lower()
                    tp = float(parts[1])
                    stop = float(parts[2])
                    
                    if sym in prices:
                        data["alerts"].append({"symbol": sym, "tp": tp, "stop": stop, "chat_id": chat_id})
                        send_message(chat_id, f"✅ هشدار با موفقیت ثبت شد!\nارز: {sym.upper()}\nقیمت فعلی: {prices[sym]}\nتارگت‌های شما: {tp} و {stop}\n\n(هر زمان قیمت به یکی از این دو برسد، در کانال آلارم می‌فرستم)", keyboard)
                    else:
                        send_message(chat_id, f"ارز {sym} در بازار تتری پیدا نشد! لطفا نام ارز را صحیح بنویسید.", keyboard)
                except:
                    send_message(chat_id, "فرمت قیمت‌ها اشتباه است! لطفا فقط عدد وارد کنید. مثال:\nxrp 1.5 1.2", keyboard)
            else:
                send_message(chat_id, "دستور نامعتبر است! لطفاً به این شکل بفرستید:\nxrp 1.5 1.2", keyboard)
                
        else:
            # Assuming it's a single coin name request
            sym = text.replace('usdt', '').strip()
            if sym in prices:
                send_message(chat_id, f"قیمت لحظه‌ای {sym.upper()}:\n{prices[sym]} دلار", keyboard)
            else:
                send_message(chat_id, "دستور یا نام ارز پیدا نشد.\nبرای دیدن لیست دکمه‌ها /start را بفرستید.", keyboard)

    # Check Active Alerts
    remaining_alerts = []
    for alert in data["alerts"]:
        sym = alert["symbol"]
        current_price = prices.get(sym)
        
        if not current_price:
            remaining_alerts.append(alert)
            continue
            
        triggered = False
        triggered_type = ""
        trigger_price = 0
        
        upper_bound = max(alert["tp"], alert["stop"])
        lower_bound = min(alert["tp"], alert["stop"])
        
        if current_price >= upper_bound:
            triggered = True
            if alert["tp"] == upper_bound:
                triggered_type = "tp"
                trigger_price = alert["tp"]
            else:
                triggered_type = "stop"
                trigger_price = alert["stop"]
        elif current_price <= lower_bound:
            triggered = True
            if alert["tp"] == lower_bound:
                triggered_type = "tp"
                trigger_price = alert["tp"]
            else:
                triggered_type = "stop"
                trigger_price = alert["stop"]
            
        if triggered:
            msg_alert = f"نام {sym.lower()} {triggered_type} {trigger_price}"
            
            # Send to Alert Channel
            send_message(ALERT_CHANNEL, msg_alert)
            # Also notify the user in their PV
            send_message(alert["chat_id"], f"هشدار فعال شد:\n{msg_alert}")
        else:
            remaining_alerts.append(alert)
            
    data["alerts"] = remaining_alerts
    
    # Save data
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()
