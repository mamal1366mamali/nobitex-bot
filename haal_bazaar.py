import os
import json
import requests
import re
from datetime import datetime, timedelta
import jdatetime
import warnings

warnings.filterwarnings('ignore')

# Config
BOT_TOKEN = os.environ.get("HAAL_BOT_TOKEN", "")
ALERT_CHANNEL = "-1004462898426"
CHANNEL_REPORT_MAIN = "-1004304608564"
DATA_FILE = "haal_data.json"

# Ourbit API (Futures)
OURBIT_TICKER_URL = "https://futures.ourbit.com/api/v1/contract/ticker"

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
    prices = {}
    stats_data = {}
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(OURBIT_TICKER_URL, headers=headers, timeout=15)
        if r.status_code == 200:
            res_json = r.json()
            tickers = res_json.get("data", []) if isinstance(res_json, dict) else res_json
            if isinstance(tickers, list):
                for item in tickers:
                    symbol_raw = item.get("symbol", "")
                    symbol = symbol_raw.upper()
                    if not symbol.endswith("_USDT") and not symbol.endswith("USDT"):
                        continue
                    if symbol_raw.startswith("~~"):
                        continue
                    sym = symbol.replace("_USDT", "").replace("USDT", "").lower()
                    if re.match(r'^\d+(yes|no)$', sym):
                        continue
                    
                    try:
                        last_price = float(item.get("lastPrice", 0))
                        day_change = float(item.get("riseFallRate", 0)) * 100
                        high_price = float(item.get("high24Price", 0))
                        low_price = float(item.get("lower24Price", 0))
                        
                        growth = 0
                        if low_price > 0:
                            growth = ((high_price - low_price) / low_price) * 100
                        
                        prices[sym] = last_price
                        stats_data[sym] = {
                            "dayChange": day_change,
                            "growth": growth,
                            "dayHigh": high_price,
                            "dayLow": low_price,
                            "lastPrice": last_price
                        }
                    except:
                        pass
    except Exception as e:
        print(f"Error fetching market data from Ourbit Futures: {e}")
    return prices, stats_data

def main():
    # Load data
    data = {"last_update_id": 0, "alerts": []}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data.update(loaded)
        except Exception:
            pass
    
    prices, stats_data = get_market_data()

    # Process new messages
    last_id = data.get("last_update_id", 0)
    updates = get_updates(offset=last_id + 1)
    
    max_id = last_id
    for update in updates:
        update_id = update.get("update_id", 0)
        if update_id > max_id:
            max_id = update_id
        
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "").strip().lower()
        
        if not text or not chat_id:
            continue

        keyboard = {
            "keyboard": [
                [{"text": "قیمت لحظه ای 💰"}],
                [{"text": "حال بازار 📊"}],
                [{"text": "بیشترین رشد و افت 📈📉"}],
                [{"text": "هشدار قیمتی 🔔"}],
                [{"text": "لیست هشدارهای قیمتی 📝"}]
            ],
            "resize_keyboard": True
        }

        if text == "/start":
            msg = "سلام! به دستیار حال بازار و هشدار قیمت خوش آمدید.\nبرای دریافت قیمت لحظه‌ای، فقط نام ارز را به تنهایی بفرستید (مثلا xrp یا btc)."
            send_message(chat_id, msg, keyboard)
            
        elif text in ["قیمت لحظه ای 💰", "قیمت لحظه ای"]:
            msg = "لطفا نام ارز مورد نظر را بنویسید (مثلاً xrp):"
            force_reply_markup = {"force_reply": True, "input_field_placeholder": "xrp"}
            send_message(chat_id, msg, force_reply_markup)
            
        elif text in ["حال بازار 📊", "حال بازار"]:
            if not stats_data:
                send_message(chat_id, "متاسفانه دریافت اطلاعات بازار با مشکل مواجه شد.", keyboard)
                continue
            
            up_count = 0
            down_count = 0
            for item in stats_data.values():
                chg = item.get("dayChange", 0)
                if chg > 0:
                    up_count += 1
                elif chg < 0:
                    down_count += 1
                    
            total = up_count + down_count
            if total > 0:
                up_pct = int(round((up_count / total) * 100))
                down_pct = int(round((down_count / total) * 100))
                
                if up_pct >= 60:
                    msg = f"روند بازار صعودی +{up_pct} %\nتعداد ارزهای مثبت {up_count}\nتعداد ارزهای منفی {down_count}"
                elif down_pct >= 60:
                    msg = f"روند بازار نزولی -{down_pct} %\nتعداد ارزهای مثبت {up_count}\nتعداد ارزهای منفی {down_count}"
                else:
                    msg = f"روند بازار رنج\nتعداد ارزهای مثبت {up_count}\nتعداد ارزهای منفی {down_count}"
                    
                send_message(chat_id, msg, keyboard)
                
        elif text in ["بیشترین رشد و افت 📈📉", "بیشترین رشد و افت", "بیشترین رشد", "بیشترین افت"]:
            if not stats_data:
                send_message(chat_id, "متاسفانه دریافت اطلاعات بازار با مشکل مواجه شد.", keyboard)
                continue
            
            sorted_by_growth = sorted(stats_data.items(), key=lambda x: x[1].get("growth", 0), reverse=True)
            top_20 = sorted_by_growth[:20]
            
            top_lines = []
            for sym, item in top_20:
                g = int(round(item.get("growth", 0)))
                c = int(round(item.get("dayChange", 0)))
                c_sign = "+" if c > 0 else ""
                top_lines.append(f"{sym} +{g} % درصد تابلو {c_sign}{c} %")
            top_msg = "\n".join(top_lines)
            
            sorted_by_drop = sorted(stats_data.items(), key=lambda x: x[1].get("dayChange", 0))
            bottom_10 = sorted_by_drop[:10]
            
            bottom_lines = []
            for sym, item in bottom_10:
                g = int(round(item.get("growth", 0)))
                c = int(round(item.get("dayChange", 0)))
                c_sign = "+" if c > 0 else ""
                bottom_lines.append(f"{sym} +{g} % درصد تابلو {c_sign}{c} %")
            bottom_msg = "\n".join(bottom_lines)

            msg = f"بیشترین رشد:\n{top_msg}\n\nبیشترین افت:\n{bottom_msg}"
            send_message(chat_id, msg, keyboard)
            
        elif text in ["هشدار قیمتی 🔔", "هشدار قیمتی", "هشدار قیمت 🔔"]:
            msg = "لطفا اول نام ارز، سپس نشانه (مثلا لانگ یا شرت یا رشد ناگهانی)، بعد قیمت tp و بعد قیمت stop را وارد نمایید"
            force_reply_markup = {"force_reply": True, "input_field_placeholder": "xrp لانگ 1.5 0.4"}
            send_message(chat_id, msg, force_reply_markup)
            
        elif text in ["لیست هشدارهای قیمتی 📝", "لیست هشدارها 📝", "لیست"]:
            my_alerts = [a for a in data.get("alerts", []) if a.get("chat_id") == chat_id]
            if not my_alerts:
                send_message(chat_id, "شما هیچ هشدار فعالی ندارید.", keyboard)
            else:
                msg = "لیست هشدارهای فعال شما:\n\n"
                for i, a in enumerate(my_alerts, 1):
                    tag_str = f" ({a['tag']})" if a.get('tag') else ""
                    msg += f"هشدار {i}:\nنام ارز {a['symbol'].upper()}{tag_str}\nقیمت tp {a['tp']}\nقیمت stop {a['stop']}\n\n"
                send_message(chat_id, msg, keyboard)

        elif text.startswith("هشدار") or "قیمت tp" in message.get("reply_to_message", {}).get("text", "") or (len(text.replace("هشدار", "").replace(",", " ").strip().split()) in [3, 4] and any(char.isdigit() for char in text)):
            parts = text.replace("هشدار", "").replace(",", " ").strip().split()
            if len(parts) == 4:
                try:
                    sym = parts[0].lower().replace("_usdt", "").replace("usdt", "")
                    tag = parts[1]
                    tp = float(parts[2])
                    stop = float(parts[3])
                    
                    if sym in prices:
                        if "alerts" not in data:
                            data["alerts"] = []
                        data["alerts"].append({"symbol": sym, "tag": tag, "tp": tp, "stop": stop, "chat_id": chat_id})
                        send_message(chat_id, f"✅ هشدار با موفقیت ثبت شد!\nارز: {sym.upper()}\nنشانه: {tag}\nقیمت فعلی: {prices[sym]}\nتارگت‌های شما: {tp} و {stop}\n\n(هر زمان قیمت به یکی از این دو برسد، در کانال آلارم می‌فرستم)", keyboard)
                    else:
                        send_message(chat_id, f"ارز {sym.upper()} در بازار تتری اوربیت پیدا نشد! لطفا نام ارز را صحیح بنویسید.", keyboard)
                except:
                    send_message(chat_id, "فرمت قیمت‌ها اشتباه است! لطفا قیمت‌ها را به عدد وارد کنید. مثال:\nxrp لانگ 1.5 0.4", keyboard)
            elif len(parts) == 3:
                try:
                    sym = parts[0].lower().replace("_usdt", "").replace("usdt", "")
                    tp = float(parts[1])
                    stop = float(parts[2])
                    tag = ""
                    
                    if sym in prices:
                        if "alerts" not in data:
                            data["alerts"] = []
                        data["alerts"].append({"symbol": sym, "tag": tag, "tp": tp, "stop": stop, "chat_id": chat_id})
                        send_message(chat_id, f"✅ هشدار با موفقیت ثبت شد!\nارز: {sym.upper()}\nقیمت فعلی: {prices[sym]}\nتارگت‌های شما: {tp} و {stop}\n\n(هر زمان قیمت به یکی از این دو برسد، در کانال آلارم می‌فرستم)", keyboard)
                    else:
                        send_message(chat_id, f"ارز {sym.upper()} در بازار تتری اوربیت پیدا نشد! لطفا نام ارز را صحیح بنویسید.", keyboard)
                except:
                    send_message(chat_id, "فرمت قیمت‌ها اشتباه است! لطفا فقط عدد وارد کنید. مثال:\nxrp لانگ 1.5 0.4", keyboard)
            else:
                send_message(chat_id, "دستور نامعتبر است! لطفاً به این شکل بفرستید:\nxrp لانگ 1.5 0.4", keyboard)
                
        else:
            sym = text.replace('usdt', '').strip()
            if sym in stats_data:
                info = stats_data[sym]
                day_change = round(info["dayChange"], 2)
                growth = round(info.get("growth", 0), 2)
                day_low = info["dayLow"]
                day_high = info["dayHigh"]
                price_now = info["lastPrice"]
                
                sign = "+" if day_change > 0 else ""
                msg = (
                    f"نام {sym}\n"
                    f"میزان رشد +{growth} % درصد تابلو {sign}{day_change} %\n"
                    f"قیمت {price_now} usdt\n"
                    f"کمترین قیمت {day_low} usdt\n"
                    f"بیشترین قیمت {day_high} usdt"
                )
                send_message(chat_id, msg, keyboard)
            else:
                send_message(chat_id, "دستور یا نام ارز پیدا نشد.\nبرای دیدن لیست دکمه‌ها /start را بفرستید.", keyboard)

    # Acknowledge to Telegram that messages were processed
    if max_id > last_id:
        data["last_update_id"] = max_id
        try:
            requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates", params={"offset": max_id + 1, "limit": 1}, timeout=10)
        except Exception:
            pass

    # Check Active Alerts
    remaining_alerts = []
    for alert in data.get("alerts", []):
        sym = alert.get("symbol", "")
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
            tag_str = f" {alert.get('tag')}" if alert.get("tag") else ""
            msg_alert = f"نام {sym.upper()}{tag_str} {triggered_type} {trigger_price}"
            send_message(ALERT_CHANNEL, msg_alert)
            send_message(alert["chat_id"], f"هشدار فعال شد:\n{msg_alert}")
        else:
            remaining_alerts.append(alert)
            
    data["alerts"] = remaining_alerts

    # Daily Market Status Report to CHANNEL_REPORT_MAIN at 20:00 (8 PM Iran time)
    iran_time = datetime.utcnow() + timedelta(hours=3, minutes=30)
    shamsi_date = jdatetime.datetime.fromgregorian(datetime=iran_time).strftime('%Y %m %d')
    today_str = jdatetime.datetime.fromgregorian(datetime=iran_time).strftime('%Y/%m/%d')
    time_str = iran_time.strftime('%H : %M')
    current_date_str = f"{shamsi_date} ساعت {time_str} دقیقه"

    if iran_time.hour >= 20 and data.get("last_daily_report_date") != today_str:
        if stats_data:
            up_count = 0
            down_count = 0
            for item in stats_data.values():
                chg = item.get("dayChange", 0)
                if chg > 0:
                    up_count += 1
                elif chg < 0:
                    down_count += 1
                    
            total = up_count + down_count
            if total > 0:
                up_pct = int(round((up_count / total) * 100))
                down_pct = int(round((down_count / total) * 100))
                
                if up_pct >= 60:
                    status_line = f"حال بازار صعودی +{up_pct} %"
                elif down_pct >= 60:
                    status_line = f"حال بازار نزولی -{down_pct} %"
                else:
                    status_line = "حال بازار رنج"
                    
                daily_report_msg = f"{status_line}\nتعداد ارزهای مثبت {up_count}\nتعداد ارزهای منفی {down_count}\n\nتاریخ {current_date_str}"
                send_message(CHANNEL_REPORT_MAIN, daily_report_msg)
                data["last_daily_report_date"] = today_str
    
    # Save data locally
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving data: {e}")

if __name__ == "__main__":
    main()
