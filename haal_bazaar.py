import os
import json
import requests
import re
from datetime import datetime, timedelta
import jdatetime
import pandas as pd
import warnings

warnings.filterwarnings('ignore')

# Config
BOT_TOKEN = os.environ.get("HAAL_BOT_TOKEN", "")
ALERT_CHANNEL = "-1004462898426"
CHANNEL_REPORT_MAIN = "-1004304608564"
DATA_FILE = "haal_data.json"

# Ourbit API (Futures)
OURBIT_TICKER_URL = "https://futures.ourbit.com/api/v1/contract/ticker"
OURBIT_KLINE_URL = "https://futures.ourbit.com/api/v1/contract/kline"

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
                        amount_24 = float(item.get("amount24", 0) or 0)
                        if amount_24 == 0 and "volume24" in item:
                            vol24 = float(item.get("volume24", 0) or 0)
                            if vol24 > 0 and last_price > 0:
                                amount_24 = vol24 * last_price
                        
                        growth = 0
                        if low_price > 0:
                            growth = ((high_price - low_price) / low_price) * 100
                        
                        prices[sym] = last_price
                        stats_data[sym] = {
                            "dayChange": day_change,
                            "growth": growth,
                            "dayHigh": high_price,
                            "dayLow": low_price,
                            "lastPrice": last_price,
                            "amount24": amount_24
                        }
                    except:
                        pass
    except Exception as e:
        print(f"Error fetching market data from Ourbit Futures: {e}")
    return prices, stats_data

def format_volume(val):
    if not val:
        return "0 usdt"
    try:
        val = float(val)
        if val >= 1_000_000_000:
            return f"{val / 1_000_000_000:.2f}b usdt"
        elif val >= 1_000_000:
            return f"{val / 1_000_000:.2f}m usdt"
        elif val >= 1_000:
            return f"{val / 1_000:.0f}k usdt"
        else:
            return f"{int(val)} usdt"
    except Exception:
        return f"{val} usdt"

def fmt_price(val):
    try:
        val = float(val)
        if val == int(val):
            return str(int(val))
        return f"{val:.8f}".rstrip('0').rstrip('.')
    except Exception:
        return str(val)

def process_chart_request(symbol, timeframe, candle_count_str, target_price_str, code_str):
    sym = symbol.lower().replace("_usdt", "").replace("usdt", "").strip()
    
    tf_map = {
        '15': ('Min15', '15 دقیقه', 1),
        '15m': ('Min15', '15 دقیقه', 1),
        '30': ('Min30', '30 دقیقه', 1),
        '30m': ('Min30', '30 دقیقه', 1),
        '1': ('Min60', '1 ساعته', 1),
        '1h': ('Min60', '1 ساعته', 1),
        '2': ('Min60', '2 ساعته', 2),
        '2h': ('Min60', '2 ساعته', 2),
        '4': ('Hour4', '4 ساعته', 1),
        '4h': ('Hour4', '4 ساعته', 1),
    }
    
    tf_clean = str(timeframe).lower().strip()
    if tf_clean not in tf_map:
        return "تایم فریم نامعتبر است"
        
    api_interval, tf_name, mult = tf_map[tf_clean]
    
    try:
        count = int(candle_count_str)
        if count <= 0 or count > 50:
            count = 50
    except ValueError:
        count = 50
        
    code_clean = str(code_str).strip()
    is_min = (code_clean == '0')
    
    pair = f"{sym.upper()}_USDT"
    url = f"{OURBIT_KLINE_URL}/{pair}?interval={api_interval}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=12)
        res = r.json()
    except Exception:
        return "خطا در اتصال به سرور"
        
    if not res.get("success") or not res.get("data"):
        return f"ارز {sym} یافت نشد"
        
    raw_data = res["data"]
    try:
        df = pd.DataFrame(raw_data)
        if len(df) == 0:
            return f"داده‌ای برای {sym} یافت نشد"
    except Exception:
        return f"خطا در پردازش داده‌ها"
        
    df = df.tail(count * mult).reset_index(drop=True)
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    
    # تجمیع کندل‌ها برای تایم‌فریم ۲ ساعته
    if mult == 2:
        agg_rows = []
        for i in range(0, len(df), 2):
            chunk = df.iloc[i:i+2]
            agg_rows.append({
                'time': chunk['time'].iloc[0],
                'open': chunk['open'].iloc[0],
                'high': chunk['high'].max(),
                'low': chunk['low'].min(),
                'close': chunk['close'].iloc[-1]
            })
        df = pd.DataFrame(agg_rows)
        
    def format_candle_price(p, target_str):
        if '.' in target_str:
            dec = len(target_str.split('.')[1])
            dec = max(2, dec)
            return f"{p:.{dec}f}"
        elif p >= 100:
            return f"{p:.2f}"
        elif p >= 1:
            return f"{p:.4f}".rstrip('0').rstrip('.')
        else:
            return f"{p:.6f}".rstrip('0').rstrip('.')

    target_str_clean = str(target_price_str).strip()
    lines = [f"{sym} {target_str_clean}"]
    
    price_col = 'low' if is_min else 'high'
    for _, row in df.iterrows():
        p = row[price_col]
        lines.append(format_candle_price(p, target_str_clean))
        
    return "\n".join(lines)

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
                [{"text": "چارت 📊"}],
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
            msg = "لطفا نام ارز، قیمت ورود (entri)، قیمت tp و stop را وارد نمایید.\nمی‌توانید هر نوشته‌ای (فروش، لانگ، اهرم ۷، منفی ۷ درصد و...) بین نام ارز و قیمت‌ها بنویسید.\n\nمثال‌ها:\nxrp 1.58 2.51 0.4\nxrp لانگ 1.58 2.51 0.4\nxrp فروش منفی 7 درصد اهرم 7 1.58 2.51 0.4\nbtc معامله شورت اهرم 10 98000 105000 91000"
            force_reply_markup = {"force_reply": True, "input_field_placeholder": "xrp 1.58 2.51 0.4"}
            send_message(chat_id, msg, force_reply_markup)
            
        elif text in ["لیست هشدارهای قیمتی 📝", "لیست هشدارها 📝", "لیست"]:
            my_alerts = [a for a in data.get("alerts", []) if str(a.get("chat_id")) == str(chat_id)]
            if not my_alerts:
                send_message(chat_id, "شما هیچ هشدار فعالی ندارید.", keyboard)
            else:
                # مرتب‌سازی بر اساس زمان ثبت (جدیدترین در ابتدا)
                my_alerts = my_alerts[::-1]
                msg = f"تعداد هشدارهای فعال: {len(my_alerts)}\n\n"
                for i, a in enumerate(my_alerts, 1):
                    sym = a['symbol'].lower()
                    tag = a.get('tag', '')
                    tag_str = f" ({tag})" if tag and not str(tag).replace('.', '').isdigit() else ""
                    
                    close_price = prices.get(sym) or stats_data.get(sym, {}).get("lastPrice", 0)
                    
                    # Resolve entry price - اول از فیلد entry هشدار بخون
                    entry = 0.0
                    try:
                        entry = float(a.get("entry", 0) or 0)
                    except:
                        pass
                    # اگه entry هنوز صفره از tag امتحان کن
                    if entry == 0 and tag and str(tag).replace('.', '').isdigit():
                        try:
                            entry = float(tag)
                        except:
                            pass
                        
                    if close_price == 0:
                        close_price = entry if entry > 0 else 0

                        
                    diff_pct = 0.0
                    if entry > 0 and close_price > 0:
                        diff_pct = round(((close_price - entry) / entry) * 100, 2)
                    diff_sign = "+" if diff_pct > 0 else ""
                    if diff_pct == int(diff_pct):
                        diff_val_str = str(int(diff_pct))
                    else:
                        diff_val_str = f"{diff_pct:.2f}".rstrip('0').rstrip('.')
                    diff_str = f"{diff_sign}{diff_val_str}%"
                    
                    msg += f"{i}- {sym}{tag_str} قیمت {fmt_price(close_price)}usd entri {fmt_price(entry)} tp {fmt_price(a['tp'])} stop {fmt_price(a['stop'])} میزان اختلاف قیمت به entri {diff_str}\n\n"
                
                msg += "راهنمای حذف:\n"
                msg += "برای حذف کامل عدد 11 و برای حذف یک ارز عدد 1 به همراه نام ارز را وارد نمایید.\n"
                msg += "مثال:\n"
                msg += "11 (حذف کل لیست)\n"
                msg += "1 btc (حذف فقط ارز btc)"
                send_message(chat_id, msg, keyboard)

        elif text == "11" or (text.startswith("حذف") and "11" in text):
            count_deleted = len([a for a in data.get("alerts", []) if str(a.get("chat_id")) == str(chat_id)])
            if count_deleted > 0:
                data["alerts"] = [a for a in data.get("alerts", []) if str(a.get("chat_id")) != str(chat_id)]
                send_message(chat_id, "کل لیست هشدارهای شما با موفقیت حذف شد.", keyboard)
            else:
                send_message(chat_id, "شما هیچ هشدار فعالی در لیست ندارید.", keyboard)

        elif (text.startswith("1 ") or text.startswith("1-") or (len(text.split()) == 2 and text.split()[0] == "1") or (text.startswith("1") and len(text) > 2 and text[1:].isalpha())):
            parts = text.replace("-", " ").strip().split()
            if len(parts) >= 2 and parts[0] == "1":
                target_sym = parts[1].lower().replace("_usdt", "").replace("usdt", "")
            elif text.startswith("1") and len(text) > 1:
                target_sym = text[1:].strip().lower().replace("_usdt", "").replace("usdt", "")
            else:
                target_sym = ""
                
            if target_sym:
                count_deleted = len([a for a in data.get("alerts", []) if str(a.get("chat_id")) == str(chat_id) and a.get("symbol", "").lower() == target_sym])
                if count_deleted > 0:
                    data["alerts"] = [a for a in data.get("alerts", []) if not (str(a.get("chat_id")) == str(chat_id) and a.get("symbol", "").lower() == target_sym)]
                    send_message(chat_id, f"هشدار ارز {target_sym.upper()} با موفقیت حذف شد.", keyboard)
                else:
                    send_message(chat_id, f"هشداری برای ارز {target_sym.upper()} در لیست شما پیدا نشد.", keyboard)

        elif text.startswith("هشدار") or "قیمت tp" in message.get("reply_to_message", {}).get("text", "") or "قیمت ورود" in message.get("reply_to_message", {}).get("text", "") or (len(text.replace("هشدار", "").replace(",", " ").strip().split()) >= 3 and any(char.isdigit() for char in text) and not (len(text.replace(",", " ").strip().split()) == 5 and text.replace(",", " ").strip().split()[-1] in ["0", "9"])):

            raw = text.replace("هشدار", "").replace(",", " ").strip()
            parts = raw.split()
            sym = parts[0].lower().replace("_usdt", "").replace("usdt", "")
            tag = ""
            entry = 0.0
            tp = 0.0
            stop = 0.0
            valid = False

            # پیدا کردن سه عدد آخر به عنوان entry، tp، stop
            # همه قطعه‌های بینابینی به عنوان tag ذخیره می‌شوند (بدون محدودیت)
            numeric_indices = []
            for i, p in enumerate(parts[1:], start=1):
                try:
                    float(p)
                    numeric_indices.append(i)
                except ValueError:
                    pass

            if len(numeric_indices) >= 3:
                # سه عدد آخر = entry، tp، stop
                entry_idx, tp_idx, stop_idx = numeric_indices[-3], numeric_indices[-2], numeric_indices[-1]
                try:
                    entry = float(parts[entry_idx])
                    tp = float(parts[tp_idx])
                    stop = float(parts[stop_idx])
                    # همه بخش‌های بینابینی (غیر از sym و سه عدد آخر) به عنوان tag
                    tag_parts = [p for i, p in enumerate(parts[1:], start=1) if i not in (entry_idx, tp_idx, stop_idx)]
                    tag = " ".join(tag_parts).strip()
                    valid = True
                except:
                    valid = False
            elif len(numeric_indices) == 2:
                # بدون entry: entry = قیمت لحظه‌ای
                tp_idx, stop_idx = numeric_indices[0], numeric_indices[1]
                try:
                    entry = float(prices.get(sym, 0))
                    tp = float(parts[tp_idx])
                    stop = float(parts[stop_idx])
                    tag_parts = [p for i, p in enumerate(parts[1:], start=1) if i not in (tp_idx, stop_idx)]
                    tag = " ".join(tag_parts).strip()
                    valid = True
                except:
                    valid = False

            if valid:
                if sym in prices:
                    if "alerts" not in data:
                        data["alerts"] = []
                    if entry == 0:
                        entry = float(prices.get(sym, 0))
                    data["alerts"].append({
                        "symbol": sym,
                        "tag": tag,
                        "entry": entry,
                        "tp": tp,
                        "stop": stop,
                        "chat_id": chat_id,
                        "created_at": int(datetime.utcnow().timestamp())
                    })
                    tag_line = f"نشانه: {tag}\n" if tag else ""
                    send_message(chat_id, f"✅ هشدار با موفقیت ثبت شد!\nارز: {sym.upper()}\n{tag_line}قیمت فعلی: {prices[sym]}\nورود (entri): {fmt_price(entry)}\nتارگت‌های شما: tp {fmt_price(tp)} و stop {fmt_price(stop)}\n\n(هر زمان قیمت به یکی از این دو برسد، در کانال آلارم می‌فرستم)", keyboard)
                else:
                    send_message(chat_id, f"ارز {sym.upper()} در بازار تتری اوربیت پیدا نشد! لطفا نام ارز را صحیح بنویسید.", keyboard)
            else:
                send_message(chat_id, "فرمت اشتباه است! حداقل باید نام ارز و دو قیمت (tp و stop) وارد شود.\nمثال:\nxrp 2.51 0.4\nxrp 1.58 2.51 0.4\nxrp فروش منفی 7 درصد اهرم 7 1.58 2.51 0.4", keyboard)
                
        elif text in ["چارت 📊", "چارت", "chart"]:
            guide_msg = (
                "برای دریافت ابتدا نام عرض سپس تایم فریم که گزینه های 15 و 30 دقیقه و 1 2 4 ساعتی میباشد سپس تایم فریم حد اکثر 50 کندل میباشد و سپس قیمت مورد نظر و سپس برای کمترین قیمت عدد 0 و بیشترین قیمت عدد 9 را وارد نمایید\n\n"
                "1 نام   : که اول باید نام عرض نوشته شود\n"
                "2 تایم  فریم : که دقیقه دو گزینه 15 و 30 دقیقه باشد و ساعتی نیز 1 2 4 ساعته باشد\n"
                "3 تعداد کندل : که حد اکثر 50 تا کندل باشد\n"
                "4 قیمت مد نظر  : که اینجا از قیمت مورد نظر شروع به خروجی داده که کمترین یا بیشترین قیمت میباشد\n"
                "5 رمز بیشترین یا کمترین  : که اگر کمترین قیمت باشد عدد 0 و اگر بیشترین قیمت را بخواهیم عدد 9 را وارد کنیم\n\n"
                "مثال : btc  4 30 1.58 0"
            )
            force_reply_markup = {"force_reply": True, "input_field_placeholder": "btc 4 30 1.58 0"}
            send_message(chat_id, guide_msg, force_reply_markup)
            
        elif text.startswith("چارت") or "برای دریافت ابتدا نام" in message.get("reply_to_message", {}).get("text", "") or (len(text.replace("چارت", "").replace(",", " ").strip().split()) == 5 and text.replace("چارت", "").replace(",", " ").strip().split()[-1] in ["0", "9"]):
            parts = text.replace("چارت", "").replace(",", " ").strip().split()
            if len(parts) == 5:
                chart_res = process_chart_request(parts[0], parts[1], parts[2], parts[3], parts[4])
                send_message(chat_id, chart_res, keyboard)
            else:
                send_message(chat_id, "فرمت دستور چارت اشتباه است! لطفاً به این شکل بفرستید:\nbtc 4 30 1.58 0", keyboard)
                
        else:
            sym = text.replace('usdt', '').strip()
            if sym in stats_data:
                info = stats_data[sym]
                day_change = round(info["dayChange"], 2)
                growth = round(info.get("growth", 0), 2)
                day_low = info["dayLow"]
                day_high = info["dayHigh"]
                price_now = info["lastPrice"]
                vol_str = format_volume(info.get("amount24", 0))
                
                sign = "+" if day_change > 0 else ""
                msg = (
                    f"نام {sym}\n"
                    f"قیمت {price_now} usdt\n"
                    f"میزان رشد +{growth} % درصد تابلو {sign}{day_change} %\n"
                    f"کمترین قیمت {day_low} usdt\n"
                    f"بیشترین قیمت {day_high} usdt\n"
                    f"حجم {vol_str}"
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
            tag_str = f"\n{alert.get('tag')}" if alert.get("tag") else ""
            msg_alert = f"نام {sym.upper()}{tag_str}\n{triggered_type} {fmt_price(trigger_price)}"
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
