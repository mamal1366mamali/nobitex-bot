import os
import json
import math
import time
import requests
import re
import concurrent.futures
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

def _kline_ref_24h(pair, tries=2, sleep_base=0.3):
    """کلوز ۲۴ ساعت قبل از کندل ساعتی"""
    for i in range(tries):
        try:
            r = requests.get(
                f"{OURBIT_KLINE_URL}/{pair}?interval=Min60&limit=25",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=20
            )
            res = r.json()
            d = res.get("data") or {}
            closes = d.get("close") if isinstance(d, dict) else None
            if closes and len(closes) >= 25:
                return float(closes[-25])
        except Exception:
            pass
        if i < tries - 1:
            time.sleep(sleep_base * (i + 1))
    return None

def _fetch_refs(syms, workers, tries, sleep_base):
    """گرفتن مرجع ۲۴ ساعته برای لیستی از ارزها"""
    if not syms:
        return {}
    pairs = [f"{s.upper()}_USDT" for s in syms]
    out = {}
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(lambda p: _kline_ref_24h(p, tries, sleep_base), pairs))
        for s, ref in zip(syms, results):
            if ref and ref > 0:
                out[s] = ref
    except Exception:
        pass
    return out

def get_true_24h_counts(stats_data, data, force=False):
    """شمارش مثبت/منفی بر اساس ۲۴ ساعت واقعی: کلوز الان نسبت به کلوز ۲۴ ساعت قبل.
    مرجع هر ساعت یک‌بار محاسبه و در haal_data.json کش می‌شود تا دکمهٔ دستی سریع باشد."""
    hour_key = int(time.time() // 3600)
    cache = data.get("ref_cache") or {}
    if force or cache.get("hour") != hour_key:
        refs = {}
    else:
        refs = dict(cache.get("prices") or {})

    syms = list(stats_data.keys())
    missing = [s for s in syms if not refs.get(s)]

    # چند مرحله تلاش: اول پرسرعت، بعد آهسته‌تر برای ارزهایی که جواب ندادند
    # (صرافی درخواست‌های هم‌زمان زیاد را محدود می‌کند؛ با تلاش دوباره تقریباً همه شمرده می‌شوند)
    for workers, tries, pause in ((12, 2, 0.3), (6, 3, 0.8), (3, 4, 1.5)):
        if not missing:
            break
        got = _fetch_refs(missing, workers, tries, pause)
        if got:
            refs.update(got)
        missing = [s for s in missing if not refs.get(s)]

    if refs:
        data["ref_cache"] = {"hour": hour_key, "prices": refs}

    up = 0
    down = 0
    for sym, item in stats_data.items():
        ref = refs.get(sym)
        last = item.get("lastPrice", 0) or 0
        if not ref or last <= 0:
            continue
        if last > ref:
            up += 1
        elif last < ref:
            down += 1

    return up, down, len(refs)

def build_market_status_line(up_count, down_count):
    total = up_count + down_count
    if total <= 0:
        return None
    # عدد = درصد ارزهای صعودی (مثبت)
    up_pct = int(round((up_count / total) * 100))
    # مرزها: زیر ۳۳ نزولی، ۳۳ تا ۶۶ رنج، ۶۶ به بالا صعودی
    if up_count * 3 <= total:
        return f"نزولی {up_pct} %"
    elif up_count * 3 >= total * 2:
        return f"صعودی {up_pct} %"
    return f"رنج {up_pct} %"

def format_volume(val):
    if not val:
        return "0"
    try:
        val = float(val)
        if val >= 1_000_000_000:
            return f"{val / 1_000_000_000:.2f}b"
        elif val >= 1_000_000:
            return f"{val / 1_000_000:.2f}m"
        elif val >= 1_000:
            return f"{val / 1_000:.0f}k"
        else:
            return f"{int(val)}"
    except Exception:
        return f"{val}"

def fmt_price(val):
    if val is None or val == 0:
        return '0'
    try:
        val_float = float(val)
        if abs(val_float) >= 1:
            decimals = 4
        else:
            exponent = math.floor(math.log10(abs(val_float)))
            leading_zeros = -exponent - 1
            decimals = leading_zeros + 4
        return f"{val_float:.{decimals}f}".rstrip('0').rstrip('.')
    except Exception:
        return str(val)

def process_chart_request(symbol, timeframe, target_price_str, code_str):
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
        return "تایم فریم نامعتبر است. گزینه‌ها: 15 ، 30 ، 1 ، 2 ، 4"
        
    api_interval, tf_name, mult = tf_map[tf_clean]
        
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
        
    df = df.tail(500).reset_index(drop=True)
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['time'] = df['time'].astype(int)
    
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
    try:
        target_val = float(target_str_clean)
    except ValueError:
        target_val = 0.0

    price_col = 'low' if is_min else 'high'
    prefix = 'low' if is_min else 'high'

    # پیدا کردن نزدیک‌ترین کندل به قیمت ورودی مبدأ
    if len(df) > 0 and target_val > 0:
        diff = (df[price_col] - target_val).abs()
        match_idx = int(diff.idxmin())
    else:
        match_idx = len(df) - 1

    def get_candle_time_range(ts, tf):
        iran_dt = datetime.utcfromtimestamp(ts) + timedelta(hours=3, minutes=30)
        h = iran_dt.hour
        m = iran_dt.minute
        
        if tf in ['1', '1h']:
            start_dt = iran_dt.replace(minute=0, second=0)
            end_dt = start_dt + timedelta(hours=1)
        elif tf in ['2', '2h']:
            start_dt = iran_dt.replace(hour=(h // 2) * 2, minute=0, second=0)
            end_dt = start_dt + timedelta(hours=2)
        elif tf in ['4', '4h']:
            start_dt = iran_dt.replace(hour=(h // 4) * 4, minute=0, second=0)
            end_dt = start_dt + timedelta(hours=4)
        elif tf in ['30', '30m']:
            start_m = 0 if m < 30 else 30
            start_dt = iran_dt.replace(minute=start_m, second=0)
            end_dt = start_dt + timedelta(minutes=30)
        elif tf in ['15', '15m']:
            start_m = (m // 15) * 15
            start_dt = iran_dt.replace(minute=start_m, second=0)
            end_dt = start_dt + timedelta(minutes=15)
        else:
            start_dt = iran_dt.replace(minute=0, second=0)
            end_dt = start_dt + timedelta(hours=1)
            
        return f"{start_dt.strftime('%H : %M')} تا {end_dt.strftime('%H : %M')}"

    # استخراج کندل‌ها از نقطه تطابق مبدأ تا زمان فعلی (آخرین کندل دیتافریم)
    lines = []
    for idx in range(match_idx, len(df)):
        row = df.loc[idx]
        p = float(row[price_col])
        ts = int(row['time'])
        time_range_str = get_candle_time_range(ts, tf_clean)
        p_str = format_candle_price(p, target_str_clean)
        lines.append(f"{p_str} {time_range_str}")
        
    return "\n".join(lines)

def check_is_chart(raw_text, msg_obj):
    if raw_text.startswith("چارت") or "برای دریافت چارت" in msg_obj.get("reply_to_message", {}).get("text", ""):
        return True
    tokens = raw_text.replace("چارت", "").replace(",", " ").strip().split()
    if len(tokens) == 4:
        valid_tfs = ['15', '15m', '30', '30m', '1', '1h', '2', '2h', '4', '4h']
        tf = tokens[1].lower().strip()
        last_tok = tokens[3].strip()
        # شرط قطعی چارت:
        # ۱. توکن دوم حتماً یکی از تایم‌فریم‌های معتبر باشد
        # ۲. توکن چهارم دقیقاً و فقط کاراکتر مجزای "0" یا "9" باشد (با فاصله قبل از آن)
        if tf in valid_tfs and last_tok in ["0", "9"]:
            return True
    return False

def main():
    # Load data
    data = {"last_update_id": 0, "alerts": [], "alert_counter": 0}
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

            # محاسبهٔ خودمان: کلوز الان نسبت به کلوز ۲۴ ساعت قبل (به درصد تابلو کاری ندارد)
            up_count, down_count, covered = get_true_24h_counts(stats_data, data)

            # اگر داده ناقص بود، یک بار دیگر با گرفتن مجدد قیمت‌ها تلاش کن
            if (up_count + down_count) == 0:
                up_count, down_count, covered = get_true_24h_counts(stats_data, data, force=True)

            if (up_count + down_count) == 0:
                send_message(chat_id, "دریافت قیمت‌ها انجام نشد. لطفاً چند لحظه بعد دوباره بزنید.", keyboard)
                continue

            total = up_count + down_count
            if total > 0:
                trend = build_market_status_line(up_count, down_count)
                if trend:
                    msg = (f"روند بازار {trend}\n"
                           f"تعداد ارزهای مثبت {up_count}\n"
                           f"تعداد ارزهای منفی {down_count}")
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
            msg = (
                "لطفا نام ارز، نشانه متنی، قیمت tp و قیمت stop را وارد نمایید.\n"
                "(قیمت ورود به صورت خودکار برابر با قیمت لحظه‌ای بازار ثبت می‌شود)\n\n"
                "مثال‌ها:\n"
                "xrp 2.51 0.4\n"
                "xrp فروش اهرم 7 2.51 0.4\n"
                "btc لانگ اهرم 10 98000 91000"
            )
            force_reply_markup = {"force_reply": True, "input_field_placeholder": "xrp فروش اهرم 7 2.51 0.4"}
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
                    tag_display = str(tag).strip() if tag and not str(tag).replace('.', '').isdigit() else "ندارد"
                    
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

                    # تشخیص نوع معامله (شورت یا لانگ):
                    trade_type = a.get('trade_type', '')
                    is_short = (trade_type == 'short')
                    tp_val = float(a.get('tp', 0) or 0)
                    stop_val = float(a.get('stop', 0) or 0)
                    if not trade_type:
                        if entry > 0:
                            if tp_val > 0 and tp_val < entry:
                                is_short = True
                            elif stop_val > 0 and stop_val > entry:
                                is_short = True
                            elif tp_val > 0 and tp_val > entry:
                                is_short = False
                            elif stop_val > 0 and stop_val < entry:
                                is_short = False
                        if not is_short and any(k in str(tag).lower() for k in ['شورت', 'فروش', 'short', 'sell', 'مثبت']):
                            is_short = True
                        
                    leverage = int(a.get("leverage") or 7)
                    if leverage == 1:
                        leverage = 7
                    diff_pct = 0.0
                    if entry > 0 and close_price > 0:
                        if is_short:
                            # در معامله شورت: در نزول قیمت سود، در صعود قیمت ضرر
                            diff_pct = round(((entry - close_price) / entry) * 100 * leverage, 2)
                        else:
                            # در معامله لانگ: در صعود قیمت سود، در نزول قیمت ضرر
                            diff_pct = round(((close_price - entry) / entry) * 100 * leverage, 2)
                    
                    abs_diff = abs(diff_pct)
                    if abs_diff == int(abs_diff):
                        diff_val_str = str(int(abs_diff))
                    else:
                        diff_val_str = f"{abs_diff:.2f}".rstrip('0').rstrip('.')

                    if diff_pct > 0:
                        pnl_str = f"سود + {diff_val_str}٪"
                    elif diff_pct < 0:
                        pnl_str = f"ضرر - {diff_val_str}٪"
                    else:
                        pnl_str = "سود + 0٪"
                    
                    msg += (
                        f"{i}- نام: {sym}  نشانه: {tag_display}\n"
                        f"قیمت: {fmt_price(close_price)}  entri: {fmt_price(entry)}\n"
                        f"تیپی: {fmt_price(a['tp'])}  استاپ: {fmt_price(a['stop'])}\n"
                        f"{pnl_str}\n\n"
                    )
                
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

        elif text in ["چارت 📊", "چارت", "chart"]:
            guide_msg = (
                "برای دریافت چارت، 4 بخش زیر را با فاصله وارد نمایید:\n\n"
                "1 نام ارز\n"
                "2 تایم فریم (15 ، 30 ، 1 ، 2 ، 4)\n"
                "3 قیمت مد نظر (مبدأ)\n"
                "4 کد 0 برای کمترین قیمت یا 9 برای بیشترین قیمت\n\n"
                "سیستم به طور خودکار از قیمت مبدأ تا زمان فعلی کندل‌ها را خروجی می‌دهد.\n\n"
                "مثال:\n"
                "btc 1 65000 0\n"
                "eth 4 2500 9"
            )
            force_reply_markup = {"force_reply": True, "input_field_placeholder": "btc 1 65000 0"}
            send_message(chat_id, guide_msg, force_reply_markup)

        elif check_is_chart(text, message):
            parts = text.replace("چارت", "").replace(",", " ").strip().split()
            if len(parts) == 4:
                chart_res = process_chart_request(parts[0], parts[1], parts[2], parts[3])
                send_message(chat_id, chart_res, keyboard)
            else:
                send_message(chat_id, "فرمت دستور چارت اشتباه است! لطفاً به این شکل بفرستید:\nbtc 1 65000 0", keyboard)

        elif text.startswith("هشدار") or (
            ("قیمت tp" in message.get("reply_to_message", {}).get("text", "") or "قیمت ورود" in message.get("reply_to_message", {}).get("text", ""))
            and not check_is_chart(text, message)
        ) or (
            len(text.replace("هشدار", "").replace(",", " ").strip().split()) >= 3
            and any(char.isdigit() for char in text)
            and not check_is_chart(text, message)
        ):

            raw = text.replace("هشدار", "").replace(",", " ").strip()
            # تبدیل اعداد فارسی به انگلیسی
            persian_digits = '۰۱۲۳۴۵۶۷۸۹'
            for idx_p, d in enumerate(persian_digits):
                raw = raw.replace(d, str(idx_p))

            parts = raw.split()
            sym = parts[0].lower().replace("_usdt", "").replace("usdt", "")
            tag = ""
            entry = 0.0
            tp = 0.0
            stop = 0.0
            leverage = 7
            valid = False

            # پارس اهرم در صورت وجود (پیش‌فرض ۷)
            lev_match = re.search(r'اهرم\s*(\d+)', raw)
            if lev_match:
                try:
                    leverage = int(lev_match.group(1))
                except Exception:
                    leverage = 7

            # طبق دستور دقیق کاربر:
            # دو کادر/عدد آخر در نظر گرفته می‌شوند:
            # آخرین عدد (چهارمی) = استاپ (stop)
            # یکی مانده به آخر (سومی) = تی‌پی (tp)
            # تمام بخش‌های بین نام ارز و تی‌پی = نشانه (tag)
            try:
                stop = float(parts[-1])
                tp = float(parts[-2])
                tag_parts = parts[1:-2]
                tag = " ".join(tag_parts).strip()
                valid = True
            except (ValueError, IndexError):
                # اگر فقط یک عدد در انتها وارد شده بود (فقط تی‌پی)
                try:
                    tp = float(parts[-1])
                    stop = 0.0
                    tag_parts = parts[1:-1]
                    tag = " ".join(tag_parts).strip()
                    valid = True
                except (ValueError, IndexError):
                    valid = False

            if valid:
                if sym in prices:
                    if "alerts" not in data:
                        data["alerts"] = []

                    # قیمت کلوز اینتری = قیمت زنده بازار در لحظه ثبت معامله
                    entry = float(prices.get(sym, 0))

                    # قانون مستقیم کاربر:
                    # اگر سومی که تیپی هست زیر قیمت کلوز اینتری باشه معامله شورت
                    # و اگر تیپی بالای قیمت کلوز اینتری باشه معامله لانگ
                    if tp < entry:
                        trade_type = "short"
                    else:
                        trade_type = "long"

                    # شماره ترتیبی هشدار
                    data["alert_counter"] = data.get("alert_counter", 0) + 1
                    alert_num = data["alert_counter"]

                    data["alerts"].append({
                        "symbol": sym,
                        "tag": tag,
                        "entry": entry,
                        "tp": tp,
                        "stop": stop,
                        "trade_type": trade_type,
                        "leverage": leverage,
                        "alert_num": alert_num,
                        "chat_id": chat_id,
                        "created_at": int(datetime.utcnow().timestamp())
                    })
                    tag_display = tag if tag else "بدون نشانه"
                    type_display = "شورت (فروش)" if trade_type == "short" else "لانگ (خرید)"
                    confirm_msg = (
                        f"✅ هشدار با موفقیت ثبت شد!\n\n"
                        f"نام: {sym.upper()}  نوع: {type_display}\n"
                        f"نشانه: {tag_display}\n"
                        f"entri: {fmt_price(entry)}\n"
                        f"تیپی: {fmt_price(tp)}  استاپ: {fmt_price(stop)}"
                    )
                    send_message(chat_id, confirm_msg, keyboard)
                else:
                    send_message(chat_id, f"ارز {sym.upper()} در بازار تتری اوربیت پیدا نشد! لطفا نام ارز را صحیح بنویسید.", keyboard)
            else:
                send_message(chat_id, "فرمت اشتباه است! حداقل باید نام ارز و دو قیمت (tp و stop) وارد شود.\nمثال:\nxrp 2.51 0.4\nxrp 1.58 2.51 0.4\nxrp فروش منفی 7 درصد اهرم 7 1.58 2.51 0.4", keyboard)
                
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
                    f"قیمت {fmt_price(price_now)}\n"
                    f"میزان رشد +{growth} % درصد تابلو {sign}{day_change} %\n"
                    f"کمترین قیمت {fmt_price(day_low)}\n"
                    f"بیشترین قیمت {fmt_price(day_high)}\n"
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
            
        entry_price = float(alert.get("entry", 0) or 0)
        tp_price = float(alert.get("tp", 0) or 0)
        stop_price = float(alert.get("stop", 0) or 0)
        trade_type = alert.get("trade_type", "")
        
        # تشخیص دقیق شورت یا لانگ
        is_short = (trade_type == "short")
        if not trade_type:
            if tp_price > 0 and entry_price > 0:
                is_short = (tp_price < entry_price)
            elif stop_price > 0 and entry_price > 0:
                is_short = (stop_price > entry_price)
            elif any(k in str(alert.get("tag", "")).lower() for k in ["شورت", "فروش", "short", "sell", "مثبت"]):
                is_short = True
            else:
                is_short = False

        triggered = False
        triggered_type = ""
        trigger_price = 0
        
        if is_short:
            # در معامله شورت:
            # تی‌پی پایین‌تر از نقطه ورود است (نزول قیمت = سود)
            if tp_price > 0 and current_price <= tp_price:
                triggered = True
                triggered_type = "tp"
                trigger_price = tp_price
            # استاپ بالاتر از نقطه ورود است (صعود قیمت = ضرر)
            elif stop_price > 0 and current_price >= stop_price:
                triggered = True
                triggered_type = "stop"
                trigger_price = stop_price
        else:
            # در معامله لانگ:
            # تی‌پی بالاتر از نقطه ورود است (صعود قیمت = سود)
            if tp_price > 0 and current_price >= tp_price:
                triggered = True
                triggered_type = "tp"
                trigger_price = tp_price
            # استاپ پایین‌تر از نقطه ورود است (نزول قیمت = ضرر)
            elif stop_price > 0 and current_price <= stop_price:
                triggered = True
                triggered_type = "stop"
                trigger_price = stop_price
            
        if triggered:
            leverage = int(alert.get("leverage") or 7)
            if leverage == 1:
                leverage = 7
            alert_num = alert.get("alert_num", "")

            # محاسبه دقیق سود یا ضرر با اهرم
            # در شورت: نزول = سود، صعود = ضرر
            # در لانگ: صعود = سود، نزول = ضرر
            if entry_price > 0:
                if is_short:
                    pnl_pct = ((entry_price - trigger_price) / entry_price) * leverage * 100
                else:
                    pnl_pct = ((trigger_price - entry_price) / entry_price) * leverage * 100
                pnl_pct_rounded = round(abs(pnl_pct))
                if pnl_pct >= 0:
                    pnl_label = f"سود + {pnl_pct_rounded}٪"
                else:
                    pnl_label = f"ضرر - {pnl_pct_rounded}٪"
            else:
                pnl_label = ""

            pnl_text = f" : {pnl_label}" if pnl_label else ""
            tag_part = f" {alert.get('tag')}" if alert.get("tag") else ""
            msg_alert = (
                f"نام {sym.lower()}{tag_part}"
                f" entri {fmt_price(entry_price)}"
                f" {triggered_type} {fmt_price(trigger_price)}"
                f"{pnl_text}"
            )
            send_message(ALERT_CHANNEL, msg_alert)
            send_message(alert["chat_id"], f"هشدار فعال شد:\n{msg_alert}")
        else:
            remaining_alerts.append(alert)
            
    data["alerts"] = remaining_alerts

    # Daily Market Status Report to CHANNEL_REPORT_MAIN
    # مرحله ۱: ساعت ۱۹:۲۰ عکس می‌گیرد (از عدد خود صرافی)
    # مرحله ۲: ساعت ۱۹:۲۵ همان عکس را ارسال می‌کند
    iran_time = datetime.utcnow() + timedelta(hours=3, minutes=30)
    shamsi_date = jdatetime.datetime.fromgregorian(datetime=iran_time).strftime('%Y %m %d')
    today_str = jdatetime.datetime.fromgregorian(datetime=iran_time).strftime('%Y/%m/%d')
    time_str = iran_time.strftime('%H : %M')
    current_date_str = f"{shamsi_date} ساعت {time_str} دقیقه"

    minute_of_day = iran_time.hour * 60 + iran_time.minute
    snap_minute = 19 * 60 + 20   # 19:20
    send_minute = 19 * 60 + 25   # 19:25

    if data.get("last_daily_report_date") != today_str:

        # --- مرحله ۱: عکس‌گرفتن ساعت ۱۹:۲۰ ---
        if minute_of_day >= snap_minute and data.get("pending_report_date") != today_str:
            if stats_data:
                snap_up = 0
                snap_down = 0
                for item in stats_data.values():
                    chg = item.get("dayChange", 0)
                    if chg > 0:
                        snap_up += 1
                    elif chg < 0:
                        snap_down += 1

                if (snap_up + snap_down) > 0:
                    data["pending_report"] = {
                        "date": today_str,
                        "up": snap_up,
                        "down": snap_down,
                        "time_str": current_date_str,
                    }
                    data["pending_report_date"] = today_str

        # --- مرحله ۲: ارسال ساعت ۱۹:۲۵ ---
        pending = data.get("pending_report") or {}
        if minute_of_day >= send_minute and pending.get("date") == today_str:
            up_count = int(pending.get("up", 0))
            down_count = int(pending.get("down", 0))

            trend = build_market_status_line(up_count, down_count)
            if trend:
                daily_report_msg = (
                    f"حال بازار {trend}\n"
                    f"تعداد ارزهای مثبت {up_count}\n"
                    f"تعداد ارزهای منفی {down_count}\n\n"
                    f"تاریخ {pending.get('time_str', current_date_str)}"
                )
                send_message(CHANNEL_REPORT_MAIN, daily_report_msg)
                data["last_daily_report_date"] = today_str
                data.pop("pending_report", None)
                data.pop("pending_report_date", None)
    
    # Save data locally
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving data: {e}")

if __name__ == "__main__":
    main()
