import json
import os
import math
import requests
import pandas as pd
import jdatetime
from datetime import datetime, timedelta
import warnings

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
        "leverage": 7
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
        "leverage": 7
    }
}

TRADES_FILE = "trades.json"
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

def calculate_short_pnl(entry, exit_price, leverage=7):
    pnl = ((entry - exit_price) / entry) * 100 * leverage
    return round(pnl, 2)

def calculate_long_pnl(entry, exit_price, leverage=7):
    pnl = ((exit_price - entry) / entry) * 100 * leverage
    return round(pnl, 2)

def generate_entry_message(trade_type, symbol, cat_name, growth, neg_percent, low, high, entry, tp, stop, vol, date_str, daily_count):
    name = clean_symbol(symbol).lower()
    type_str = "فروش" if trade_type == 'short' else "خرید"
    return (
        f"{daily_count} {type_str}\n"
        f"نام: {name}\n"
        f"دسته بندی رشد: {cat_name}\n"
        f"میزان رشد: +{growth:.2f} %\n"
        f"درصد منفی: -{neg_percent} %\n"
        f"Entri: {fmt_price(entry)}\n"
        f"tp: {fmt_price(tp)}\n"
        f"stop: {fmt_price(stop)}\n"
        f"حجم: {vol}\n"
        f"low: {fmt_price(low)}\n"
        f"hi: {fmt_price(high)}\n"
        f"تاریخ: {date_str}"
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

def generate_exit_message(exit_type, symbol, cat_name, growth, neg_percent, low, high, entry, tp, stop, vol, start_date_str, end_date_str, duration_str, daily_count, trade_type):
    name = clean_symbol(symbol).lower()
    trade_name = "فروش" if trade_type == 'short' else "خرید"
    status_fa = f"{trade_name} {exit_type}"
    if daily_count:
        msg = f"{daily_count} {status_fa}\n"
    else:
        msg = f"{status_fa}\n"
    msg += f"نام: {name}\n"
    msg += f"دسته بندی رشد: {cat_name}\n"
    msg += f"میزان رشد: +{growth:.2f} %\n"
    msg += f"درصد منفی: -{neg_percent} %\n"
    msg += f"Entri: {fmt_price(entry)}\n"
    if exit_type == "tp":
        msg += f"tp: {fmt_price(tp)}\n"
    else:
        msg += f"stop: {fmt_price(stop)}\n"
    msg += f"حجم: {vol}\n"
    msg += f"low: {fmt_price(low)}\n"
    msg += f"hi: {fmt_price(high)}\n"
    msg += f"زمان شروع: {start_date_str}\n"
    msg += f"زمان پایان: {end_date_str}\n"
    msg += f"زمان سپری شده: {duration_str}"
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

def process_markets(app_data):
    trades = app_data.get('trades', [])
    market_overview = get_market_overview()
    market_trend = get_overall_market_trend(market_overview)
    symbols = list(market_overview.keys())
    
    current_ts = iran_time.timestamp()
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
                    
            if exit_type:
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
                
                exit_label_cat = f"{entry_num_cat} 1"
                
                msg_main = generate_exit_message(
                    exit_type, symbol, cat_info['name_fa'], trade['growth'], neg_pct, 
                    trade['low'], trade['high'], trade['entry'], trade['tp'], trade['stop'], 
                    vol_str, start_date_str, end_date_str, duration_str, exit_label_global, trade_type
                )
                
                msg_cat = generate_exit_message(
                    exit_type, symbol, cat_info['name_fa'], trade['growth'], neg_pct, 
                    trade['low'], trade['high'], trade['entry'], trade['tp'], trade['stop'], 
                    vol_str, start_date_str, end_date_str, duration_str, exit_label_cat, trade_type
                )
                
                send_telegram_message(get_exit_token(), [PERSONAL_ID, CHANNEL_EXIT_MAIN], msg_main)
                send_telegram_message(get_exit_token(), [cat_info['report_channel']], msg_cat)

                # اگر خروج با TP بود و معامله short در دسته‌های زیر ۱۰۰ درصد بود:
                # سریعاً همان لحظه (پشتبندش) معامله دسته بعدی باز شود
                if exit_type == 'tp' and trade_type == 'short' and cat_id != '100_plus':
                    cat_order = ["100_plus", "90_100", "80_90", "70_80", "60_70", "50_60", "40_50", "30_40", "20_30"]
                    if cat_id in cat_order:
                        curr_idx = cat_order.index(cat_id)
                        next_idx = curr_idx + 1
                        if next_idx < len(cat_order):
                            next_cat_id = cat_order[next_idx]
                            
                            # بررسی اینکه دسته بعدی در ۲۴ ساعت گذشته یا امروز معامله نشده باشد
                            next_already_traded = any(
                                t.get('symbol', '').upper() == symbol.upper()
                                and t.get('category_id') == next_cat_id
                                and t.get('status') == 'OPEN'
                                for t in trades
                            )
                            
                            if not next_already_traded:
                                next_cat_info = CATEGORIES[next_cat_id]
                                next_entry = exit_price  # نقطه ورود = تی‌پی معامله قبلی
                                next_tp = round_price(next_entry * (1 - 0.15))
                                next_stop = round_price(next_entry * (1 + 0.14))
                                next_neg_pct = 15
                                
                                cascade_trade = {
                                    'symbol': symbol,
                                    'category_id': next_cat_id,
                                    'growth': trade.get('growth', growth),
                                    'low': low_24h,
                                    'high': high_24h,
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
                                    'leverage': next_cat_info.get('leverage', 7)
                                }
                                trades.append(cascade_trade)
                                
                                cat_entry_count = len([t for t in trades if t.get('category_id') == next_cat_id and t.get('open_time') == today_str])
                                global_entry_count = len([
                                    t for t in trades 
                                    if t.get('open_time') == today_str 
                                    and CATEGORIES.get(t.get('category_id', '20_30'), {}).get('trade_type', 'short') == 'short'
                                ])
                                cascade_trade['cat_entry_num'] = cat_entry_count
                                cascade_trade['global_entry_num'] = global_entry_count
                                
                                c_msg_main = generate_entry_message(
                                    'short', symbol, next_cat_info['name_fa'], cascade_trade['growth'], next_neg_pct,
                                    low_24h, high_24h, next_entry, next_tp, next_stop, vol_str, current_date_str, global_entry_count
                                )
                                c_msg_cat = generate_entry_message(
                                    'short', symbol, next_cat_info['name_fa'], cascade_trade['growth'], next_neg_pct,
                                    low_24h, high_24h, next_entry, next_tp, next_stop, vol_str, current_date_str, f"{cat_entry_count} 1"
                                )
                                
                                send_telegram_message(SELL_BOT_TOKEN, [PERSONAL_ID, next_cat_info['entry_channel']], c_msg_main)
                                send_telegram_message(SELL_BOT_TOKEN, [next_cat_info['report_channel']], c_msg_cat)

        # بررسی وضعیت معاملات برای این ارز:
        # ۱. اگر این ارز در ۲۴ ساعت گذشته یا امروز استاپ خورده باشد، تا ۲۴ ساعت در هیچ دسته‌ای معامله نمی‌شود
        symbol_has_stop_cooldown = False
        for t in trades:
            if t.get('symbol', '').upper() == symbol.upper() and str(t.get('status', '')).lower() == 'stop':
                stop_ts = 0.0
                try:
                    stop_ts = float(t.get('close_timestamp') or t.get('open_timestamp') or 0)
                except Exception:
                    stop_ts = 0.0
                if (current_ts - stop_ts) < (24 * 3600) or t.get('close_time') == today_str:
                    symbol_has_stop_cooldown = True
                    break

        if symbol_has_stop_cooldown:
            continue

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
            # ۲. فقط اگر همین دسته در همین لحظه معامله‌ی باز داشته باشد، دوباره باز نمی‌شود.
            #    کول‌داون استاپ (کل ارز، ۲۴ ساعت) در بالای همین حلقه اعمال می‌شود.
            #    تی‌پی هیچ بلاکی ایجاد نمی‌کند و دسته بلافاصله بعد از تی‌پی آزاد است.
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
                        else:
                            # دسته‌های زیر ۱۰۰ درصد برای ارز با رشد بالای ۱۰۰:
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

                            if not prev_sub_trades:
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
                                entry_price = round_price(low_24h * target_ratio * (1 - 0.15))
                                tp_price = round_price(entry_price * (1 - 0.15))
                                stop_price = round_price(entry_price * (1 + 0.14))
                                neg_pct = 15
                                should_enter = (current_close <= entry_price and current_close > tp_price)
                            else:
                                # اگر قبلاً معامله آبشاری انجام شده و TP خورده باشد، معامله بعدی از طریق پشتبند TP باز می‌شود
                                last_sub = prev_sub_trades[-1]
                                if last_sub.get('status') == 'tp':
                                    last_cat_idx = cat_order.index(last_sub['category_id'])
                                    if current_cat_idx == last_cat_idx + 1:
                                        entry_price = round_price(float(last_sub['tp']))
                                        tp_price = round_price(entry_price * (1 - 0.15))
                                        stop_price = round_price(entry_price * (1 + 0.14))
                                        neg_pct = 15
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

                        if not prev_sub_trades:
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
                                last_cat_idx = cat_order.index(last_sub['category_id'])
                                if current_cat_idx == last_cat_idx + 1:
                                    entry_price = round_price(float(last_sub['tp']))
                                    tp_price = round_price(entry_price * (1 - 0.15))
                                    stop_price = round_price(entry_price * (1 + 0.14))
                                    neg_pct = 15
                                    should_enter = (current_close <= entry_price and current_close > tp_price)
                                else:
                                    continue
                            else:
                                continue
                else: # long
                    entry_price = round_price(high_24h * (1 - entry_drop))
                    tp_price = round_price(entry_price * (1 + cat_info['tp_rise']))
                    stop_price = round_price(entry_price * (1 - cat_info['stop_drop']))
                    neg_pct = round(cat_info['entry_drop'] * 100, 1) if (cat_info['entry_drop'] * 100) % 1 != 0 else int(cat_info['entry_drop'] * 100)
                    should_enter = (current_close >= entry_price and current_close < tp_price)
                
            if should_enter:
                new_trade = {
                    'symbol': symbol,
                    'category_id': cat_id,
                    'growth': growth,
                    'low': low_24h,
                    'high': high_24h,
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
                    'leverage': cat_info.get('leverage', 7)
                }
                trades.append(new_trade)
                
                cat_entry_count = len([t for t in trades if t.get('category_id') == cat_id and t.get('open_time') == today_str])
                global_entry_count = len([
                    t for t in trades 
                    if t.get('open_time') == today_str 
                    and CATEGORIES.get(t.get('category_id', '20_30'), {}).get('trade_type', 'short') == trade_type
                ])
                new_trade['cat_entry_num'] = cat_entry_count
                new_trade['global_entry_num'] = global_entry_count
                
                msg_main = generate_entry_message(
                    trade_type, symbol, cat_info['name_fa'], growth, neg_pct, low_24h, high_24h, 
                    entry_price, tp_price, stop_price, vol_str, current_date_str, global_entry_count
                )
                
                msg_cat = generate_entry_message(
                    trade_type, symbol, cat_info['name_fa'], growth, neg_pct, low_24h, high_24h, 
                    entry_price, tp_price, stop_price, vol_str, current_date_str, cat_entry_count
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

def generate_and_send_daily_report(app_data, target_date=None):
    if not target_date:
        target_date = today_str
    trades = app_data.get('trades', [])
    
    cat_stats = {cat: {'tp': 0, 'stop': 0, 'opening': 0, 'closed_pnl': 0.0, 'open_pnl': 0.0, 'strings': [], 'excel': []} for cat in CATEGORIES.keys()}
    all_excel_data = []

    for t in trades:
        cat_id = t.get('category_id', '20_30')
        if cat_id not in cat_stats:
            cat_id = '20_30'
            
        name = clean_symbol(t['symbol']).lower()
        stats = cat_stats[cat_id]
        
        if t['status'] == 'OPEN':
            stats['opening'] += 1
            df = get_candles(t['symbol'], resolution=60, num_candles=1)
            current_close = float(df['close'].iloc[-1]) if df is not None else t['entry']
            
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
            
            row = {'دسته': CATEGORIES[cat_id]['name_fa'], 'وضعیت عرض': 'opening', 'نام': name, 'کمترین قیمت': t['low'], 'بیشترین قیمت': t['high'], 'قیمت باز شدن معامله': t['entry'], 'قیمت بسته شدن': current_close}
            stats['excel'].append(row)
            all_excel_data.append(row)
            
        elif t['status'] in ['tp', 'stop']:
            if t.get('close_time') == target_date:
                stats['closed_pnl'] += t['pnl']
                pnl_str = f"+{t['pnl']:.2f} %" if t['pnl'] > 0 else f"{t['pnl']:.2f} %"
                
                if t['status'] == 'tp':
                    stats['tp'] += 1
                    stats['strings'].append(f"{name} tp {pnl_str}")
                else:
                    stats['stop'] += 1
                    stats['strings'].append(f"{name} stop {pnl_str}")
            
            row = {'دسته': CATEGORIES[cat_id]['name_fa'], 'وضعیت عرض': t['status'], 'نام': name, 'کمترین قیمت': t['low'], 'بیشترین قیمت': t['high'], 'قیمت باز شدن معامله': t['entry'], 'قیمت بسته شدن': t['close_price']}
            stats['excel'].append(row)
            all_excel_data.append(row)

    total_all_transactions = 0
    for cat_id, stats in cat_stats.items():
        total = stats['tp'] + stats['stop'] + stats['opening']
        total_all_transactions += total
        
        if total == 0:
            continue
            
        cat_info = CATEGORIES[cat_id]
        closed_pnl_str = f"+{stats['closed_pnl']:.2f} %" if stats['closed_pnl'] > 0 else f"{stats['closed_pnl']:.2f} %"
        open_pnl_str = f"+{stats['open_pnl']:.2f} %" if stats['open_pnl'] > 0 else f"{stats['open_pnl']:.2f} %"

        msg = f"گزارش روز\nمیزان رشد مثبت {cat_info['name_fa'].replace('+','')}\n"
        msg += f"2 تعداد معاملات : {total}\n"
        msg += f"2 1 تعداد tp : {stats['tp']}\n"
        msg += f"2 2 تعداد stop : {stats['stop']}\n"
        msg += f"2 3 تعداد opening : {stats['opening']}\n"
        msg += f"3 میزان سود یا ضرر تمامی معاملات بسته شده : {closed_pnl_str}\n"
        msg += f"4 میزان سود یا ضرر تمامی معاملات باز {open_pnl_str}\n"
        msg += "5 نام عرض معاملات بسته و باز همراه سود یا ضرر\n"
        
        for i, s in enumerate(stats['strings']):
            msg += f"{i+1} {s}\n"
            
        report_date_str = f"{target_date.replace('/', ' ')} ساعت {time_str} دقیقه"
        msg += f"\n6 تاریخ\n{report_date_str}"

        chats = [PERSONAL_ID, CHANNEL_REPORT_MAIN, cat_info['report_channel']]
        send_telegram_message(REPORT_BOT_TOKEN, chats, msg)

    if total_all_transactions == 0:
        report_date_str = f"{target_date.replace('/', ' ')} ساعت {time_str} دقیقه"
        msg = f"گزارش روز\nتعداد معاملات 0\nتاریخ {report_date_str}"
        chats = [PERSONAL_ID, CHANNEL_REPORT_MAIN]
        for c in CATEGORIES.values():
            chats.append(c['report_channel'])
        chats = list(set(chats))
        send_telegram_message(REPORT_BOT_TOKEN, chats, msg)
        return

    # خروجی مجزا: بیشترین سوددهی دسته‌بندی‌ها از بیشترین به کمترین
    active_ranking = []
    for cat_id, stats in cat_stats.items():
        if (stats['tp'] + stats['stop']) > 0 or stats['closed_pnl'] != 0:
            active_ranking.append((cat_id, stats))
            
    # اگر معامله بسته‌شده‌ای نبود، دسته‌های فعال را بر اساس معاملات باز قرار بده
    if not active_ranking:
        for cat_id, stats in cat_stats.items():
            if stats['opening'] > 0:
                active_ranking.append((cat_id, stats))

    if active_ranking:
        active_ranking.sort(key=lambda x: x[1]['closed_pnl'], reverse=True)
        msg_rank = "بیشترین سوددهی :\n"
        for cat_id, stats in active_ranking:
            c_info = CATEGORIES[cat_id]
            c_name = c_info['name_fa'].replace('+', '').replace('الی', ' ').strip()
            c_name = " ".join(c_name.split())
            c_name = c_name.replace('%', '٪')
            if '٪' not in c_name:
                c_name = f"{c_name} ٪"
                
            pnl_val = round(stats['closed_pnl'], 2)
            if pnl_val.is_integer():
                pnl_str = f"+{int(pnl_val)} ٪" if pnl_val > 0 else f"{int(pnl_val)} ٪"
            else:
                pnl_str = f"+{pnl_val:.2f} ٪" if pnl_val > 0 else f"{pnl_val:.2f} ٪"
                
            msg_rank += f"دسته بندی {c_name} {pnl_str}\n"
            
        report_date_str = f"{target_date.replace('/', ' ')} ساعت {time_str} دقیقه"
        msg_rank += f"\nتاریخ {report_date_str}"
        
        chats_rank = [CHANNEL_REPORT_MAIN]
        send_telegram_message(REPORT_BOT_TOKEN, chats_rank, msg_rank)

    # ارسال فایل اکسل طبق درخواست غیرفعال شد
    return

def generate_and_send_weekly_report(app_data):
    trades = app_data.get('trades', [])
    current_ts = iran_time.timestamp()
    seven_days_ago_ts = current_ts - (7 * 86400)
    
    cat_stats = {cat: {'tp': 0, 'stop': 0, 'opening': 0, 'closed_pnl': 0.0, 'open_pnl': 0.0, 'strings': []} for cat in CATEGORIES.keys()}

    for t in trades:
        cat_id = t.get('category_id', '20_30')
        if cat_id not in cat_stats:
            cat_id = '20_30'
            
        name = clean_symbol(t['symbol']).lower()
        stats = cat_stats[cat_id]
        
        if t['status'] == 'OPEN':
            stats['opening'] += 1
            df = get_candles(t['symbol'], resolution=60, num_candles=1)
            current_close = float(df['close'].iloc[-1]) if df is not None else t['entry']
            
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
            close_ts = t.get('close_timestamp', 0)
            if close_ts >= seven_days_ago_ts:
                stats['closed_pnl'] += t['pnl']
                pnl_str = f"+{t['pnl']:.2f} %" if t['pnl'] > 0 else f"{t['pnl']:.2f} %"
                
                if t['status'] == 'tp':
                    stats['tp'] += 1
                    stats['strings'].append(f"{name} tp {pnl_str}")
                else:
                    stats['stop'] += 1
                    stats['strings'].append(f"{name} stop {pnl_str}")

    total_all_transactions = 0
    for cat_id, stats in cat_stats.items():
        total = stats['tp'] + stats['stop'] + stats['opening']
        total_all_transactions += total
        
        if total == 0:
            continue
            
        cat_info = CATEGORIES[cat_id]
        closed_pnl_str = f"+{stats['closed_pnl']:.2f} %" if stats['closed_pnl'] > 0 else f"{stats['closed_pnl']:.2f} %"
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
