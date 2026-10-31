import json
import os
import math
import re
import requests
import pandas as pd
import jdatetime
from datetime import datetime, timedelta, timezone
import warnings
import time
from concurrent.futures import ThreadPoolExecutor

warnings.filterwarnings('ignore')

SELL_BOT_TOKEN = os.environ.get("SELL_BOT_TOKEN") or ""
BUY_BOT_TOKEN = os.environ.get("BUY_BOT_TOKEN") or ""
EXIT_BOT_TOKEN = os.environ.get("EXIT_BOT_TOKEN") or ""
REPORT_BOT_TOKEN = os.environ.get("REPORT_BOT_TOKEN") or "8865582989:AAHRhGoMjnVUsBpCNj_FlZAm-Hmk7p_SR0E"
WEEKLY_REPORT_BOT_TOKEN = os.environ.get("WEEKLY_REPORT_BOT_TOKEN") or "8820733728:AAEM4e3UlWM7YekuFcFwsPXBd-GWsgievHE"

def get_exit_token():
    """توکن خروج: اگر EXIT_BOT_TOKEN تنظیم شده باشد از آن استفاده می‌کند،
    در غیر این صورت از SELL_BOT_TOKEN (که حتماً باید تنظیم شده باشد) استفاده می‌کند."""
    return EXIT_BOT_TOKEN if EXIT_BOT_TOKEN else SELL_BOT_TOKEN

PERSONAL_ID = "114669886"
CHANNEL_EXIT_MAIN = "-1004415777827"
CHANNEL_REPORT_MAIN = "-1004304608564"
CHANNEL_WEEKLY_REPORT = "-1004462143665"

CATEGORIES = {
    "20_30": {
        "name_fa": "+20 الی 30 %",
        "entry_channel": "-1004290922830",
        "report_channel": "-1003914385862",
        "entry_drop": 0.14,
        "tp_drop": 0.075,
        "stop_rise": 0.14,
        "trade_type": "short",
        "leverage": 7,
        "enabled": False
    },
    "30_40": {
        "name_fa": "+30 الی 40 %",
        "entry_channel": "-1004290922830",
        "report_channel": "-1003733086854",
        "entry_drop": 0.15,
        "tp_drop": 0.15,
        "stop_rise": 0.14,
        "trade_type": "short",
        "leverage": 7
    },
    "40_50": {
        "name_fa": "+40 الی 50 %",
        "entry_channel": "-1004290922830",
        "report_channel": "-1003945753248",
        "entry_drop": 0.15,
        "tp_drop": 0.15,
        "stop_rise": 0.14,
        "trade_type": "short",
        "leverage": 7
    },
    "50_60": {
        "name_fa": "+50 الی 60 %",
        "entry_channel": "-1004290922830",
        "report_channel": "-1003781040656",
        "entry_drop": 0.15,
        "tp_drop": 0.15,
        "stop_rise": 0.14,
        "trade_type": "short",
        "leverage": 7
    },
    "60_70": {
        "name_fa": "+60 الی 70 %",
        "entry_channel": "-1004290922830",
        "report_channel": "-1004379515603",
        "entry_drop": 0.15,
        "tp_drop": 0.15,
        "stop_rise": 0.14,
        "trade_type": "short",
        "leverage": 7
    },
    "70_80": {
        "name_fa": "+70 الی 80 %",
        "entry_channel": "-1004290922830",
        "report_channel": "-1003820960180",
        "entry_drop": 0.15,
        "tp_drop": 0.15,
        "stop_rise": 0.14,
        "trade_type": "short",
        "leverage": 7
    },
    "80_90": {
        "name_fa": "+80 الی 90 %",
        "entry_channel": "-1004290922830",
        "report_channel": "-1004310315552",
        "entry_drop": 0.15,
        "tp_drop": 0.15,
        "stop_rise": 0.14,
        "trade_type": "short",
        "leverage": 7
    },
    "90_100": {
        "name_fa": "+90 الی 100 %",
        "entry_channel": "-1004290922830",
        "report_channel": "-1004452909288",
        "entry_drop": 0.15,
        "tp_drop": 0.15,
        "stop_rise": 0.14,
        "trade_type": "short",
        "leverage": 7
    },
    "100_plus": {
        "name_fa": "+100 % به بالا",
        "entry_channel": "-1004290922830",
        "report_channel": "-1004458729980",
        "entry_drop": 0.25,
        "tp_drop": 0.25,
        "stop_rise": 0.25,
        "trade_type": "short",
        "leverage": 4
    }
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRADES_FILE = os.path.join(SCRIPT_DIR, "trades.json")
BASE_URL = 'https://futures.ourbit.com/api/v1/contract/kline'
ORDERBOOK_URL = 'https://futures.ourbit.com/api/v1/contract/ticker'

iran_time = datetime.utcnow() + timedelta(hours=3, minutes=30)
shamsi_date = jdatetime.datetime.fromgregorian(datetime=iran_time).strftime('%Y %m %d')
today_str = jdatetime.datetime.fromgregorian(datetime=iran_time).strftime('%Y/%m/%d')
time_str = iran_time.strftime('%H : %M')
current_date_str = f"{shamsi_date} ساعت {time_str} دقیقه"

def load_data():
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_trades = [t for t in data.get('trades', []) if t.get('symbol', '').endswith('_USDT')]
                
                # برای هر symbol و دسته فقط آخرین OPEN رو نگه‌دار (تکراری‌ها حذف)
                seen_open = set()
                deduped = []
                for t in reversed(all_trades):
                    if t.get('status') == 'OPEN':
                        key = (t.get('symbol', '').upper(), t.get('category_id'))
                        if key not in seen_open:
                            seen_open.add(key)
                            deduped.append(t)
                    else:
                        deduped.append(t)
                deduped.reverse()
                data['trades'] = deduped
                return data
        except Exception:
            pass
    return {"last_report_date": "", "trades": []}

# معاملات بازی که باید یک‌بار حذف شوند: (نماد، تاریخ ورود، قیمت ورود)
BAD_OPEN_TRADES = [
    ("IRYS_USDT", "1405/08/05", 0.02916),
    ("BEAT_USDT", "1405/08/07", 0.0979),
    ("ON_USDT", "1405/08/08", 0.2156),
]

# شروع تازه (درخواست کاربر): حذف معاملات باز + صفر شدن گزارش روز و هفته از این لحظه
# فقط یک بار اجرا می‌شود (تا وقتی report_start_ts در حافظه ثبت نشده باشد).
RESET_REPORTS_ONCE = False

def remove_bad_open_trades(trades):
    return [t for t in trades if str(t.get('status')) != 'OPEN']
    """حذف معامله(های) بازِ مشخص‌شده؛ پس از حذف دیگر در فایل نمی‌مانند و تکرار نمی‌شود."""
    if not BAD_OPEN_TRADES:
        return trades
    out = []
    for t in trades:
        if t.get('status') == 'OPEN':
            sym = (t.get('symbol') or '').upper()
            day = str(t.get('open_time') or '')
            try:
                entry = float(t.get('entry') or 0)
            except Exception:
                entry = 0.0
            bad = False
            for s, d, p in BAD_OPEN_TRADES:
                if sym == s and day == d and abs(entry - p) < 1e-9:
                    bad = True
                    break
            if bad:
                print(f"removed bad open trade: {sym} {day} {entry}")
                continue
        out.append(t)
    return out

def save_data(data):
    with open(TRADES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def send_telegram_message(token, chat_ids, text):
    if not token:
        return
    for chat_id in chat_ids:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception:
            pass

def send_telegram_document(token, chat_ids, file_path, caption):
    if not token:
        return
    for chat_id in chat_ids:
        url = f"https://api.telegram.org/bot{token}/sendDocument"
        try:
            with open(file_path, 'rb') as f:
                files = {'document': f}
                data = {'chat_id': chat_id, 'caption': caption}
                requests.post(url, data=data, files=files, timeout=20)
        except Exception:
            pass

def clean_symbol(symbol):
    s = symbol.replace('_USDT', '').replace('USDT', '')
    if s == '' or s == 'BTC':
        return 'BTC'
    return s

def format_volume(val):
    if val is None or pd.isna(val):
        return '0'
    if val >= 1_000_000_000:
        return f'{val / 1_000_000_000:.2f}b'
    elif val >= 1_000_000:
        return f'{val / 1_000_000:.2f}m'
    elif val >= 1_000:
        return f'{val / 1_000:.0f}k'
    else:
        return f'{int(val)}'

def round_price(val):
    if val is None or val == 0:
        return 0.0
    val_float = float(val)
    if abs(val_float) >= 1:
        return round(val_float, 4)
    exponent = math.floor(math.log10(abs(val_float)))
    leading_zeros = -exponent - 1
    decimals = leading_zeros + 4
    return round(val_float, decimals)

def drop_to_percent(drop):
    """تبدیل نسبت افت دسته به درصد تمیز برای نمایش در پیام: 0.14 → 14 و 0.075 → 7.5"""
    p = round(float(drop) * 100, 1)
    return int(p) if p % 1 == 0 else p

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

def get_market_overview():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(ORDERBOOK_URL, headers=headers, timeout=20)
        data = response.json()
        valid_map = {}
        items = data.get('data', [])
        if isinstance(items, list):
            for ticker in items:
                sym = ticker.get('symbol', '')
                if sym.endswith('_USDT'):
                    valid_map[sym] = ticker
        return valid_map
    except Exception:
        pass
    return {}

def get_candles(symbol, resolution=60, num_candles=24):
    url = f"{BASE_URL}/{symbol}?interval=Min60"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        res = response.json()
        if res.get('success') and 'data' in res:
            data = res['data']
            df = pd.DataFrame(data)
            if len(df) > 0:
                df = df.tail(num_candles).reset_index(drop=True)
                df['open'] = df['open'].astype(float)
                df['high'] = df['high'].astype(float)
                df['low'] = df['low'].astype(float)
                df['close'] = df['close'].astype(float)
                df['volume'] = df['amount'].astype(float)
                return df
    except Exception:
        pass
    return None

def first_touch_after(symbol, tp_price, stop_price, start_utc_ts, trade_type='short'):
    """ترتیب واقعی برخورد قیمت با tp و stop با کندل‌های ۱ دقیقه‌ای.
    خروجی: 'tp' یا 'stop' یا None (اگر هیچ‌کدام نخورده باشد)"""
    try:
        url = f"{BASE_URL}/{symbol}?interval=Min1&limit=1440"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15).json()
        data = res.get('data') or {}
        times = data.get('time') or []
        highs = data.get('high') or []
        lows = data.get('low') or []
        tp_ts = None
        st_ts = None
        for i in range(min(len(times), len(highs), len(lows))):
            try:
                ts = float(times[i])
                if ts > 1e11:
                    ts /= 1000.0
                if ts < start_utc_ts:
                    continue
                hi = float(highs[i])
                lo = float(lows[i])
            except Exception:
                continue
            if trade_type == 'short':
                hit_tp = lo <= tp_price
                hit_st = hi >= stop_price
            else:
                hit_tp = hi >= tp_price
                hit_st = lo <= stop_price
            if hit_tp and tp_ts is None:
                tp_ts = ts
            if hit_st and st_ts is None:
                st_ts = ts
            if tp_ts is not None and st_ts is not None:
                break
        if tp_ts is None and st_ts is None:
            return None
        if st_ts is None:
            return 'tp'
        if tp_ts is None:
            return 'stop'
        return 'tp' if tp_ts <= st_ts else 'stop'
    except Exception:
        return None

def calculate_short_pnl(entry, exit_price, leverage=7):
    pnl = ((entry - exit_price) / entry) * 100 * leverage
    return round(pnl, 2)

def calculate_long_pnl(entry, exit_price, leverage=7):
    pnl = ((exit_price - entry) / entry) * 100 * leverage
    return round(pnl, 2)

def get_coin_day_number(trades, trade, today_str, status=None):
    """شمارهٔ این معامله برای همین ارز در همین روز.
    اگر status داده شود فقط معاملات همان نوع (tp یا stop) شمرده می‌شوند؛
    یعنی تی‌پی‌ها در شمارش استاپ حساب نمی‌شوند و برعکس."""
    sym = (trade.get('symbol') or '').upper()
    day = []
    for t in trades:
        if (t.get('symbol') or '').upper() != sym:
            continue
        if not (t.get('open_time') == today_str or t.get('close_time') == today_str):
            continue
        if status is not None and str(t.get('status', '')).lower() != status:
            continue
        day.append(t)
    day.sort(key=lambda t: float(t.get('open_timestamp') or 0))
    for i, t in enumerate(day):
        if t is trade:
            return i + 1
    return 1

def is_release_entry(trades, symbol, current_ts, lock_hours=24, window_hours=72):
    """آیا این ورود، ورودِ بعد از پایانِ قفل ۲۴ ساعتهٔ استاپ است؟ (علامت z)
    یعنی ارز قبلاً قفل شده بود و بعد از یک روز دوباره معامله می‌شود."""
    sym = symbol.upper()
    last_stop = 0.0
    for t in trades:
        if t.get('symbol', '').upper() != sym:
            continue
        if str(t.get('status', '')).lower() != 'stop':
            continue
        try:
            ts = float(t.get('close_timestamp') or t.get('open_timestamp') or 0)
        except Exception:
            ts = 0.0
        if ts > last_stop:
            last_stop = ts
    if last_stop <= 0:
        return False
    age = current_ts - last_stop
    return lock_hours * 3600 <= age <= window_hours * 3600

def coin_is_z(trades, symbol, current_ts, today_str):
    """آیا این ارز امروز در حالت z است؟
    یعنی قبلاً قفل بوده و بعد از یک روز آزاد شده؛ تا آخر همان روز
    همهٔ معاملاتش (ورود و خروج) با z علامت می‌خورند."""
    sym = symbol.upper()
    for t in trades:
        if t.get('symbol', '').upper() != sym:
            continue
        if t.get('open_time') == today_str and t.get('release_entry'):
            return True
    return is_release_entry(trades, symbol, current_ts)

def generate_entry_message(trade_type, symbol, cat_name, growth, neg_percent, low, high, entry, tp, stop, vol, date_str, coin_num=1, daily_count=0, release_flag=False):
    name = clean_symbol(symbol).lower()
    type_str = "فروش" if trade_type == 'short' else "خرید"
    # شمارشگر «۱» نمایش داده نمی‌شود: اولین معامله فقط کلمه، از معامله دوم عدد بعد از کلمه می‌آید
    parts = [type_str]
    if coin_num and int(coin_num) > 1:
        parts.append(str(int(coin_num)))
    elif daily_count and int(daily_count) > 1:
        parts.append(str(int(daily_count)))
    head = " ".join(parts)
    if release_flag:
        head = f"{head} z"
    return (
        f"{head}\n"
        f"نام: {name}\n"
        f"دسته بندی رشد: {cat_name}  میزان رشد: +{growth:.2f} %\n"
        f"تاریخ: {date_str}\n"
        f"{market_state_block()}"
        f"Entri: {fmt_price(entry)} tp: {fmt_price(tp)} stop: {fmt_price(stop)}\n"
        f"حجم: {vol}\n"
        f"low: {fmt_price(low)} hi: {fmt_price(high)}"
    )

def calculate_duration_str(start_ts, end_ts):
    try:
        total_seconds = max(0, int(end_ts - start_ts))
    except Exception:
        total_seconds = 0
        
    days = total_seconds // 86400
    rem_seconds = total_seconds % 86400
    hours = rem_seconds // 3600
    minutes = (rem_seconds % 3600) // 60
    
    parts = []
    if days > 0:
        parts.append(f"{days} روز")
    if hours > 0:
        parts.append(f"{hours} ساعت")
    if minutes > 0:
        parts.append(f"{minutes} دقیقه")
        
    return " و ".join(parts) if parts else "کمتر از ۱ دقیقه"

def format_shamsi_from_timestamp(ts):
    if not ts:
        return current_date_str
    try:
        dt = datetime.fromtimestamp(ts)
        s_date = jdatetime.datetime.fromgregorian(datetime=dt).strftime('%Y %m %d')
        s_time = dt.strftime('%H : %M')
        return f"{s_date} ساعت {s_time} دقیقه"
    except Exception:
        return current_date_str

def generate_exit_message(exit_type, symbol, cat_name, growth, neg_percent, low, high, entry, tp, stop, vol, start_date_str, end_date_str, duration_str, daily_count, trade_type, coin_num=1, release_flag=False):
    name = clean_symbol(symbol).lower()
    status_fa = str(exit_type)
    # شمارشگر «۱» نمایش داده نمی‌شود: اولین خروج فقط کلمه، از خروج دوم عدد بعد از کلمه می‌آید
    parts = [status_fa]
    if coin_num and int(coin_num) > 1:
        parts.append(str(int(coin_num)))
    elif daily_count and int(daily_count) > 1:
        parts.append(str(int(daily_count)))
    if release_flag:
        parts.append("z")
    msg = f"{' '.join(parts)}\n"
    msg += f"نام: {name}\n"
    msg += f"دسته بندی رشد: {cat_name} میزان رشد: +{growth:.2f} %\n"
    if exit_type == "tp":
        entry_line = f"Entri: {fmt_price(entry)} tp: {fmt_price(tp)}\n"
    else:
        entry_line = f"Entri: {fmt_price(entry)} stop: {fmt_price(stop)}\n"
    msg += f"شروع: {start_date_str}\n"
    msg += f"پایان: {end_date_str}\n"
    msg += f"مدت {duration_str}\n"
    msg += market_state_block()
    msg += entry_line
    msg += f"حجم: {vol}\n"
    msg += f"low: {fmt_price(low)} hi: {fmt_price(high)}"
    return msg

def get_valid_categories(growth):
    cats = []
    if growth >= 100:
        cats = ["100_plus", "90_100", "80_90", "70_80", "60_70", "50_60", "40_50", "30_40", "20_30"]
    elif 90 <= growth < 100:
        cats = ["90_100", "80_90", "70_80", "60_70", "50_60", "40_50", "30_40", "20_30"]
    elif 80 < growth <= 90:
        cats = ["80_90", "70_80", "60_70", "50_60", "40_50", "30_40", "20_30"]
    elif 70 < growth <= 80:
        cats = ["70_80", "60_70", "50_60", "40_50", "30_40", "20_30"]
    elif 60 < growth <= 70:
        cats = ["60_70", "50_60", "40_50", "30_40", "20_30"]
    elif 50 < growth <= 60:
        cats = ["50_60", "40_50", "30_40", "20_30"]
    elif 40 < growth <= 50:
        cats = ["40_50", "30_40", "20_30"]
    elif 30 < growth <= 40:
        cats = ["30_40", "20_30"]
    # ارزهایی که رشد آنها از صفر تابلو تا مثبت 30 درصد بوده کلاً غیرفعال هستند و هیچی اضافه نمی‌شود
    return cats

def get_category_for_growth(growth_val):
    if growth_val >= 90:
        return "90_100"
    elif growth_val >= 80:
        return "80_90"
    elif growth_val >= 70:
        return "70_80"
    elif growth_val >= 60:
        return "60_70"
    elif growth_val >= 50:
        return "50_60"
    elif growth_val >= 40:
        return "40_50"
    elif growth_val >= 30:
        return "30_40"
    else:
        return "20_30"

CAT_ORDER = ["100_plus", "90_100", "80_90", "70_80", "60_70", "50_60", "40_50", "30_40", "20_30"]

def get_tp_blocked_categories(trades, symbol, current_ts):
    """دسته‌هایی که برای این ارز تا ۲۴ ساعت بعد از TP ممنوع هستند.
    قانون: بعد از TP در یک دسته، همان دسته و تمام دسته‌های بالاتر تا ۲۴ ساعت ممنوع‌اند
    و معامله فقط در دسته‌های پایین‌تر مجاز است."""
    blocked = set()
    for t in trades:
        if t.get('symbol', '').upper() != symbol.upper():
            continue
        if str(t.get('status', '')).lower() != 'tp':
            continue
        cat = t.get('category_id')
        if cat not in CAT_ORDER:
            continue
        try:
            ref_ts = float(t.get('close_timestamp') or t.get('open_timestamp') or 0)
        except Exception:
            ref_ts = 0.0
        if ref_ts > 0:
            in_24h = (current_ts - ref_ts) < (24 * 3600)
        else:
            in_24h = (t.get('close_time') == today_str)
        if not in_24h:
            continue
        idx = CAT_ORDER.index(cat)
        # دسته‌های بالاتر ممنوع می‌شوند
        blocked.update(CAT_ORDER[:idx])
        # استثنا: tp در دسته ۱۰۰+ خودِ دسته ۱۰۰+ را ممنوع نمی‌کند
        # (اگر قیمت بعد از tp دوباره به نقطه ورود برگردد، معامله مجدد مجاز است)
        if cat != '100_plus':
            blocked.add(cat)
    return blocked

def entry_level_cat_name(entry_price, low_24h, cat_id):
    """نام دستهٔ نمایشی بر اساس رشدِ نقطهٔ ورود نسبت به کف ۲۴ ساعته.
    مثال: رشد ۹۳٪ و ورود ۱۵٪ زیر سقف → رشد نقطهٔ ورود ۶۴٪ → «۶۰ الی ۷۰».
    برای دستهٔ ۱۰۰+ همان «۱۰۰+» می‌ماند (چون اهرم و درصدها متفاوت است)."""
    try:
        if cat_id == '100_plus':
            return CATEGORIES['100_plus']['name_fa']
        e = float(entry_price or 0)
        lo = float(low_24h or 0)
        if e > 0 and lo > 0:
            g = (e - lo) / lo * 100.0
            if g >= 100:
                cid = '90_100'
            else:
                cid = get_category_for_growth(g)
            if cid in CATEGORIES:
                return CATEGORIES[cid]['name_fa']
    except Exception:
        pass
    return CATEGORIES.get(cat_id, {}).get('name_fa', '')

# حداکثر تعداد tp هر زنجیره، بر اساس دستهٔ شروع زنجیره
CATEGORY_TP_CAP = {
    '30_40': 1, '40_50': 1,
    '50_60': 2, '60_70': 2,
    '70_80': 3, '80_90': 3, '90_100': 3,
    '100_plus': 2,
}

def get_chain_info(trades, symbol, trade):
    """(طول زنجیره تا این معامله، دستهٔ شروع زنجیره)"""
    lst = [t for t in trades
           if (t.get('symbol') or '').upper() == symbol.upper()
           and str(t.get('open_time')) == str(trade.get('open_time'))]
    lst.sort(key=lambda x: float(x.get('open_timestamp') or 0))
    try:
        i = lst.index(trade)
    except ValueError:
        return 1, trade.get('category_id')
    j = i
    while j > 0 and lst[j].get('leg') == 'tp':
        j -= 1
    return i - j + 1, lst[j].get('category_id')

def cascade_bump(start_cat, step):
    """ضریب بالاتر بودن نقطهٔ ورود پشتبند از tp معاملهٔ قبلی.
    step = شمارهٔ ورود جدید در زنجیره (۲ = ورود دوم، ۳ = ورود سوم).
    ورود دوم در ۴۰-۵۰/۵۰-۶۰/۶۰-۷۰ و ورود سوم در ۷۰-۸۰/۸۰-۹۰/۹۰-۱۰۰ → ۱۰٪
    بقیه → ۵٪"""
    if start_cat in ('40_50', '50_60', '60_70') and step == 2:
        return 1.10
    if start_cat in ('70_80', '80_90', '90_100') and step == 3:
        return 1.10
    return 1.05

def chain_cap_reached(trades, symbol, trade):
    """آیا زنجیرهٔ این ارز به سقف tp خود رسیده است؟"""
    n, start_cat = get_chain_info(trades, symbol, trade)
    cap = CATEGORY_TP_CAP.get(start_cat)
    if cap is None:
        return False
    return n >= cap

def is_cascade_trade(trades, trade):
    """آیا این معامله در «پشتبند» معاملهٔ قبلی باز شده (نه ورود اول)؟
    پشتبند یعنی نقطهٔ ورودش برابر tp یا stop یک معاملهٔ قبلیِ همان ارز است."""
    if trade.get('leg') in ('tp', 'stop'):
        return True
    try:
        entry = float(trade.get('entry') or 0)
    except Exception:
        entry = 0.0
    if entry <= 0:
        return False
    symbol = trade.get('symbol', '').upper()
    try:
        open_ts = float(trade.get('open_timestamp') or 0)
    except Exception:
        open_ts = 0.0
    for t in trades:
        if t is trade:
            continue
        if t.get('symbol', '').upper() != symbol:
            continue
        if str(t.get('status', '')).lower() not in ('tp', 'stop'):
            continue
        try:
            close_ts = float(t.get('close_timestamp') or 0)
        except Exception:
            close_ts = 0.0
        # فقط معامله‌ای که قبل از این معامله بسته شده
        if open_ts > 0 and close_ts > 0 and close_ts > open_ts + 60:
            continue
        for key in ('tp', 'stop'):
            try:
                level = float(t.get(key) or 0)
            except Exception:
                level = 0.0
            if level > 0 and abs(entry - level) / level <= 0.002:
                return True
    return False

def post_lock_new_peak(df, stop_ts_iran, last_high):
    """آیا بعد از پایان قفل ۲۴ ساعته، سقف تازه‌ای بالاتر از سقفِ زمان استاپ زده شده؟
    (سقفِ همان روزِ استاپ به‌عنوان «قلهٔ جدید» حساب نمی‌شود)"""
    try:
        if df is None or 'time' not in df.columns or not last_high:
            return False
        times = df['time'].astype(float)
        if float(times.max()) > 1e12:
            times = times / 1000.0
        lock_end_utc = float(stop_ts_iran) + 24 * 3600 - 12600
        mask = times >= lock_end_utc
        if not bool(mask.any()):
            return False
        highs = df['high'].astype(float)
        return float(highs[mask].max()) > float(last_high)
    except Exception:
        return False

def get_symbol_stop_state(trades, symbol, current_ts, high_24h=None, growth=None, df=None):
    """وضعیت قفلِ بعد از استاپ برای این ارز.
    خروجی: (locked, only_100plus, equality_required, block_low)
    - locked           : تا ۲۴ ساعت هیچ معامله‌ای مجاز نیست
    - only_100plus     : (دیگر استفاده نمی‌شود؛ برای سازگاری نگه داشته شده)
    - equality_required: قیمت ورود باید با قیمت بازار یکی باشد
    - block_low        : بعد از پایان قفل فقط ۵۰-۶۰ و بالاتر مجاز است
                         (۳۰-۴۰ و ۴۰-۵۰ ممنوع) تا پایان بازهٔ ۷۲ ساعته

    قوانین:
    ۱) همان روزِ استاپ: اگر رشد به بالای ۱۰۰٪ برسد → همهٔ دسته‌ها مجاز
       (ورود منفی ۲۵٪، tp ۲۵٪، stop ۲۵٪ و اهرم ۴ برای همهٔ دسته‌ها)
    ۲) بعد از ۲۴ ساعت: ۳۰-۴۰ و ۴۰-۵۰ ممنوع، فقط ۵۰-۶۰ و بالاتر
    ۳) قلهٔ جدید دیگر مجوز نمی‌دهد؛ فقط رشد ۱۰۰٪ یا بیشتر همهٔ دسته‌ها را باز می‌کند

    ملاک، زمان «آخرین استاپ» این ارز است (تی‌پی‌های بعد از استاپ قفل را باز نمی‌کنند)."""
    sym = symbol.upper()
    last_ts = 0.0
    last_cat = ''
    last_high = 0.0
    for t in trades:
        if t.get('symbol', '').upper() != sym:
            continue
        if str(t.get('status', '')).lower() != 'stop':
            continue
        try:
            ts = float(t.get('close_timestamp') or t.get('open_timestamp') or 0)
        except Exception:
            ts = 0.0
        if ts > last_ts:
            last_ts = ts
            last_cat = str(t.get('category_id') or '')
            try:
                last_high = float(t.get('high') or 0)
            except Exception:
                last_high = 0.0

    if last_ts <= 0:
        return False, False, False, False

    age = current_ts - last_ts
    if age < 0:
        return False, False, False, False

    equality_required = age <= 72 * 3600

    # ---------- قفل ۲۴ ساعته ----------
    if age < 24 * 3600:
        # استاپ در دستهٔ ۱۰۰+ → قفل کامل تا فردا
        if last_cat == '100_plus':
            return True, False, True, False
        # همان روز رشد به بالای ۱۰۰٪ رسید → همهٔ دسته‌ها مجاز
        try:
            if growth is not None and float(growth) >= 100:
                return False, False, True, False
        except Exception:
            pass
        return True, False, True, False

    # ---------- بعد از ۲۴ ساعت ----------
    # رشد بالای ۱۰۰٪ → همهٔ دسته‌ها مجاز
    try:
        if growth is not None and float(growth) >= 100:
            return False, False, equality_required, False
    except Exception:
        pass

    # قلهٔ جدید دیگر مجوز نمی‌دهد (به درخواست کاربر حذف شد)
    # فقط رشد ۱۰۰٪ یا بیشتر همهٔ دسته‌ها را باز می‌کند
    # ۳۰-۴۰ و ۴۰-۵۰ بعد از استاپ همیشه ممنوع هستند - حتی بعد از ۷۲ ساعت
    # ارزهای z نباید در دسته‌های پایین وارد شوند
    return False, False, equality_required, True

def price_returned_to_level(df, since_ts_utc, level):
    """آیا قیمت بعد از زمان داده‌شده (ثانیه UTC) دوباره به این سطح رسیده است؟"""
    try:
        if df is None or 'time' not in df.columns:
            return False
        times = df['time'].astype(float)
        if float(times.max()) > 1e12:
            times = times / 1000.0
        highs = df['high'].astype(float)
        # ۶۰ ثانیه حاشیه: کندلِ ساعتِ خودِ تی‌پی (که سقفش ممکن است قبل از تی‌پی باشد) حساب نشود
        mask = times > (float(since_ts_utc) + 60)
        if not bool(mask.any()):
            return False
        return float(highs[mask].max()) >= float(level)
    except Exception:
        return False

def count_recent_sub_trades(trades, symbol, current_ts, hours=24):
    """تعداد معاملات پایین‌دست (غیر ۱۰۰+) این ارز در ۲۴ ساعت گذشته"""
    n = 0
    for t in trades:
        if t.get('symbol', '').upper() != symbol.upper():
            continue
        if t.get('category_id') == '100_plus':
            continue
        try:
            ref_ts = float(t.get('open_timestamp') or 0)
        except Exception:
            ref_ts = 0.0
        if ref_ts > 0:
            recent = (current_ts - ref_ts) < (hours * 3600)
        else:
            recent = (t.get('open_time') == today_str)
        if recent:
            n += 1
    return n

def get_overall_market_trend(market_overview):
    up_count = 0
    down_count = 0
    for ticker in market_overview.values():
        try:
            rate = float(ticker.get('riseFallRate', 0))
            if rate > 0:
                up_count += 1
            elif rate < 0:
                down_count += 1
        except Exception:
            pass
            
    total = up_count + down_count
    if total == 0:
        return "ranging"
        
    up_pct = (up_count / total) * 100
    down_pct = (down_count / total) * 100
    
    if up_pct >= 60.0:
        return "bullish"   # صعودی
    elif down_pct >= 60.0:
        return "bearish"   # نزولی
    else:
        return "ranging"   # رنج

def get_market_summary_string(market_overview=None):
    if not market_overview:
        market_overview = get_market_overview()
    up_count = 0
    down_count = 0
    for ticker in market_overview.values():
        try:
            rate = float(ticker.get('riseFallRate', 0))
            if rate > 0:
                up_count += 1
            elif rate < 0:
                down_count += 1
        except Exception:
            pass
            
    total = up_count + down_count
    if total == 0:
        return "حال بازار رنج\nتعداد ارزهای مثبت 0\nتعداد ارزهای منفی 0\n\n"
        
    up_pct = int(round((up_count / total) * 100))
    down_pct = int(round((down_count / total) * 100))
    
    if up_pct >= 60:
        return f"حال بازار صعودی +{up_pct} %\nتعداد ارزهای مثبت {up_count}\nتعداد ارزهای منفی {down_count}\n\n"
    elif down_pct >= 60:
        return f"حال بازار نزولی -{down_pct} %\nتعداد ارزهای مثبت {up_count}\nتعداد ارزهای منفی {down_count}\n\n"
    else:
        return f"حال بازار رنج\nتعداد ارزهای مثبت {up_count}\nتعداد ارزهای منفی {down_count}\n\n"

# ---------- فیلتر هم‌خوانی قیمت ورود با قیمت بازار ----------
# قیمت محاسبه‌شدهٔ ورود باید با قیمت لحظهٔ بازار (کلوز) یکی باشد؛
# اختلاف مجاز ۰.۵ درصد است (برای صفر کردن دقیقاً، مقدار را کمتر کن)
ENTRY_MATCH_TOL = 0.005

# ---------- حال بازار (همان روش ربات «حال بازار») ----------
# شمارش مثبت/منفی بر اساس ۲۴ ساعت واقعی: کلوز الان نسبت به کلوز ۲۴ ساعت قبل.
# یک‌بار در ساعت محاسبه و در trades.json ذخیره می‌شود تا سیگنال‌ها معطل نشن.
MARKET_STATE_MAX_AGE = 3600
# حداقل پوشش: اگر کمتر از این نسبت از ارزها حساب شوند، عدد ناقص است و نمایش داده نمی‌شود
MARKET_MIN_COVERAGE = 0.80
HAAL_DATA_URL = "https://raw.githubusercontent.com/mamal1366mamali/nobitex-bot/main/haal_data.json"
_MARKET_STATE = {'up': 0, 'down': 0, 'ts': 0.0}
_MARKET_CTX = {'app_data': None, 'overview': None}

def _ref_24h_pair(pair, tries=2, sleep_base=0.3):
    """کلوز ۲۴ ساعت قبل از کندل ۵ دقیقه‌ای"""
    target = time.time() - 24 * 3600
    for i in range(tries):
        try:
            r = requests.get(
                f"{BASE_URL}/{pair}?interval=Min5&limit=300",
                headers={"User-Agent": "Mozilla/5.0"}, timeout=20
            )
            d = (r.json().get("data") or {})
            times = d.get("time") or []
            closes = d.get("close") or []
            best = None
            first = None
            for ts, c in zip(times, closes):
                try:
                    t = float(ts)
                    cv = float(c)
                except Exception:
                    continue
                if t > 1e11:
                    t /= 1000.0
                if first is None and cv > 0:
                    first = cv
                if t <= target:
                    best = cv
                else:
                    break
            if best and best > 0:
                return best
            # ارزهای تازه‌لیست‌شده که ۲۴ ساعت سابقه ندارند: قدیمی‌ترین کندل موجود
            if first and first > 0:
                return first
        except Exception:
            pass
        if i < tries - 1:
            time.sleep(sleep_base * (i + 1))
    return None

def _fetch_refs_24h(pairs, workers=12, tries=2, sleep_base=0.3):
    if not pairs:
        return {}
    out = {}
    try:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            res = list(ex.map(lambda p: _ref_24h_pair(p, tries, sleep_base), pairs))
        for p, v in zip(pairs, res):
            if v:
                out[p] = v
    except Exception:
        pass
    return out

def _fetch_refs_staged(pairs):
    """چند مرحله تلاش: اول پرسرعت، بعد آهسته‌تر برای ارزهایی که جواب ندادند
    (صرافی درخواست‌های هم‌زمان زیاد را محدود می‌کند؛ با تلاش دوباره تقریباً همه شمرده می‌شوند)"""
    refs = {}
    missing = list(pairs)
    for workers, tries, pause in ((10, 2, 0.4), (6, 3, 0.8), (3, 4, 1.5)):
        if not missing:
            break
        got = _fetch_refs_24h(missing, workers=workers, tries=tries, sleep_base=pause)
        refs.update(got)
        missing = [p for p in missing if not refs.get(p)]
    return refs

def _haal_refs(now):
    """مراجع ۲۴ ساعتهٔ ربات حال بازار، اگر مربوط به همین ساعت باشد
    (اول فایل محلی، اگر ناقص بود نسخهٔ گیت‌هاب) — این‌طوری بیشتر وقت‌ها بدون درخواست حساب می‌شود"""
    hour = int(now // 3600)
    out = {}
    try:
        with open('haal_data.json', encoding='utf-8') as f:
            rc = (json.load(f) or {}).get('ref_cache') or {}
        if int(rc.get('hour') or 0) == hour:
            out = {str(k).upper(): v for k, v in (rc.get('prices') or {}).items()}
    except Exception:
        pass
    if len(out) > 300:
        return out
    try:
        r = requests.get(HAAL_DATA_URL, timeout=20)
        rc = (r.json() or {}).get('ref_cache') or {}
        if int(rc.get('hour') or 0) == hour:
            remote = {str(k).upper(): v for k, v in (rc.get('prices') or {}).items()}
            if len(remote) > len(out):
                out = remote
    except Exception:
        pass
    return out

def build_market_trend_line(up_count, down_count):
    total = up_count + down_count
    if total <= 0:
        return ""
    up_pct = int(round((up_count / total) * 100))
    if up_count * 3 <= total:
        return f"نزولی {up_pct} %"
    if up_count * 3 >= total * 2:
        return f"صعودی {up_pct} %"
    return f"رنج {up_pct} %"

def _cached_state_ok(cached):
    """آیا عدد حال بازارِ ذخیره‌شده قابل اعتماد است؟ (پوشش کافی داشته باشد)"""
    try:
        up = int(cached.get('up') or 0)
        down = int(cached.get('down') or 0)
        if up + down <= 0:
            return False
        total = int(cached.get('total') or 0)
        counted = int(cached.get('counted') or 0)
        if total > 0:
            return counted >= total * MARKET_MIN_COVERAGE
        # ذخیره‌های قدیمی که تعداد کل را ندارند
        return (up + down) >= 500
    except Exception:
        return False

def ensure_market_state():
    """حال بازار را (در صورت کهنه بودن) حساب می‌کند؛ حداکثر یک‌بار در ساعت"""
    global _MARKET_STATE
    now = time.time()
    if _MARKET_STATE.get('ts') and (now - _MARKET_STATE['ts']) < MARKET_STATE_MAX_AGE:
        return _MARKET_STATE

    app_data = _MARKET_CTX.get('app_data')
    if not isinstance(app_data, dict):
        app_data = {}
    cached = app_data.get('market_state') or {}
    try:
        if cached and (now - float(cached.get('ts') or 0)) < MARKET_STATE_MAX_AGE:
            if _cached_state_ok(cached):
                _MARKET_STATE = {
                    'up': int(cached.get('up') or 0),
                    'down': int(cached.get('down') or 0),
                    'ts': float(cached.get('ts') or now),
                }
                return _MARKET_STATE
    except Exception:
        pass

    overview = _MARKET_CTX.get('overview') or get_market_overview()
    if not overview:
        return _MARKET_STATE

    total = len(overview)
    refs = _haal_refs(now)

    def _key(sym):
        return sym.split('_')[0].upper()

    missing = [s for s in overview.keys() if not refs.get(_key(s))]
    if missing:
        got = _fetch_refs_staged(missing)
        for s, v in got.items():
            refs[_key(s)] = v

    up = 0
    down = 0
    for sym, item in overview.items():
        ref = refs.get(_key(sym))
        try:
            last = float(item.get('lastPrice') or 0)
        except Exception:
            last = 0.0
        if not ref or last <= 0:
            continue
        if last > float(ref):
            up += 1
        elif last < float(ref):
            down += 1

    counted = up + down

    # اگر بخش زیادی از ارزها حساب نشده باشند، عدد ناقص و گمراه‌کننده است:
    # یا از مقدار قبلی استفاده می‌شود یا دو خط حال بازار نمایش داده نمی‌شود
    if total > 0 and counted < total * MARKET_MIN_COVERAGE:
        print(f"market state incomplete: {counted}/{total}")
        prev_up = int(cached.get('up') or 0)
        prev_down = int(cached.get('down') or 0)
        if prev_up + prev_down > 0:
            _MARKET_STATE = {'up': prev_up, 'down': prev_down, 'ts': float(cached.get('ts') or 0)}
            return _MARKET_STATE
        return {'up': 0, 'down': 0, 'ts': 0.0}

    _MARKET_STATE = {'up': up, 'down': down, 'ts': now}
    if isinstance(app_data, dict):
        app_data['market_state'] = {'up': up, 'down': down, 'ts': now, 'total': total, 'counted': counted}
    return _MARKET_STATE

def market_state_block():
    """یک خط حال بازار برای انتهای پیام سیگنال"""
    st = ensure_market_state()
    up = int(st.get('up') or 0)
    down = int(st.get('down') or 0)
    trend = build_market_trend_line(up, down)
    if not trend:
        return ""
    return f"روند بازار {trend} تعداد ارزهای مثبت {up} تعداد ارزهای منفی {down}\n"

# ---------- پایش اعلانات «حذف ارز» در صرافی ----------
DELIST_SECTION_URL = "https://www.ourbit.com/support/categories/360000254192"
DELIST_ARTICLE_URL = "https://www.ourbit.com/support/articles/{id}"
DELIST_CHECK_INTERVAL = 6 * 3600     # هر ۶ ساعت یک‌بار اعلانات چک می‌شود
DELIST_CLOSE_BEFORE = 3 * 3600       # سه ساعت مانده به زمان حذف، معامله بسته می‌شود
DELIST_MAX_PER_RUN = 8

_MONTHS_EN = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
}


def real_now_ts():
    """زمان واقعی UTC به epoch (مستقل از ساعت داخلی برنامه)"""
    return datetime.now(timezone.utc).timestamp()


def ts_to_iran_str(ts):
    """epoch واقعی → تاریخ شمسی و ساعت تهران"""
    try:
        dt = datetime.fromtimestamp(float(ts), timezone(timedelta(hours=3, minutes=30)))
        jd = jdatetime.date.fromgregorian(date=dt.date())
        return f"{jd.year}/{jd.month:02d}/{jd.day:02d} ساعت {dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        return "-"


def _next_data_json(html):
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def fetch_delist_announcements():
    """لیست اعلان‌های بخش «حذف ارز» صرافی: [(id, title)]"""
    try:
        r = requests.get(DELIST_SECTION_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=25)
        j = _next_data_json(r.text)
        if not j:
            return []
        groups = (((j.get('props') or {}).get('pageProps') or {}).get('_articleLists')) or []
        items = []
        for g in groups:
            for a in (g.get('articles') or []):
                title = a.get('title') or ''
                if a.get('id') and re.search(r'delist', title, re.I):
                    items.append((str(a['id']), title))
        return items
    except Exception:
        return []


def parse_delist_deadline_utc(text):
    """زمان حذف از متن اعلان (UTC) → epoch واقعی"""
    m = re.search(r'(\d{1,2}):(\d{2})\s*,?\s*([A-Za-z]+)\s+(\d{1,2})\s*,?\s*(\d{4})\s*\(UTC\)', text)
    if not m:
        return None
    try:
        month = _MONTHS_EN.get(m.group(3).lower())
        if not month:
            return None
        dt = datetime(int(m.group(5)), month, int(m.group(4)),
                      int(m.group(1)), int(m.group(2)), tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


def fetch_delist_symbols(article_id):
    """نمادهای اعلان حذف + زمان حذف (None یعنی خطا)"""
    try:
        r = requests.get(DELIST_ARTICLE_URL.format(id=article_id),
                         headers={'User-Agent': 'Mozilla/5.0'}, timeout=25)
        j = _next_data_json(r.text)
        if not j:
            return None
        fd = ((j.get('props') or {}).get('pageProps') or {}).get('fallbackData') or {}
        body = (fd.get('data') or {}).get('body') or ''
        if not body:
            return None
        text = re.sub(r'<[^>]+>', ' ', body)
        for a, b in (('&nbsp;', ' '), ('&#39;', "'"), ('&amp;', '&'), ('&quot;', '"')):
            text = text.replace(a, b)
        symbols = set(re.findall(r'\b([A-Z0-9]{2,15})USDT\b', text.upper()))
        return symbols, parse_delist_deadline_utc(text)
    except Exception:
        return None


def check_delist_announcements(app_data, trades, current_ts):
    """هر ۶ ساعت اعلانات حذف ارز خوانده می‌شود؛ برای معاملهٔ بازِ در خطر، زمان حذف ذخیره می‌شود"""
    now = real_now_ts()
    try:
        last_check = float(app_data.get('delist_last_check') or 0)
    except Exception:
        last_check = 0.0
    if now - last_check < DELIST_CHECK_INTERVAL:
        return

    announcements = fetch_delist_announcements()
    if not announcements:
        return  # صفحه در دسترس نبود؛ دفعهٔ بعد تلاش می‌شود

    app_data['delist_last_check'] = int(now)
    seen = set(str(x) for x in (app_data.get('delist_seen_ids') or []))
    open_trades = [t for t in trades if t.get('status') == 'OPEN']

    processed = 0
    for aid, title in announcements:
        if aid in seen or processed >= DELIST_MAX_PER_RUN:
            continue
        processed += 1
        result = fetch_delist_symbols(aid)
        if result is None:
            continue  # خطا → «دیده‌شده» علامت نمی‌شود تا بعداً دوباره تلاش شود
        symbols, deadline = result
        seen.add(aid)
        # فقط اعلان‌هایی که زمان حذفشان مشخص و مربوط به آیندهٔ نزدیک است
        if deadline is None or deadline < real_now_ts() - 86400:
            continue
        for trade in open_trades:
            base = (trade.get('symbol') or '').upper().replace('_USDT', '')
            if not base or base not in symbols or trade.get('delist_ts'):
                continue
            trade['delist_ts'] = float(deadline)
            trade['delist_announce_title'] = title
            name = clean_symbol(trade.get('symbol', '')).lower()
            when = ts_to_iran_str(deadline)
            msg = (
                "اعلان حذف ارز در صرافی\n"
                f"{name}\n"
                f"زمان حذف : {when}\n"
                "برنامه : تا ۳ ساعت مانده به حذف نگه داشته می‌شود تا شاید tp بخورد،\n"
                "اگر tp نخورد ۳ ساعت قبل از حذف بسته می‌شود"
            )
            send_telegram_message(REPORT_BOT_TOKEN, [PERSONAL_ID], msg)

    app_data['delist_seen_ids'] = list(seen)[-300:]


# ================== مدیریت سرمایه (فعلاً غیرفعال) ==================
# برای فعال‌سازی فقط CAPITAL_MANAGEMENT_ENABLED را True کن.
CAPITAL_MANAGEMENT_ENABLED = False

CONTRACT_DETAIL_URL = "https://futures.ourbit.com/api/v1/contract/detail"

CAPITAL_SETTINGS = {
    'total_capital': 4.78,       # موجودی فعلی (دلار)
    'max_trades': 50,            # سرمایه روی ۵۰ معامله تقسیم می‌شود
    'min_per_trade': 0.20,       # کف مارجین هر معامله (۲۰ سنت)
    'max_per_trade': 100000.0,   # سقف مارجین هر معامله
    'default_leverage': 7,
}

# جدول پله‌ها: (سرمایه از این عدد به بالا, مارجین هر معامله)
# مبنا = عدد گردِ پایین‌تر، تقسیم بر ۵۰
CAPITAL_TIERS = [
    (30, 0.40), (40, 0.60), (50, 0.80), (60, 1.00), (70, 1.20), (80, 1.40), (90, 1.60),
    (100, 1.80), (110, 2.00),
    (160, 3.00), (210, 4.00), (260, 5.00), (310, 6.00), (360, 7.00),
    (410, 8.00), (460, 9.00), (510, 10.00),
    (610, 12.00), (710, 14.00), (810, 16.00), (910, 18.00),
    (1100, 20.00), (1600, 30.00), (2100, 40.00), (2600, 50.00), (3000, 60.00),
    (3600, 70.00), (4100, 80.00), (4600, 90.00), (5100, 100.00),
    (6100, 120.00), (7100, 140.00), (8100, 160.00), (9100, 180.00),
    (10100, 200.00), (21000, 400.00), (31000, 600.00), (41000, 800.00), (51000, 1000.00),
    (110000, 2000.00), (210000, 4000.00), (310000, 6000.00), (410000, 8000.00), (510000, 10000.00),
    (610000, 12000.00), (710000, 14000.00),
    (1100000, 20000.00), (2100000, 40000.00), (3100000, 60000.00),
    (4100000, 80000.00), (5100000, 100000.00),
]

_contract_details_cache = {}


def get_contract_details():
    """جزئیات قراردادها (contractSize و minVol) — یک‌بار خوانده و کش می‌شود"""
    global _contract_details_cache
    if _contract_details_cache:
        return _contract_details_cache
    try:
        r = requests.get(CONTRACT_DETAIL_URL, timeout=20)
        data = (r.json() or {}).get('data') or []
        cache = {}
        for c in data:
            if c.get('symbol'):
                cache[c['symbol']] = c
        if cache:
            _contract_details_cache = cache
    except Exception:
        pass
    return _contract_details_cache


def get_wallet_capital(settings=None):
    """موجودی کل"""
    s = settings or CAPITAL_SETTINGS
    try:
        return max(0.0, float(s.get('total_capital', 0)))
    except Exception:
        return 0.0


def get_margin_per_trade(capital=None, settings=None):
    """مارجین هر معامله بر اساس پله‌های سرمایه"""
    s = settings or CAPITAL_SETTINGS
    if capital is None:
        capital = get_wallet_capital(s)
    try:
        capital = float(capital)
    except Exception:
        return 0.0
    if capital <= 0:
        return 0.0

    min_per = float(s.get('min_per_trade', 0.20))
    max_per = float(s.get('max_per_trade', 100000.0))

    # زیر ۳۰ دلار: ثابت ۲۰ سنت
    if capital < 30:
        return min(min_per, max_per)

    size = min_per
    for threshold, value in CAPITAL_TIERS:
        if capital >= threshold:
            size = value
        else:
            break
    return min(size, max_per)


def get_total_slots(capital=None, settings=None):
    """چند معاملهٔ همزمان با این سرمایه ممکن است (بدون کسر جای خالی)"""
    s = settings or CAPITAL_SETTINGS
    if capital is None:
        capital = get_wallet_capital(s)
    per = get_margin_per_trade(capital, s)
    if per <= 0:
        return 0
    try:
        affordable = int(math.floor(float(capital) / per))
    except Exception:
        return 0
    return max(0, min(int(s.get('max_trades', 50)), affordable))


def count_open_trades(trades):
    """تعداد معاملات باز"""
    return len([t for t in trades if t.get('status') == 'OPEN'])


def get_free_slots(trades, settings=None):
    """جای خالی برای معاملهٔ جدید (یک جای خالی همیشه آزاد می‌ماند)"""
    s = settings or CAPITAL_SETTINGS
    capital = get_wallet_capital(s)
    per = get_margin_per_trade(capital, s)
    if per <= 0:
        return 0
    usable = max(0, get_total_slots(capital, s) - 1)
    return max(0, usable - count_open_trades(trades))


def get_available_margin(trades, settings=None):
    """مارجین آزاد = موجودی − مارجین معاملات باز − یک سهم ذخیره"""
    s = settings or CAPITAL_SETTINGS
    capital = get_wallet_capital(s)
    per = get_margin_per_trade(capital, s)
    if per <= 0:
        return 0.0
    locked = 0.0
    for t in trades:
        if t.get('status') == 'OPEN':
            try:
                locked += float(t.get('cap_margin') or per)
            except Exception:
                locked += per
    return max(0.0, capital - locked - per)


def get_min_order_notional(symbol, price):
    """کوچک‌ترین سفارش ممکن این ارز به دلار (۱ قرارداد)"""
    c = get_contract_details().get(symbol)
    if not c or not price:
        return None
    try:
        min_vol = float(c.get('minVol') or 1)
        contract_size = float(c.get('contractSize') or 0)
        if contract_size <= 0:
            return None
        return min_vol * contract_size * float(price)
    except Exception:
        return None


def get_position_size(symbol, price, leverage=None, margin=None, settings=None):
    """تعداد قرارداد و مارجین لازم برای یک معامله طبق سهم تعیین‌شده"""
    s = settings or CAPITAL_SETTINGS
    lev = float(leverage or s.get('default_leverage', 7))
    if lev <= 0:
        lev = float(s.get('default_leverage', 7))
    if margin is None:
        margin = get_margin_per_trade(get_wallet_capital(s), s)
    margin = float(margin)
    c = get_contract_details().get(symbol)
    if not c or not price or float(price) <= 0 or margin <= 0:
        return None
    try:
        contract_size = float(c.get('contractSize') or 0)
        min_vol = float(c.get('minVol') or 1)
        if contract_size <= 0:
            return None
        budget = margin * lev
        contracts = int(math.floor(budget / (contract_size * float(price))))
        if contracts < min_vol:
            return {'contracts': 0, 'notional': 0.0, 'margin_used': 0.0, 'leverage': lev}
        notional = contracts * contract_size * float(price)
        return {
            'contracts': contracts,
            'notional': notional,
            'margin_used': notional / lev,
            'leverage': lev,
        }
    except Exception:
        return None


def capital_check(symbol, price, trades, leverage=None, settings=None):
    """آیا از نظر مدیریت سرمایه می‌توان این معامله را گرفت؟
    خروجی: (allowed, reason, size_info)"""
    s = settings or CAPITAL_SETTINGS
    capital = get_wallet_capital(s)
    per = get_margin_per_trade(capital, s)
    if per <= 0:
        return False, 'سرمایه صفر است', None
    if get_free_slots(trades, s) <= 0:
        return False, 'ظرفیت معاملات باز پر است (یک جای خالی ذخیره شده)', None
    if get_available_margin(trades, s) < per:
        return False, 'مارجین آزاد کافی نیست', None
    if not get_contract_details():
        # جزئیات قرارداد در دسترس نیست؛ فقط ظرفیت و مارجین بررسی شده
        return True, 'ok', None
    size = get_position_size(symbol, price, leverage, per, s)
    if not size or size.get('contracts', 0) <= 0:
        return False, 'حداقل سفارش این ارز از سهم ما بیشتر است', None
    return True, 'ok', size


def capital_summary(trades, settings=None):
    """خلاصهٔ وضعیت سرمایه برای گزارش"""
    s = settings or CAPITAL_SETTINGS
    capital = get_wallet_capital(s)
    per = get_margin_per_trade(capital, s)
    total_slots = get_total_slots(capital, s)
    return {
        'capital': capital,
        'margin_per_trade': per,
        'usable_slots': max(0, total_slots - 1),
        'open_trades': count_open_trades(trades),
        'free_slots': get_free_slots(trades, s),
        'available_margin': get_available_margin(trades, s),
    }

def process_markets(app_data):
    trades = app_data.get('trades', [])
    market_overview = get_market_overview()
    _MARKET_CTX['app_data'] = app_data
    _MARKET_CTX['overview'] = market_overview
    market_trend = get_overall_market_trend(market_overview)
    symbols = list(market_overview.keys())
    
    current_ts = iran_time.timestamp()
    open_symbols = set([t['symbol'] for t in trades if t['status'] == 'OPEN'])

    # پایش اعلانات حذف ارز در صرافی (هر ۶ ساعت)
    check_delist_announcements(app_data, trades, current_ts)

    # ارزهایی که اعلان حذف دارند: معاملهٔ جدید روی آن‌ها باز نمی‌شود
    delist_symbols = set()
    for t in trades:
        dts = t.get('delist_ts')
        if dts and float(dts) + 86400 > real_now_ts():
            delist_symbols.add((t.get('symbol') or '').upper())

    # اگر ارزی از صرافی حذف شود (قیمت نداشته باشد) معاملهٔ بازِ آن بسته می‌شود
    if len(symbols) > 100:
        symbol_set = set(symbols)
        closed_delisted = 0
        for t in trades:
            if t.get('status') == 'OPEN' and t.get('symbol') not in symbol_set:
                t['status'] = 'closed'
                t['close_reason'] = 'delisted'
                t['close_price'] = t.get('entry', 0)
                t['pnl'] = 0.0
                t['close_time'] = today_str
                t['close_timestamp'] = int(current_ts)
                closed_delisted += 1
        if closed_delisted:
            print(f"delisted open trades closed: {closed_delisted}")
            open_symbols = set([t['symbol'] for t in trades if t['status'] == 'OPEN'])
    
    for symbol in symbols:
        ticker = market_overview[symbol]
        
        # Fast pre-filter: skip coins with <18% 24h change unless they already have an open trade
        if symbol not in open_symbols:
            try:
                t_high = float(ticker.get('high24Price', 0))
                t_low = float(ticker.get('lower24Price', 0))
                if t_low <= 0 or (((t_high - t_low) / t_low) * 100) < 18.0:
                    continue
            except Exception:
                continue

        df = get_candles(symbol)
        if df is None or len(df) < 2:
            continue
            
        current_close = float(df['close'].iloc[-1])
        low_24h = float(df['low'].min())
        high_24h = float(df['high'].max())
        total_volume_usdt = df['volume'].sum()
        vol_str = format_volume(total_volume_usdt)
        
        growth = 0
        if low_24h > 0:
            growth = ((high_24h - low_24h) / low_24h) * 100

        valid_cats = get_valid_categories(growth)
        open_trades_for_symbol = [t for t in trades if t['symbol'] == symbol and t['status'] == 'OPEN']
        
        for trade in open_trades_for_symbol:
            cat_id = trade.get('category_id', '20_30')
            cat_info = CATEGORIES.get(cat_id, CATEGORIES['20_30'])
            trade_type = cat_info.get('trade_type', 'short')
            
            exit_type = None
            exit_price = None
            
            if trade_type == 'short':
                if current_close <= trade['tp']:
                    exit_type = 'tp'
                    exit_price = trade['tp']
                elif current_close >= trade['stop']:
                    exit_type = 'stop'
                    exit_price = trade['stop']
            else: # long
                if current_close >= trade['tp']:
                    exit_type = 'tp'
                    exit_price = trade['tp']
                elif current_close <= trade['stop']:
                    exit_type = 'stop'
                    exit_price = trade['stop']

            # ارزی که اعلان حذف دارد: ۳ ساعت مانده به زمان حذف با قیمت بازار بسته می‌شود
            if exit_type is None and trade.get('delist_ts') is not None:
                deadline_ts = float(trade.get('delist_ts') or 0)
                close_at = deadline_ts - DELIST_CLOSE_BEFORE if deadline_ts > 0 else real_now_ts()
                if real_now_ts() >= close_at:
                    exit_type = 'delist'
                    exit_price = current_close

            if exit_type == 'delist':
                trade['status'] = 'closed'
                trade['close_reason'] = 'delist_announcement'
                trade['close_time'] = today_str
                trade['close_timestamp'] = int(current_ts)
                trade['close_date_str'] = current_date_str
                trade['close_price'] = exit_price

                trade_lev = trade.get('leverage') or cat_info.get('leverage', 7)
                if trade_type == 'short':
                    pnl = calculate_short_pnl(trade['entry'], exit_price, leverage=trade_lev)
                else:
                    pnl = calculate_long_pnl(trade['entry'], exit_price, leverage=trade_lev)
                trade['pnl'] = pnl
                trade['duration_str'] = calculate_duration_str(trade.get('open_timestamp', int(current_ts)), int(current_ts))

                name = clean_symbol(symbol).lower()
                pnl_str = f"+{pnl:.0f} %" if pnl > 0 else f"{pnl:.0f} %"
                pnl_kind = "سود" if pnl > 0 else ("ضرر" if pnl < 0 else "بدون سود و ضرر")
                when = ts_to_iran_str(trade['delist_ts']) if float(trade.get('delist_ts') or 0) > 0 else 'نامشخص'
                msg_delist = (
                    f"ارز {name} به دلیل حذف از صرافی با {pnl_kind} {pnl_str} بسته شد\n"
                    f"دسته بندی {cat_info['name_fa'].replace('+','')}\n"
                    f"قیمت بسته شدن : {exit_price}\n"
                    f"زمان حذف در صرافی : {when}\n"
                    f"پایان :\n{current_date_str}"
                )
                send_telegram_message(get_exit_token(), [PERSONAL_ID, CHANNEL_EXIT_MAIN, CHANNEL_REPORT_MAIN], msg_delist)
                continue

                    
            if exit_type:
                # اگر در فاصلهٔ خوابِ گیت‌هاب هم tp و هم stop رد شده باشند،
                # ترتیب واقعی برخورد را از کندل‌های ۱ دقیقه‌ای می‌گیریم
                # (این درخواست فقط برای معاملاتی زده می‌شود که همین حالا خروج می‌خورند)
                try:
                    start_iran = float(trade.get('last_seen_ts') or trade.get('open_timestamp') or current_ts)
                except Exception:
                    start_iran = float(current_ts)
                real_order = first_touch_after(
                    symbol, trade['tp'], trade['stop'], start_iran - 12600, trade_type)
                if real_order and real_order != exit_type:
                    exit_type = real_order
                    exit_price = trade['tp'] if real_order == 'tp' else trade['stop']

                trade['status'] = exit_type
                trade['close_time'] = today_str
                trade['close_timestamp'] = int(current_ts)
                trade['close_date_str'] = current_date_str
                trade['close_price'] = exit_price
                
                start_date_str = trade.get('open_date_str') or format_shamsi_from_timestamp(trade.get('open_timestamp'))
                end_date_str = current_date_str
                start_ts = trade.get('open_timestamp', int(current_ts))
                end_ts = int(current_ts)
                duration_str = calculate_duration_str(start_ts, end_ts)
                trade['duration_str'] = duration_str
                
                trade_lev = trade.get('leverage') or cat_info.get('leverage', 7)
                if trade_type == 'short':
                    pnl = calculate_short_pnl(trade['entry'], exit_price, leverage=trade_lev)
                else:
                    pnl = calculate_long_pnl(trade['entry'], exit_price, leverage=trade_lev)
                trade['pnl'] = pnl
                
                neg_pct = trade.get('neg_pct') or (round(cat_info['entry_drop'] * 100, 1) if (cat_info['entry_drop'] * 100) % 1 != 0 else int(cat_info['entry_drop'] * 100))
                
                # تعداد خروجی‌های امروز در کانال اصلی:
                global_exit_count = len([
                    t for t in trades 
                    if t.get('close_time') == today_str 
                    and t.get('status') in ['tp', 'stop']
                ])
                exit_label_global = f"{global_exit_count}"
                
                # شماره ورود این معامله در دسته بندی + عدد ۱ برای کانال دسته بندی:
                entry_num_cat = trade.get('cat_entry_num')
                if not entry_num_cat:
                    same_day_trades = [t for t in trades if t.get('category_id') == cat_id and t.get('open_time') == trade.get('open_time')]
                    try:
                        entry_num_cat = same_day_trades.index(trade) + 1
                    except ValueError:
                        entry_num_cat = 1
                
                exit_label_cat = exit_label_global
                
                coin_num = get_coin_day_number(trades, trade, today_str, status=exit_type)
                
                msg_main = generate_exit_message(
                    exit_type, symbol, entry_level_cat_name(trade['entry'], trade['low'], cat_id), trade['growth'], neg_pct, 
                    trade['low'], trade['high'], trade['entry'], trade['tp'], trade['stop'], 
                    vol_str, start_date_str, end_date_str, duration_str, exit_label_global, trade_type, coin_num,
                    bool(trade.get('release_entry'))
                )
                
                msg_cat = generate_exit_message(
                    exit_type, symbol, entry_level_cat_name(trade['entry'], trade['low'], cat_id), trade['growth'], neg_pct, 
                    trade['low'], trade['high'], trade['entry'], trade['tp'], trade['stop'], 
                    vol_str, start_date_str, end_date_str, duration_str, exit_label_cat, trade_type, coin_num,
                    bool(trade.get('release_entry'))
                )
                
                send_telegram_message(get_exit_token(), [PERSONAL_ID, CHANNEL_EXIT_MAIN], msg_main)
                send_telegram_message(get_exit_token(), [cat_info['report_channel']], msg_cat)

                # اگر خروج با TP بود و معامله short بود: سریعاً همان لحظه (پشتبندش) معامله دسته بعدی باز شود
                if exit_type == 'tp' and trade_type == 'short':
                    cat_order = ["100_plus", "90_100", "80_90", "70_80", "60_70", "50_60", "40_50", "30_40", "20_30"]
                    if cat_id in cat_order:
                        # ارز +۱۰۰٪: اگر رشد هنوز بالای ۱۰۰ باشد → پشتبند در خود دسته ۱۰۰+
                        # (ورود دوم ۵٪ بالاتر از tp قبلی، tp و stop هر دو ۲۵٪، اهرم ۴)
                        # وگرنه دسته‌ای که رشد الان در آن است (۱۵٪ / ۱۴٪)
                        if cat_id == '100_plus':
                            next_cat_id = '100_plus' if growth >= 100 else get_category_for_growth(growth)
                        else:
                            curr_idx = cat_order.index(cat_id)
                            next_idx = curr_idx + 1
                            next_cat_id = cat_order[next_idx] if next_idx < len(cat_order) else None

                        if next_cat_id:
                            
                            # بررسی اینکه دسته بعدی در ۲۴ ساعت گذشته یا امروز معامله نشده باشد
                            next_already_traded = any(
                                t.get('symbol', '').upper() == symbol.upper()
                                and t.get('category_id') == next_cat_id
                                and t.get('status') == 'OPEN'
                                for t in trades
                            )
                            
                            # اگر دستهٔ بعدی غیرفعال باشد، پشتبند هم باز نمی‌شود
                            next_cat_info = CATEGORIES[next_cat_id]
                            next_cat_enabled = next_cat_info.get('enabled', True)

                            # قانون ۲۴ ساعته: دسته‌ای که ۲۴ ساعت اخیر در آن TP خورده (و بالاترها) ممنوع است
                            tp_blocked_cats = get_tp_blocked_categories(trades, symbol, current_ts)

                            # قانون قفل بعد از استاپ: در بازهٔ بعد از قفل، ۳۰-۴۰ و ۴۰-۵۰ ممنوع
                            # (مگر قلهٔ جدید زده باشد) — پشتبند هم از همین قانون تبعیت می‌کند
                            _c_locked, _c_only, _c_eq, c_block_low = get_symbol_stop_state(
                                trades, symbol, current_ts, high_24h=high_24h, growth=growth, df=df)

                            # درصدهای tp و stop همان درصدهای خود دسته هستند (۱۵٪ / ۱۴٪)
                            # اگر ارز بعد از استاپ بالای ۱۰۰٪ است → همهٔ دسته‌ها با شرایط ۱۰۰+ (۲۵٪/۲۵٪/اهرم ۴)
                            c_plus100 = bool((_c_eq and growth >= 100) or next_cat_id == '100_plus')
                            if c_plus100:
                                c_tp_drop = 0.25
                                c_stop_rise = 0.25
                            else:
                                c_tp_drop = next_cat_info['tp_drop']
                                c_stop_rise = next_cat_info['stop_rise']

                            if (not next_already_traded and next_cat_enabled
                                    and next_cat_id not in tp_blocked_cats
                                    and not chain_cap_reached(trades, symbol, trade)
                                    and not (c_block_low and next_cat_id in ('30_40', '40_50'))):
                                # نقطهٔ ورودِ پشتبند بالاتر از نقطهٔ تی‌پی معاملهٔ قبلی:
                                # ۱۰٪ برای زنجیره‌های شروع‌شده در ۵۰-۶۰ و ۶۰-۷۰ (که ریزش
                                # به کف ۲۴ ساعته نزدیک است) و ۵٪ برای بقیه
                                # tp و stop مثل همیشه از خودِ نقطهٔ ورود حساب می‌شوند
                                _chain_n, _chain_cat = get_chain_info(trades, symbol, trade)
                                _bump = cascade_bump(_chain_cat, _chain_n + 1)
                                next_entry = round_price(exit_price * _bump)
                                next_tp = round_price(next_entry * (1 - c_tp_drop))
                                next_stop = round_price(next_entry * (1 + c_stop_rise))
                                next_neg_pct = drop_to_percent(next_cat_info['entry_drop'])
                                
                                cascade_trade = {
                                    'symbol': symbol,
                                    'category_id': next_cat_id,
                                    # کف/سقف/رشد همان معاملهٔ اول زنجیره حفظ می‌شود
                                    # (کف ۲۴ ساعتهٔ لحظه‌ای ملاک نیست)
                                    'growth': trade.get('growth', growth),
                                    'low': trade.get('low', low_24h),
                                    'high': trade.get('high', high_24h),
                                    'entry': next_entry,
                                    'tp': next_tp,
                                    'stop': next_stop,
                                    'neg_pct': next_neg_pct,
                                    'status': 'OPEN',
                                    'open_time': today_str,
                                    'open_timestamp': int(current_ts),
                                    'open_date_str': current_date_str,
                                    'close_time': '',
                                    'close_price': 0.0,
                                    'pnl': 0.0,
                                    'leverage': (4 if c_plus100 else next_cat_info.get('leverage', 7)),
                                    'leg': 'tp'
                                }
                                trades.append(cascade_trade)
                                
                                if coin_is_z(trades[:-1], symbol, current_ts, today_str):
                                    cascade_trade['release_entry'] = True
                                
                                cat_entry_count = len([t for t in trades if t.get('category_id') == next_cat_id and (t.get('open_time') or '').replace(' ', '/') == today_str.replace(' ', '/')])
                                global_entry_count = len([
                                    t for t in trades 
                                    if (t.get('open_time') or '').replace(' ', '/') == today_str.replace(' ', '/')
                                ])
                                cascade_trade['cat_entry_num'] = cat_entry_count
                                cascade_trade['global_entry_num'] = global_entry_count
                                
                                c_coin_num = get_coin_day_number(trades, cascade_trade, today_str)
                                c_zflag = bool(cascade_trade.get('release_entry'))
                                c_msg_main = generate_entry_message(
                                    'short', symbol, entry_level_cat_name(next_entry, cascade_trade['low'], next_cat_id), cascade_trade['growth'], next_neg_pct,
                                    low_24h, high_24h, next_entry, next_tp, next_stop, vol_str, current_date_str,
                                    coin_num=c_coin_num, daily_count=global_entry_count, release_flag=c_zflag
                                )
                                c_msg_cat = generate_entry_message(
                                    'short', symbol, entry_level_cat_name(next_entry, cascade_trade['low'], next_cat_id), cascade_trade['growth'], next_neg_pct,
                                    low_24h, high_24h, next_entry, next_tp, next_stop, vol_str, current_date_str,
                                    coin_num=c_coin_num, daily_count=global_entry_count, release_flag=c_zflag
                                )
                                
                                send_telegram_message(SELL_BOT_TOKEN, [PERSONAL_ID, next_cat_info['entry_channel']], c_msg_main)
                                send_telegram_message(SELL_BOT_TOKEN, [next_cat_info['report_channel']], c_msg_cat)

            # آخرین زمانی که این معاملهٔ باز چک شد (برای تشخیص ترتیب tp/stop بعد از خوابِ ربات)
            if trade.get('status') == 'OPEN':
                trade['last_seen_ts'] = int(current_ts)

        # قانون قفل بعد از استاپ (نزولی و صعودی یکسان):
        # - هر استاپی (ورود اول یا بعد از tp) → قفل ۲۴ ساعته
        # - در مدت قفل فقط دستهٔ ۱۰۰+ مجاز است (اگر رشد از ۱۰۰٪ بگذرد)
        # - بعد از ۲۴ ساعت: ورود فقط با تطابق قیمت با بازار
        locked, only_100plus, equality_required, block_low = get_symbol_stop_state(
            trades, symbol, current_ts, high_24h=high_24h, growth=growth, df=df)
        if locked:
            continue

        # ارزی که اعلان حذف دارد، معاملهٔ جدید روی آن باز نمی‌شود
        if symbol.upper() in delist_symbols:
            continue

        # قانون ۲۴ ساعتهٔ TP: بعد از TP در یک دسته، همان دسته و تمام دسته‌های بالاتر
        # تا ۲۴ ساعت ممنوع‌اند و معامله فقط در دسته‌های پایین‌تر مجاز است
        tp_blocked_cats = get_tp_blocked_categories(trades, symbol, current_ts)

        # بررسی وضعیت معاملات باز این ارز:
        # معامله 100_plus به طور مستقل از دسته‌های زیر ۱۰۰ درصد می‌تواند باز باشد
        # در دسته‌های زیر ۱۰۰ درصد نیز همزمان حداکثر ۱ معامله باز آبشاری وجود دارد
        has_open_100_plus = any(
            t.get('symbol', '').upper() == symbol.upper() and t.get('status') == 'OPEN' and t.get('category_id') == '100_plus'
            for t in trades
        )
        has_open_sub_cat = any(
            t.get('symbol', '').upper() == symbol.upper() and t.get('status') == 'OPEN' and t.get('category_id') != '100_plus'
            for t in trades
        )

        for cat_id in valid_cats:
            cascade_src = None
            # بعد از پایان قفل ۲۴ ساعته: ۳۰-۴۰ و ۴۰-۵۰ ممنوع؛ فقط ۵۰-۶۰ و بالاتر
            # (مگر اینکه بعد از استاپ قلهٔ جدید زده باشد)
            if block_low and cat_id in ('30_40', '40_50'):
                continue
            # در مدت قفلِ بعد از استاپِ ورود اول، فقط دستهٔ ۱۰۰+ اجازهٔ ورود دارد
            if only_100plus and cat_id != '100_plus':
                continue
            # ۲. فقط اگر همین دسته در همین لحظه معامله‌ی باز داشته باشد، دوباره باز نمی‌شود.
            #    کول‌داون استاپ (کل ارز، ۲۴ ساعت) در بالای همین حلقه اعمال می‌شود.
            #    بعد از TP در یک دسته، همان دسته و بالاترها تا ۲۴ ساعت ممنوع‌اند (tp_blocked_cats)
            #    و فقط دسته‌های پایین‌تر مجاز هستند.
            if cat_id in tp_blocked_cats:
                continue

            cat_already_traded = any(
                t.get('symbol', '').upper() == symbol.upper()
                and t.get('category_id') == cat_id
                and t.get('status') == 'OPEN'
                for t in trades
            )

            if cat_already_traded:
                continue

            # ۳. بررسی معامله باز همزمان:
            if cat_id == '100_plus':
                if has_open_100_plus:
                    continue
            else:
                if has_open_sub_cat:
                    continue

            cat_info = CATEGORIES[cat_id]
            # دستهٔ غیرفعال هیچ معامله‌ای باز نمی‌کند (فعلاً ۲۰ تا ۳۰ غیرفعال است)
            if not cat_info.get('enabled', True):
                continue
            trade_type = cat_info.get('trade_type', 'short')
            
            is_fixed = cat_info.get('is_fixed', False)
            if is_fixed:
                target_ratio = 1.0 + cat_info['fixed_growth_target']
                entry_price = round_price(low_24h * target_ratio)
                tp_price = round_price(entry_price * (1 - cat_info['tp_drop']))
                stop_price = round_price(entry_price * (1 + cat_info['stop_rise']))
                should_enter = (current_close >= entry_price)
            else:
                entry_drop = cat_info['entry_drop']
                if trade_type == 'short':
                    cat_order = ["100_plus", "90_100", "80_90", "70_80", "60_70", "50_60", "40_50", "30_40", "20_30"]

                    if growth >= 100:
                        drop_price_25 = round_price(high_24h * (1 - 0.25))
                        drop_growth = ((drop_price_25 - low_24h) / low_24h) * 100 if low_24h > 0 else 0
                        drop_cat = "100_plus" if drop_growth >= 100 else get_category_for_growth(drop_growth)
                        drop_cat_idx = cat_order.index(drop_cat)
                        current_cat_idx = cat_order.index(cat_id) if cat_id in cat_order else 999

                        if cat_id == "100_plus":
                            # ورود اولیه مثبت ۱۰۰ به بالا: منفی ۲۵ درصد سقف، تی‌پی منفی ۲۵ درصد ورود، استاپ مثبت ۲۵ درصد ورود
                            entry_price = drop_price_25
                            tp_price = round_price(entry_price * (1 - 0.25))
                            stop_price = round_price(entry_price * (1 + 0.25))
                            neg_pct = 25
                            should_enter = (current_close <= entry_price and current_close > tp_price)

                            # اگر قبلاً در همین دسته tp خورده، ورود مجدد فقط وقتی مجاز است که
                            # قیمت بعد از آن tp دوباره به همین نقطه ورود برگشته باشد
                            if should_enter:
                                prev_tps = [
                                    t for t in trades
                                    if t.get('symbol', '').upper() == symbol.upper()
                                    and t.get('category_id') == '100_plus'
                                    and str(t.get('status', '')).lower() == 'tp'
                                ]
                                if prev_tps:
                                    last_tp = max(prev_tps, key=lambda t: float(t.get('close_timestamp') or 0))
                                    tp_ts = float(last_tp.get('close_timestamp') or 0)
                                    tp_ts_utc = (tp_ts - 12600) if tp_ts > 0 else 0
                                    if not price_returned_to_level(df, tp_ts_utc, entry_price):
                                        should_enter = False
                        else:
                            # دسته‌های زیر ۱۰۰ درصد برای ارز با رشد بالای ۱۰۰:
                            # اگر ارز بعد از استاپ در بازهٔ قفل/z باشد → همهٔ دسته‌ها با شرایط ۱۰۰+
                            # (ورود منفی ۲۵٪، tp ۲۵٪، stop ۲۵٪، اهرم ۴)
                            if equality_required and growth >= 100:
                                sub_tp_drop = 0.25
                                sub_stop_rise = 0.25
                                sub_entry_drop = 0.25
                            else:
                                sub_tp_drop = cat_info['tp_drop']
                                sub_stop_rise = cat_info['stop_rise']
                                sub_entry_drop = cat_info['entry_drop']
                            # الف) دسته‌های بالاتر و دسته‌ای که افت ۲۵ درصدی در آن واقع شده، کاملاً مسدود هستند (در همان دسته که هیچ)
                            if current_cat_idx <= drop_cat_idx:
                                continue

                            first_cascade_cat = cat_order[drop_cat_idx + 1]

                            # بررسی معاملات قبلی آبشاری زیر ۱۰۰ درصد برای این ارز در چرخه اخیر (امروز یا ۲۴ ساعت گذشته)
                            prev_sub_trades = [
                                t for t in trades 
                                if t.get('symbol', '').upper() == symbol.upper() and t.get('category_id') in cat_order and t.get('category_id') != '100_plus' and (
                                    t.get('open_time') == today_str or t.get('close_time') == today_str or
                                    (current_ts - float(t.get('open_timestamp') or 0)) < (24 * 3600)
                                )
                            ]

                            chain_reset = (not prev_sub_trades) or (
                                str(prev_sub_trades[-1].get('status', '')).lower() == 'stop')
                            if chain_reset:
                                # دسته ۲۰ تا ۳۰ هرگز با رشد ۲۰-۳۰ درصدی باز نمی‌شود؛ فقط پشتبندِ دستهٔ بالایی
                                if cat_id == '20_30':
                                    continue
                                # اولین معامله آبشار فقط در دسته بلافاصله زیر افت مجاز است (مثلاً ۷۰-۸۰)
                                if cat_id != first_cascade_cat:
                                    continue

                                cat_targets = {
                                    "90_100": 2.00,
                                    "80_90": 1.90,
                                    "70_80": 1.80,
                                    "60_70": 1.70,
                                    "50_60": 1.60,
                                    "40_50": 1.50,
                                    "30_40": 1.40,
                                    "20_30": 1.30
                                }
                                target_ratio = cat_targets.get(cat_id, 1.30)
                                entry_price = round_price(low_24h * target_ratio * (1 - sub_entry_drop))
                                tp_price = round_price(entry_price * (1 - sub_tp_drop))
                                stop_price = round_price(entry_price * (1 + sub_stop_rise))
                                neg_pct = drop_to_percent(sub_entry_drop)
                                should_enter = (current_close <= entry_price and current_close > tp_price)
                            else:
                                # اگر قبلاً معامله آبشاری انجام شده و TP خورده باشد، معامله بعدی از طریق پشتبند TP باز می‌شود
                                last_sub = prev_sub_trades[-1]
                                if last_sub.get('status') == 'tp':
                                    last_cat_idx = cat_order.index(last_sub['category_id'])
                                    if current_cat_idx == last_cat_idx + 1:
                                        entry_price = round_price(float(last_sub['tp']))
                                        tp_price = round_price(entry_price * (1 - sub_tp_drop))
                                        stop_price = round_price(entry_price * (1 + sub_stop_rise))
                                        neg_pct = drop_to_percent(sub_entry_drop)
                                        should_enter = (current_close <= entry_price and current_close > tp_price)
                                    else:
                                        continue
                                else:
                                    continue
                    else:
                        # منطق ارزهای با رشد زیر ۱۰۰ درصد:
                        current_cat_idx = cat_order.index(cat_id) if cat_id in cat_order else 999
                        cat_targets = {
                            "90_100": 2.00,
                            "80_90": 1.90,
                            "70_80": 1.80,
                            "60_70": 1.70,
                            "50_60": 1.60,
                            "40_50": 1.50,
                            "30_40": 1.40,
                            "20_30": 1.30
                        }

                        # بررسی معاملات قبلی آبشاری زیر ۱۰۰ درصد برای این ارز در چرخه اخیر (امروز یا ۲۴ ساعت گذشته)
                        prev_sub_trades = [
                            t for t in trades 
                            if t.get('symbol', '').upper() == symbol.upper() and t.get('category_id') in cat_order and (
                                t.get('open_time') == today_str or t.get('close_time') == today_str or
                                (current_ts - float(t.get('open_timestamp') or 0)) < (24 * 3600)
                            )
                        ]

                        chain_reset = (not prev_sub_trades) or (
                            str(prev_sub_trades[-1].get('status', '')).lower() == 'stop')
                        if chain_reset:
                            # دسته ۲۰ تا ۳۰ هرگز با رشد ۲۰-۳۰ درصدی باز نمی‌شود؛ فقط پشتبندِ دستهٔ بالایی
                            if cat_id == '20_30':
                                continue
                            if cat_id == valid_cats[0]:
                                entry_price = round_price(high_24h * (1 - entry_drop))
                            else:
                                target_ratio = cat_targets.get(cat_id, 1.30)
                                entry_price = round_price(low_24h * target_ratio * (1 - entry_drop))

                            tp_price = round_price(entry_price * (1 - cat_info['tp_drop']))
                            stop_price = round_price(entry_price * (1 + cat_info['stop_rise']))
                            neg_pct = round(cat_info['entry_drop'] * 100, 1) if (cat_info['entry_drop'] * 100) % 1 != 0 else int(cat_info['entry_drop'] * 100)
                            should_enter = (current_close <= entry_price and current_close > tp_price)
                        else:
                            last_sub = prev_sub_trades[-1]
                            if last_sub.get('status') == 'tp':
                                # سقف tp زنجیره بر اساس دستهٔ شروع
                                if chain_cap_reached(trades, symbol, last_sub):
                                    continue
                                cascade_src = last_sub
                                last_cat = last_sub.get('category_id')
                                if last_cat == '100_plus':
                                    # زنجیرهٔ ارز +۱۰۰٪: دسته جدید = دسته‌ای که رشد الان در آن است
                                    # و نقطه ورود = tp همان معامله ۱۰۰+ (tp ۱۵٪ و stop ۱۴٪ و اهرم ۷)
                                    if cat_id != get_category_for_growth(growth):
                                        continue
                                else:
                                    last_cat_idx = cat_order.index(last_cat)
                                    if current_cat_idx != last_cat_idx + 1:
                                        continue
                                # ورود پشتبند: ۱۰٪ بالاتر از tp برای زنجیره‌های
                                # شروع‌شده در ۵۰-۶۰ و ۶۰-۷۰، و ۵٪ برای بقیه
                                _cn2, _start_cat = get_chain_info(trades, symbol, last_sub)
                                _bump2 = cascade_bump(_start_cat, _cn2 + 1)
                                entry_price = round_price(float(last_sub['tp']) * _bump2)
                                tp_price = round_price(entry_price * (1 - cat_info['tp_drop']))
                                stop_price = round_price(entry_price * (1 + cat_info['stop_rise']))
                                neg_pct = drop_to_percent(cat_info['entry_drop'])
                                should_enter = (current_close <= entry_price and current_close > tp_price)
                            else:
                                continue
                else: # long
                    entry_price = round_price(high_24h * (1 - entry_drop))
                    tp_price = round_price(entry_price * (1 + cat_info['tp_rise']))
                    stop_price = round_price(entry_price * (1 - cat_info['stop_drop']))
                    neg_pct = round(cat_info['entry_drop'] * 100, 1) if (cat_info['entry_drop'] * 100) % 1 != 0 else int(cat_info['entry_drop'] * 100)
                    should_enter = (current_close >= entry_price and current_close < tp_price)

            # شرط ارزی که اخیراً استاپ خورده (باگ تی‌پی الکی):
            # قیمت محاسبه‌شدهٔ ورود باید با قیمت لحظهٔ بازار (کلوز) یکی باشد؛
            # اگر قیمت از سطح ورود فاصله گرفته باشد، این معامله انجام نمی‌شود
            if should_enter and entry_price > 0 and equality_required:
                price_gap = abs(current_close - entry_price) / entry_price
                if price_gap > ENTRY_MATCH_TOL:
                    should_enter = False

            if should_enter:
                # ---------- مدیریت سرمایه (فعلاً غیرفعال) ----------
                cap_size = None
                if CAPITAL_MANAGEMENT_ENABLED:
                    cap_ok, cap_reason, cap_size = capital_check(
                        symbol, entry_price, trades, leverage=cat_info.get('leverage', 7))
                    if not cap_ok:
                        continue

                new_trade = {
                    'symbol': symbol,
                    'category_id': cat_id,
                    # در پشتبند، کف/سقف/رشد همان معاملهٔ اول زنجیره حفظ می‌شود
                    'growth': (cascade_src.get('growth', growth) if cascade_src else growth),
                    'low': (cascade_src.get('low', low_24h) if cascade_src else low_24h),
                    'high': (cascade_src.get('high', high_24h) if cascade_src else high_24h),
                    'leg': ('tp' if cascade_src else None),
                    'entry': entry_price,
                    'tp': tp_price,
                    'stop': stop_price,
                    'neg_pct': neg_pct,
                    'status': 'OPEN',
                    'open_time': today_str,
                    'open_timestamp': int(current_ts),
                    'open_date_str': current_date_str,
                    'close_time': '',
                    'close_price': 0.0,
                    'pnl': 0.0,
                    'leverage': (4 if (equality_required and growth >= 100) else cat_info.get('leverage', 7))
                }
                trades.append(new_trade)

                # اگر این ورود بعد از پایانِ قفل ۲۴ ساعتهٔ استاپ باشد → علامت z در پیام
                if coin_is_z(trades[:-1], symbol, current_ts, today_str):
                    new_trade['release_entry'] = True

                # اطلاعات حجم پیشنهادی مدیریت سرمایه (فقط اگر فعال باشد)
                if CAPITAL_MANAGEMENT_ENABLED and cap_size:
                    new_trade['cap_contracts'] = cap_size['contracts']
                    new_trade['cap_margin'] = round(cap_size['margin_used'], 4)
                    new_trade['cap_notional'] = round(cap_size['notional'], 4)
                
                cat_entry_count = len([t for t in trades if t.get('category_id') == cat_id and (t.get('open_time') or '').replace(' ', '/') == today_str.replace(' ', '/')])
                global_entry_count = len([
                    t for t in trades 
                    if (t.get('open_time') or '').replace(' ', '/') == today_str.replace(' ', '/')
                ])
                new_trade['cat_entry_num'] = cat_entry_count
                new_trade['global_entry_num'] = global_entry_count
                
                coin_num = get_coin_day_number(trades, new_trade, today_str)
                release_flag = bool(new_trade.get('release_entry'))
                
                msg_main = generate_entry_message(
                    trade_type, symbol, entry_level_cat_name(entry_price, low_24h, cat_id), growth, neg_pct, low_24h, high_24h, 
                    entry_price, tp_price, stop_price, vol_str, current_date_str,
                    coin_num=coin_num, daily_count=global_entry_count, release_flag=release_flag
                )
                
                msg_cat = generate_entry_message(
                    trade_type, symbol, entry_level_cat_name(entry_price, low_24h, cat_id), growth, neg_pct, low_24h, high_24h, 
                    entry_price, tp_price, stop_price, vol_str, current_date_str,
                    coin_num=coin_num, daily_count=global_entry_count, release_flag=release_flag
                )
                
                bot_token = SELL_BOT_TOKEN if trade_type == 'short' else BUY_BOT_TOKEN
                
                send_telegram_message(bot_token, [PERSONAL_ID, cat_info['entry_channel']], msg_main)
                send_telegram_message(bot_token, [cat_info['report_channel']], msg_cat)
                
                if cat_id == '100_plus':
                    has_open_100_plus = True
                else:
                    has_open_sub_cat = True
                    break
                    
    app_data['trades'] = trades
    return app_data

def shamsi_days_back(date_str, n):
    """تاریخ شمسی n روز قبل از date_str (فرمت 1405/07/29)"""
    try:
        y, m, d = [int(x) for x in date_str.split('/')]
        return (jdatetime.date(y, m, d) - timedelta(days=n)).strftime('%Y/%m/%d')
    except Exception:
        return ''


def pnl_word(value):
    """متن سود/ضرر: سود +75 %  یا  ضرر -150 %"""
    iv = int(value)
    if iv > 0:
        return f"سود +{iv} %"
    if iv < 0:
        return f"ضرر {iv} %"
    return "0 %"


def cat_display_name(cat_id):
    """نام فارسی دسته‌بندی برای گزارش (مثل: 40 50 ٪)"""
    c_name = CATEGORIES[cat_id]['name_fa'].replace('+', '').replace('الی', ' ').strip()
    c_name = " ".join(c_name.split()).replace('%', '٪')
    if '٪' not in c_name:
        c_name = f"{c_name} ٪"
    return c_name


def build_counts_totals(cat_stats, week=False):
    """بخش جمع کل: تعداد تمامی معاملات + tp + stop + open + بازهای روزهای گذشته"""
    def open_count(st):
        return st['opening'] if week else st.get('opening_today', st['opening'])

    def open_pnl_of(st):
        return st['open_pnl'] if week else st.get('open_pnl_today', st['open_pnl'])

    total_all = sum(s['tp'] + s['stop'] + open_count(s) for s in cat_stats.values())
    if total_all <= 0:
        return ''

    sum_tp = sum(s['tp'] for s in cat_stats.values())
    sum_stop = sum(s['stop'] for s in cat_stats.values())
    sum_open = sum(open_count(s) for s in cat_stats.values())
    sum_open_pnl = sum(open_pnl_of(s) for s in cat_stats.values())

    label = ' هفته' if week else ''
    out = ''
    if week:
        out += f"محاسبات معاملات این هفته {pnl_word((sum_tp - sum_stop) * 100)}\n"
    out += f"تعداد تمامی معاملات{label} {total_all}\n"
    out += f"tp {sum_tp}\n"
    out += f"stop {sum_stop}\n"
    out += f"open {sum_open} {pnl_word(sum_open_pnl)}\n"

    # معاملات باز مانده از روزهای گذشته (جمع تمام دسته‌بندی‌ها)
    if not week:
        past_count = sum(s.get('opening_past', 0) for s in cat_stats.values())
        if past_count > 0:
            past_pnl = sum(s.get('open_pnl_past', 0.0) for s in cat_stats.values())
            past_line = f"opening روزهای گذشته : {past_count} {pnl_word(past_pnl)}"

            oldest_candidates = [(s.get('oldest_open_date'), s.get('oldest_open_ts') or 0)
                                 for s in cat_stats.values() if s.get('oldest_open_date')]
            if oldest_candidates:
                oldest_candidates.sort(key=lambda x: x[0])
                oldest_date, oldest_ts = oldest_candidates[0]
                past_line += f" قدیمی ترین {oldest_date.replace('/', ' ')}"
                if oldest_ts:
                    elapsed_days = int((iran_time.timestamp() - oldest_ts) / 86400)
                    if elapsed_days < 0:
                        elapsed_days = 0
                    past_line += f" مدت {elapsed_days} روز"

            out += past_line + "\n"

    return out


def build_counts_categories(cat_stats, week=False):
    """بخش دسته‌بندی‌ها: tp / stop / open هر دسته از بیشترین به کمترین"""
    def open_count(st):
        return st['opening'] if week else st.get('opening_today', st['opening'])

    ranked = [(cid, st) for cid, st in cat_stats.items()
              if (st['tp'] + st['stop'] + open_count(st)) > 0]
    ranked.sort(key=lambda x: (x[1]['tp'] + x[1]['stop'] + open_count(x[1])), reverse=True)

    out = ''
    for cat_id, st in ranked:
        line = f"دسته بندی {cat_display_name(cat_id)} tp {st['tp']} stop {st['stop']} open {open_count(st)}"
        if week:
            line += f" {pnl_word((st['tp'] - st['stop']) * 100)}"
        out += line + "\n"

    return out


def build_counts_block(cat_stats, week=False):
    """بخش تعداد معاملات (جمع کل + دسته‌بندی‌ها) — برای گزارش هفتگی"""
    return build_counts_totals(cat_stats, week) + build_counts_categories(cat_stats, week)


def generate_and_send_daily_report(app_data, target_date=None):
    if not target_date:
        target_date = today_str
    trades = app_data.get('trades', [])
    # گزارش از لحظهٔ شروع تازه (اگر ثبت شده باشد) — قبل از آن شمرده نمی‌شود
    report_start_ts = int(app_data.get('report_start_ts') or 0)
    
    cat_stats = {cat: {'tp': 0, 'stop': 0, 'opening': 0, 'opening_today': 0, 'opening_past': 0, 'closed_pnl': 0.0, 'open_pnl': 0.0, 'open_pnl_today': 0.0, 'open_pnl_past': 0.0, 'oldest_open_date': None, 'oldest_open_ts': 0, 'closed_strings': [], 'open_strings': [], 'excel': []} for cat in CATEGORIES.keys()}
    all_excel_data = []

    for t in trades:
        cat_id = t.get('category_id', '20_30')
        if cat_id not in cat_stats:
            cat_id = '20_30'
            
        name = clean_symbol(t['symbol']).lower()
        stats = cat_stats[cat_id]
        
        if t['status'] == 'OPEN':
            # ارزی که قیمت ندارد (حذف یا متوقف شده) از گزارش حذف می‌شود و ربات هم کرش نمی‌کند
            try:
                df = get_candles(t['symbol'], resolution=60, num_candles=1)
                current_close = float(df['close'].iloc[-1]) if (df is not None and len(df) > 0) else None
            except Exception:
                current_close = None
            if not current_close or current_close <= 0:
                continue

            stats['opening'] += 1
            is_today = (t.get('open_time') == target_date)
            if is_today:
                stats['opening_today'] += 1
            else:
                stats['opening_past'] += 1
                open_ts = int(t.get('open_timestamp') or 0)
                if not stats['oldest_open_date'] or (open_ts and open_ts < stats['oldest_open_ts']):
                    stats['oldest_open_date'] = t.get('open_time')
                    stats['oldest_open_ts'] = open_ts

            cat_info = CATEGORIES.get(cat_id, CATEGORIES['20_30'])
            trade_type = cat_info.get('trade_type', 'short')
            
            t_lev = t.get('leverage') or cat_info.get('leverage', 7)
            if trade_type == 'short':
                live_pnl = calculate_short_pnl(t['entry'], current_close, leverage=t_lev)
            else:
                live_pnl = calculate_long_pnl(t['entry'], current_close, leverage=t_lev)
                
            stats['open_pnl'] += live_pnl
            if is_today:
                stats['open_pnl_today'] += live_pnl
            else:
                stats['open_pnl_past'] += live_pnl

            live_int = int(live_pnl)
            pnl_str = f"+{live_int} %" if live_int > 0 else f"{live_int} %"
            stats['open_strings'].append(f"{name} : opening {pnl_str}")
            
            row = {'دسته': CATEGORIES[cat_id]['name_fa'], 'وضعیت عرض': 'opening', 'نام': name, 'کمترین قیمت': t['low'], 'بیشترین قیمت': t['high'], 'قیمت باز شدن معامله': t['entry'], 'قیمت بسته شدن': current_close}
            stats['excel'].append(row)
            all_excel_data.append(row)
            
        elif t['status'] in ['tp', 'stop']:
            close_ts_d = float(t.get('close_timestamp') or 0)
            if t.get('close_time') == target_date and close_ts_d >= report_start_ts:
                # سود/ضرر رُند: هر tp = +۱۰۰٪ و هر stop = -۱۰۰٪
                trade_pnl = 100.0 if t['status'] == 'tp' else -100.0
                stats['closed_pnl'] += trade_pnl
                pnl_int = int(trade_pnl)
                pnl_str = f"+{pnl_int} %" if pnl_int > 0 else f"{pnl_int} %"
                
                if t['status'] == 'tp':
                    stats['tp'] += 1
                    stats['closed_strings'].append(f"{name} tp {pnl_str}")
                else:
                    stats['stop'] += 1
                    stats['closed_strings'].append(f"{name} stop {pnl_str}")
            
            row = {'دسته': CATEGORIES[cat_id]['name_fa'], 'وضعیت عرض': t['status'], 'نام': name, 'کمترین قیمت': t['low'], 'بیشترین قیمت': t['high'], 'قیمت باز شدن معامله': t['entry'], 'قیمت بسته شدن': t['close_price']}
            stats['excel'].append(row)
            all_excel_data.append(row)

    total_all_transactions = 0

    # ---------- محاسبات از دو روز پیش تا امروز ----------
    hist_start_date = shamsi_days_back(target_date, 2)
    cat_closed_history = {cat: {'pnl': 0.0, 'count': 0} for cat in CATEGORIES.keys()}

    for t in trades:
        if t.get('status') not in ('tp', 'stop'):
            continue
        cid = t.get('category_id', '20_30')
        if cid not in cat_closed_history:
            cid = '20_30'
        close_time = t.get('close_time') or ''
        if not close_time or not hist_start_date:
            continue
        # معاملات قبل از شروع تازه در گزارش شمرده نمی‌شوند
        if float(t.get('close_timestamp') or 0) < report_start_ts:
            continue
        if close_time < hist_start_date or close_time > target_date:
            continue
        hist = cat_closed_history[cid]
        hist['pnl'] += 100.0 if t['status'] == 'tp' else -100.0
        hist['count'] += 1

    for cat_id, stats in cat_stats.items():
        total = stats['tp'] + stats['stop'] + stats['opening']
        total_all_transactions += total

        cat_info = CATEGORIES[cat_id]
        report_date_str = f"{target_date.replace('/', ' ')} ساعت {time_str} دقیقه"

        # دسته‌ای که هیچ معامله‌ای نداشته، هیچ خروجی‌ای نمی‌فرستد
        if total == 0:
            continue
        if not cat_info.get('enabled', True):
            continue

        closed_pnl_str_with_word = pnl_word(stats['closed_pnl'])
        open_pnl_word = pnl_word(stats['open_pnl'])

        total_today_trades = stats['tp'] + stats['stop'] + stats['opening_today']

        msg = f"گزارش روز\nمیزان رشد مثبت {cat_info['name_fa'].replace('+','')}\n"
        msg += f"محاسبات معاملات بسته شده امروز : {closed_pnl_str_with_word}\n"
        if stats['opening_today'] > 0:
            msg += f"محاسبات معاملات باز امروز : {pnl_word(stats['open_pnl_today'])}\n"
        else:
            msg += "محاسبات معاملات باز امروز : 0 \n"
        msg += f"تعداد معاملات : {total_today_trades}\n"
        msg += f"tp : {stats['tp']}\n"
        msg += f"stop : {stats['stop']}\n"
        msg += f"opening امروز : {stats['opening_today']}"
        if stats['opening_today'] > 0:
            msg += f" {pnl_word(stats['open_pnl_today'])}"
        msg += "\n"
        if stats['opening_past'] > 0:
            past_open_line = f"opening روزهای گذشته : {stats['opening_past']} {pnl_word(stats['open_pnl_past'])}"
            if stats.get('oldest_open_date'):
                past_open_line += f" تاریخ قدیمیترین {stats['oldest_open_date'].replace('/', ' ')}"
            oldest_ts = stats.get('oldest_open_ts') or 0
            if oldest_ts:
                elapsed_days = int((iran_time.timestamp() - oldest_ts) / 86400)
                if elapsed_days < 0:
                    elapsed_days = 0
                past_open_line += f" مدت {elapsed_days} روز"
            msg += past_open_line + "\n"
        else:
            msg += "opening روزهای گذشته : 0\n"

        # ---------- جمع سود/ضرر از دو روز پیش تا امروز ----------
        hist = cat_closed_history.get(cat_id, {})
        if hist.get('count', 0) > 0:
            days_count = 3
            try:
                y1, m1, d1 = [int(x) for x in hist_start_date.split('/')]
                y2, m2, d2 = [int(x) for x in target_date.split('/')]
                days_count = (jdatetime.date(y2, m2, d2) - jdatetime.date(y1, m1, d1)).days + 1
            except Exception:
                days_count = 3
            msg += (f"محاسبات معاملات روزهای گذشته از {hist_start_date.replace('/', ' ')} تا امروز "
                    f"مدت {days_count} روز : {pnl_word(hist['pnl'])}\n")

        msg += "نام عرض معاملات بسته و باز همراه سود یا ضرر\n"
        
        for i, s in enumerate(stats['closed_strings'] + stats['open_strings']):
            msg += f"{i+1} {s}\n"

        msg += f"\nتاریخ\n{report_date_str}"

        chats = [PERSONAL_ID, CHANNEL_REPORT_MAIN, cat_info['report_channel']]
        send_telegram_message(REPORT_BOT_TOKEN, chats, msg)


    # خروجی جمع‌بندی روزانه: محاسبات امروز + بیشترین سوددهی + تعداد معاملات
    active_ranking = []
    for cat_id, stats in cat_stats.items():
        if (stats['tp'] + stats['stop']) > 0 or stats['closed_pnl'] != 0:
            active_ranking.append((cat_id, stats))

    # اگر معامله بسته‌شده‌ای نبود، دسته‌های فعال را بر اساس معاملات باز قرار بده
    if not active_ranking:
        for cat_id, stats in cat_stats.items():
            if stats['opening'] > 0:
                active_ranking.append((cat_id, stats))

    total_all_trades = sum(s['tp'] + s['stop'] + s['opening'] for s in cat_stats.values())

    if active_ranking or total_all_trades > 0:
        # جمع سود/ضرر تمام معاملات بسته‌شدهٔ امروز در همهٔ دسته‌ها
        total_today_pnl = sum(s['closed_pnl'] for s in cat_stats.values())
        tt = int(total_today_pnl)
        if tt > 0:
            total_today_str = f"سود +{tt} ٪"
        elif tt < 0:
            total_today_str = f"ضرر {tt} ٪"
        else:
            total_today_str = "0 ٪"

        msg_rank = f"محاسبات معاملات امروز {total_today_str}\n"
        msg_rank += build_counts_totals(cat_stats)

        if active_ranking:
            active_ranking.sort(key=lambda x: x[1]['closed_pnl'], reverse=True)
            msg_rank += "بیشترین سوددهی :\n"
            for cat_id, stats in active_ranking:
                pnl_val = round(stats['closed_pnl'], 2)
                if pnl_val.is_integer():
                    pnl_str = f"+{int(pnl_val)} ٪" if pnl_val > 0 else f"{int(pnl_val)} ٪"
                else:
                    pnl_str = f"+{pnl_val:.2f} ٪" if pnl_val > 0 else f"{pnl_val:.2f} ٪"

                msg_rank += f"دسته بندی {cat_display_name(cat_id)} {pnl_str}\n"

        msg_rank += build_counts_categories(cat_stats)

        report_date_str = f"{target_date.replace('/', ' ')} ساعت {time_str} دقیقه"
        msg_rank += f"\nتاریخ {report_date_str}"

        send_telegram_message(REPORT_BOT_TOKEN, [CHANNEL_REPORT_MAIN], msg_rank)

    # ارسال فایل اکسل طبق درخواست غیرفعال شد
    return

def generate_and_send_weekly_report(app_data):
    trades = app_data.get('trades', [])
    current_ts = iran_time.timestamp()
    seven_days_ago_ts = current_ts - (7 * 86400)
    # گزارش از لحظهٔ شروع تازه (اگر ثبت شده باشد)
    report_start_ts = int(app_data.get('report_start_ts') or 0)
    
    cat_stats = {cat: {'tp': 0, 'stop': 0, 'opening': 0, 'closed_pnl': 0.0, 'open_pnl': 0.0, 'strings': []} for cat in CATEGORIES.keys()}

    for t in trades:
        cat_id = t.get('category_id', '20_30')
        if cat_id not in cat_stats:
            cat_id = '20_30'
            
        name = clean_symbol(t['symbol']).lower()
        stats = cat_stats[cat_id]
        
        if t['status'] == 'OPEN':
            # ارزی که قیمت ندارد (حذف یا متوقف شده) از گزارش حذف می‌شود
            try:
                df = get_candles(t['symbol'], resolution=60, num_candles=1)
                current_close = float(df['close'].iloc[-1]) if (df is not None and len(df) > 0) else None
            except Exception:
                current_close = None
            if not current_close or current_close <= 0:
                continue

            stats['opening'] += 1

            cat_info = CATEGORIES.get(cat_id, CATEGORIES['20_30'])
            trade_type = cat_info.get('trade_type', 'short')
            
            t_lev = t.get('leverage') or cat_info.get('leverage', 7)
            if trade_type == 'short':
                live_pnl = calculate_short_pnl(t['entry'], current_close, leverage=t_lev)
            else:
                live_pnl = calculate_long_pnl(t['entry'], current_close, leverage=t_lev)
                
            stats['open_pnl'] += live_pnl
            pnl_str = f"+{live_pnl:.2f} %" if live_pnl > 0 else f"{live_pnl:.2f} %"
            stats['strings'].append(f"{name} : opening {pnl_str}")
            
        elif t['status'] in ['tp', 'stop']:
            close_ts = float(t.get('close_timestamp') or 0)
            if close_ts >= seven_days_ago_ts and close_ts >= report_start_ts:
                # مثل گزارش روز: هر tp = +۱۰۰٪ و هر stop = -۱۰۰٪
                trade_pnl = 100.0 if t['status'] == 'tp' else -100.0
                stats['closed_pnl'] += trade_pnl
                pnl_int = int(trade_pnl)
                pnl_str = f"+{pnl_int} %" if pnl_int > 0 else f"{pnl_int} %"
                
                if t['status'] == 'tp':
                    stats['tp'] += 1
                    stats['strings'].append(f"{name} tp {pnl_str}")
                else:
                    stats['stop'] += 1
                    stats['strings'].append(f"{name} stop {pnl_str}")

    # جمع‌بندی هفتگی در ابتدای گزارش: محاسبات کل، تعدادها و دسته‌بندی‌ها
    weekly_counts = build_counts_block(cat_stats, week=True)
    if weekly_counts:
        weekly_counts += f"\nتاریخ {today_str.replace('/', ' ')}"
        send_telegram_message(WEEKLY_REPORT_BOT_TOKEN, [PERSONAL_ID, CHANNEL_WEEKLY_REPORT], weekly_counts)

    total_all_transactions = 0
    for cat_id, stats in cat_stats.items():
        total = stats['tp'] + stats['stop'] + stats['opening']
        total_all_transactions += total
        
        if total == 0:
            continue
            
        cat_info = CATEGORIES[cat_id]
        closed_pnl_str = f"+{int(stats['closed_pnl'])} %" if stats['closed_pnl'] > 0 else f"{int(stats['closed_pnl'])} %"
        open_pnl_str = f"+{stats['open_pnl']:.2f} %" if stats['open_pnl'] > 0 else f"{stats['open_pnl']:.2f} %"

        msg = f"گزارش هفتگی\nمیزان رشد مثبت {cat_info['name_fa'].replace('+','')}\n"
        msg += f"2 تعداد معاملات هفته : {total}\n"
        msg += f"2 1 تعداد tp : {stats['tp']}\n"
        msg += f"2 2 تعداد stop : {stats['stop']}\n"
        msg += f"2 3 تعداد opening : {stats['opening']}\n"
        msg += f"3 میزان سود یا ضرر تمامی معاملات بسته شده هفته : {closed_pnl_str}\n"
        msg += f"4 میزان سود یا ضرر تمامی معاملات باز {open_pnl_str}\n"
        msg += "5 نام عرض معاملات بسته و باز همراه سود یا ضرر\n"
        
        for i, s in enumerate(stats['strings']):
            msg += f"{i+1} {s}\n"
            
        msg += f"\n6 تاریخ\n{current_date_str}"

        chats = [PERSONAL_ID, CHANNEL_WEEKLY_REPORT, cat_info['report_channel']]
        send_telegram_message(WEEKLY_REPORT_BOT_TOKEN, chats, msg)

    if total_all_transactions == 0:
        msg = f"گزارش هفتگی\nتعداد معاملات هفته 0\nتاریخ {current_date_str}"
        chats = [PERSONAL_ID, CHANNEL_WEEKLY_REPORT]
        for c in CATEGORIES.values():
            chats.append(c['report_channel'])
        chats = list(set(chats))
        send_telegram_message(WEEKLY_REPORT_BOT_TOKEN, chats, msg)

if __name__ == '__main__':
    app_data = load_data()

    # شروع تازه (درخواست کاربر): معاملات باز حذف می‌شوند و گزارش‌ها از این لحظه صفر می‌شوند
    # (معاملات بسته‌شده می‌مانند تا قفل‌های tp/stop و قوانین دست‌نخورده بمانند)
    if RESET_REPORTS_ONCE and not app_data.get('report_start_ts'):
        trades = app_data.get('trades') or []
        kept = [t for t in trades if str(t.get('status')) != 'OPEN']
        removed = len(trades) - len(kept)
        app_data['trades'] = kept
        app_data['report_start_ts'] = int(iran_time.timestamp())
        save_data(app_data)
        print(f"open trades removed: {removed} | reports start now")

    # حذف یک‌بارهٔ معاملهٔ بازِ اشتباه (دستور کاربر): فقط همان معامله، بدون اثر روی بقیه
    try:
        app_data['trades'] = remove_bad_open_trades(app_data.get('trades', []))
    except Exception as e:
        print(f"purge error: {e}")

    try:
        app_data = process_markets(app_data)

        # گزارش روزانه هر شب راس ساعت ۱۲:۰۰ (۰۰:۰۰ نیمه‌شب)
        # تاریخ گزارش دقیقاً کل معاملات ۲۴ ساعته روز گذشته است (از ۰۰:۰۰ تا ۲۳:۵۹)
        if iran_time.hour == 0:
            target_date = jdatetime.datetime.fromgregorian(datetime=iran_time - timedelta(hours=1)).strftime('%Y/%m/%d')
            if app_data.get('last_report_date') != target_date:
                generate_and_send_daily_report(app_data, target_date=target_date)
                app_data['last_report_date'] = target_date

            # گزارش هفتگی بامداد شنبه ساعت ۰۰:۰۰ (پایان هفته جمعه)
            j_now = jdatetime.datetime.fromgregorian(datetime=iran_time)
            if j_now.weekday() == 0: # شنبه بامداد
                if app_data.get('last_weekly_report_date') != target_date:
                    generate_and_send_weekly_report(app_data)
                    app_data['last_weekly_report_date'] = target_date
    finally:
        # ذخیره‌ی نهایی — حتی اگر وسط اجرا خطایی پیش بیاید.
        # دلیل: پیام خروج/ورود *قبل* از ذخیره ارسال می‌شود؛ پس اگر اجرا نیمه‌کاره بمیرد،
        # اجرای بعدی همان معامله را «باز» می‌بیند و همان پیام را دوباره می‌فرستد.
        save_data(app_data)
