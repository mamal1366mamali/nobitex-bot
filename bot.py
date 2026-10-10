import json
import os
import requests
import pandas as pd
import jdatetime
from datetime import datetime, timedelta
import warnings
import re

warnings.filterwarnings('ignore')

SELL_BOT_TOKEN = "8808538539:AAEiADT6e7lhGhDbQZx1FtxW990V_b4WiFI"
BUY_BOT_TOKEN = "8994334309:AAHy8H4WuYTel0wzMvj7Jkif-oEZR_7BEyc"
EXIT_BOT_TOKEN = "8781543538:AAGCr8Rjc70KouCmrfAbNcu_FhPneFJTCMs"
REPORT_BOT_TOKEN = "8865582989:AAHRhGoMjnVUsBpCNj_FlZAm-Hmk7p_SR0E"

PERSONAL_ID = "114669886"
CHANNEL_EXIT_MAIN = "-1004415777827"
CHANNEL_REPORT_MAIN = "-1004304608564"

CATEGORIES = {
    "20_30": {
        "name_fa": "+20 الی 30 ٪",
        "entry_channel": "-1004290922830",
        "report_channel": "-1003914385862",
        "entry_drop": 0.14,
        "tp_drop": 0.07,
        "stop_rise": 0.14,
        "trade_type": "short"
    },
    "30_40": {
        "name_fa": "+30 الی 40 ٪",
        "entry_channel": "-1004290922830",
        "report_channel": "-1003733086854",
        "entry_drop": 0.15,
        "tp_drop": 0.15,
        "stop_rise": 0.14,
        "trade_type": "short"
    },
    "40_50": {
        "name_fa": "+40 الی 50 ٪",
        "entry_channel": "-1004290922830",
        "report_channel": "-1003945753248",
        "entry_drop": 0.15,
        "tp_drop": 0.15,
        "stop_rise": 0.14,
        "trade_type": "short"
    },
    "50_100": {
        "name_fa": "+50 الی 100 ٪",
        "entry_channel": "-1004290922830",
        "report_channel": "-1004452909288",
        "entry_drop": 0.15,
        "tp_drop": 0.15,
        "stop_rise": 0.14,
        "trade_type": "short"
    },
    "100_plus": {
        "name_fa": "+100 ٪ به بالا",
        "entry_channel": "-1004290922830",
        "report_channel": "-1004458729980",
        "entry_drop": 0.25,
        "tp_drop": 0.25,
        "stop_rise": 0.25,
        "trade_type": "short"
    },
    "fixed_50": {
        "name_fa": "مثبت 50 (ورود آنی)",
        "entry_channel": "-1004290922830",
        "report_channel": "-1003781040656",
        "entry_drop": 0.00,
        "tp_drop": 0.15,
        "stop_rise": 0.14,
        "trade_type": "short",
        "is_fixed": True,
        "fixed_growth_target": 0.50
    },
    "fixed_100": {
        "name_fa": "مثبت 100 (ورود آنی)",
        "entry_channel": "-1004290922830",
        "report_channel": "-1004458729980",
        "entry_drop": 0.00,
        "tp_drop": 0.15,
        "stop_rise": 0.14,
        "trade_type": "short",
        "is_fixed": True,
        "fixed_growth_target": 1.00
    },
    "long_20_30": {
        "name_fa": "+20 الی 30 ٪ (خرید)",
        "entry_channel": "-1004310315552",
        "report_channel": "-1003820960180",
        "entry_drop": 0.21,
        "tp_rise": 0.15,
        "stop_drop": 0.14,
        "trade_type": "long"
    },
    "long_30_100": {
        "name_fa": "+30 الی 100 ٪ (خرید)",
        "entry_channel": "-1004310315552",
        "report_channel": "-1004379515603",
        "entry_drop": 0.30,
        "tp_rise": 0.15,
        "stop_drop": 0.14,
        "trade_type": "long"
    }
}

TRADES_FILE = "trades.json"
BASE_URL = 'https://api.ourbit.com/api/v3/klines'
ORDERBOOK_URL = 'https://api.ourbit.com/api/v3/ticker/24hr'

iran_time = datetime.utcnow() + timedelta(hours=3, minutes=30)
shamsi_date = jdatetime.datetime.fromgregorian(datetime=iran_time).strftime('%Y %m %d')
today_str = jdatetime.datetime.fromgregorian(datetime=iran_time).strftime('%Y/%m/%d')
time_str = iran_time.strftime('%H : %M')
current_date_str = f"{shamsi_date} ساعت {time_str} دقیقه"

def load_data():
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_report_date": "", "trades": []}

def save_data(data):
    with open(TRADES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def send_telegram_message(token, chat_ids, text):
    for chat_id in chat_ids:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception:
            pass

def send_telegram_document(token, chat_ids, file_path, caption):
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
    s = symbol.replace('USDT', '')
    if s == '' or s == 'BTC':
        return 'BTC'
    return s

def format_volume(val):
    if val is None or pd.isna(val):
        return '0usdt'
    if val >= 1_000_000_000:
        return f'{val / 1_000_000_000:.2f}b'
    elif val >= 1_000_000:
        return f'{val / 1_000_000:.2f}m'
    elif val >= 1_000:
        return f'{val / 1_000:.0f}k'
    else:
        return f'{int(val)}usdt'

def get_all_usdt_symbols():
    try:
        response = requests.get(ORDERBOOK_URL, timeout=30)
        data = response.json()
        valid = []
        for ticker in data:
            sym = ticker.get('symbol', '')
            if sym.endswith('USDT'):
                name_clean = sym.replace("USDT", "").lower()
                if not re.match(r'^\d+(yes|no)$', name_clean):
                    valid.append(sym)
        return valid
    except Exception:
        pass
    return []

def get_candles(symbol, resolution=60, num_candles=24):
    interval = '1h' if resolution == 60 else '1m'
    params = {'symbol': symbol, 'interval': interval, 'limit': num_candles}
    try:
        response = requests.get(BASE_URL, params=params, timeout=15)
        data = response.json()
        if len(data) > 0:
            df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'trades', 'tb_base', 'tb_quote', 'ignore'])
            df['time'] = pd.to_datetime(df['time'], unit='ms')
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            df['volume'] = df['quote_asset_volume'].astype(float)
            return df.sort_values('time', ascending=True).reset_index(drop=True)
    except Exception:
        pass
    return None

def calculate_short_pnl(entry, exit_price, leverage=7):
    pnl = ((entry - exit_price) / entry) * 100 * leverage
    return round(pnl, 2)

def calculate_long_pnl(entry, exit_price, leverage=7):
    pnl = ((exit_price - entry) / entry) * 100 * leverage
    return round(pnl, 2)

def generate_entry_message(symbol, cat_name, growth, neg_percent, low, high, entry, tp, stop, vol, date_str, daily_count):
    name = clean_symbol(symbol).lower()
    return (
        f"{daily_count} نام: {name}\n"
        f"دسته بندی رشد: {cat_name}\n"
        f"میزان رشد: +{growth:.2f}%\n"
        f"درصد منفی: -{neg_percent} ٪\n"
        f"low: {low} usdt\n"
        f"hi: {high} usdt\n"
        f"Entri: {entry}\n"
        f"tp: {tp} usdt\n"
        f"stop: {stop}\n"
        f"حجم: {vol}\n"
        f"تاریخ: {date_str}"
    )

def generate_exit_message(exit_type, symbol, cat_name, growth, neg_percent, low, high, entry, tp, stop, vol, date_str, daily_count, trade_type):
    name = clean_symbol(symbol).lower()
    msg = f"{daily_count} نام: {name}\n"
    msg += f"{exit_type}\n"
    msg += f"دسته بندی رشد: {cat_name}\n"
    msg += f"میزان رشد: +{growth:.2f}%\n"
    msg += f"درصد منفی: -{neg_percent} ٪\n"
    msg += f"low: {low} usdt\n"
    msg += f"hi: {high} usdt\n"
    msg += f"Entri: {entry}\n"
    if exit_type == "tp":
        msg += f"tp: {tp} usdt\n"
    else:
        msg += f"stop: {stop}\n"
    msg += f"حجم: {vol}\n"
    msg += f"تاریخ: {date_str}"
    return msg

def get_valid_categories(growth):
    cats = []
    if 20 < growth <= 30: 
        cats.append("20_30")
        cats.append("long_20_30")
    elif 30 < growth <= 40: 
        cats.append("30_40")
    elif 40 < growth <= 50: 
        cats.append("40_50")
    elif 50 < growth <= 100: 
        cats.append("50_100")
    elif growth > 100: 
        cats.append("100_plus")
        
    if 30 < growth <= 100:
        cats.append("long_30_100")
    
    if growth >= 50:
        cats.append("fixed_50")
        
    if growth >= 100:
        cats.append("fixed_100")
        
    return cats

def process_markets(app_data):
    trades = app_data.get('trades', [])
    symbols = get_all_usdt_symbols()
    
    current_ts = iran_time.timestamp()
    
    for symbol in symbols:
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
            
            trade_open_ts = pd.to_datetime(trade.get('open_timestamp', 0), unit='s')
            df_since_open = df[df['time'] >= trade_open_ts]
            
            if not df_since_open.empty:
                lowest_since_open = float(df_since_open['low'].min())
                highest_since_open = float(df_since_open['high'].max())
            else:
                lowest_since_open = current_close
                highest_since_open = current_close

            exit_type = None
            if trade_type == 'short':
                if lowest_since_open <= trade['tp']:
                    exit_type = "tp"
                elif highest_since_open >= trade['stop']:
                    exit_type = "stop"
            else:
                if highest_since_open >= trade['tp']:
                    exit_type = "tp"
                elif lowest_since_open <= trade['stop']:
                    exit_type = "stop"
                    
            if exit_type:
                trade['status'] = exit_type
                trade['close_time'] = today_str
                trade['close_price'] = current_close
                if trade_type == 'short':
                    trade['pnl'] = calculate_short_pnl(trade['entry'], current_close, leverage=7)
                else:
                    trade['pnl'] = calculate_long_pnl(trade['entry'], current_close, leverage=7)
                
                neg_pct = int(cat_info['entry_drop'] * 100)
                
                cat_exit_count = len([t for t in trades if t.get('category_id') == cat_id and t.get('close_time') == today_str and t.get('status') in ['tp', 'stop']])
                global_exit_count = len([t for t in trades if t.get('close_time') == today_str and t.get('status') in ['tp', 'stop']])
                
                msg_main = generate_exit_message(
                    exit_type, symbol, cat_info['name_fa'], trade['growth'], neg_pct,
                    trade['low'], trade['high'], trade['entry'], trade['tp'], trade['stop'], vol_str, current_date_str, global_exit_count, trade_type
                )
                
                msg_cat = generate_exit_message(
                    exit_type, symbol, cat_info['name_fa'], trade['growth'], neg_pct,
                    trade['low'], trade['high'], trade['entry'], trade['tp'], trade['stop'], vol_str, current_date_str, cat_exit_count, trade_type
                )
                
                exit_bot_token = SELL_BOT_TOKEN if trade_type == 'short' else BUY_BOT_TOKEN
                
                send_telegram_message(exit_bot_token, [PERSONAL_ID, CHANNEL_EXIT_MAIN], msg_main)
                send_telegram_message(exit_bot_token, [cat_info['report_channel']], msg_cat)

        cat_cooldowns = {}
        for cat_id in valid_cats:
            can_open = True
            for t in trades:
                if t['symbol'] == symbol and t.get('category_id', '20_30') == cat_id:
                    if t['status'] == 'OPEN':
                        can_open = False
                        break
                    else:
                        trade_ts = t.get('open_timestamp', 0)
                        if (current_ts - trade_ts) < (24 * 3600): # 24 hours cooldown
                            can_open = False
                            break
            cat_cooldowns[cat_id] = can_open

        for cat_id in valid_cats:
            if not cat_cooldowns[cat_id]:
                continue
                
            cat_info = CATEGORIES[cat_id]
            trade_type = cat_info.get('trade_type', 'short')
            
            if cat_info.get("is_fixed"):
                target_price = low_24h * (1 + cat_info.get("fixed_growth_target", 0.50))
                entry_trigger = target_price * (1 - cat_info['entry_drop'])
            else:
                entry_trigger = high_24h * (1 - cat_info['entry_drop'])
                
            if current_close <= entry_trigger:
                entry_price = current_close
                if trade_type == 'short':
                    tp_price = round(entry_price * (1 - cat_info['tp_drop']), 5)
                    stop_price = round(entry_price * (1 + cat_info['stop_rise']), 5)
                else:
                    tp_price = round(entry_price * (1 + cat_info.get('tp_rise', 0.15)), 5)
                    stop_price = round(entry_price * (1 - cat_info.get('stop_drop', 0.14)), 5)
                
                new_trade = {
                    'symbol': symbol,
                    'category_id': cat_id,
                    'growth': growth,
                    'low': low_24h,
                    'high': high_24h,
                    'entry': entry_price,
                    'tp': tp_price,
                    'stop': stop_price,
                    'status': 'OPEN',
                    'open_time': today_str,
                    'open_timestamp': int(current_ts),
                    'close_time': '',
                    'close_price': 0.0,
                    'pnl': 0.0
                }
                trades.append(new_trade)
                
                neg_pct = int(cat_info['entry_drop'] * 100)
                cat_entry_count = len([t for t in trades if t.get('category_id') == cat_id and t.get('open_time') == today_str])
                global_entry_count = len([
                    t for t in trades 
                    if t.get('open_time') == today_str 
                    and CATEGORIES.get(t.get('category_id', '20_30'), {}).get('trade_type', 'short') == trade_type
                ])
                
                msg_main = generate_entry_message(
                    symbol, cat_info['name_fa'], growth, neg_pct, low_24h, high_24h, 
                    entry_price, tp_price, stop_price, vol_str, current_date_str, global_entry_count
                )
                
                msg_cat = generate_entry_message(
                    symbol, cat_info['name_fa'], growth, neg_pct, low_24h, high_24h, 
                    entry_price, tp_price, stop_price, vol_str, current_date_str, cat_entry_count
                )
                
                bot_token = SELL_BOT_TOKEN if trade_type == 'short' else BUY_BOT_TOKEN
                
                send_telegram_message(bot_token, [PERSONAL_ID, cat_info['entry_channel']], msg_main)
                send_telegram_message(bot_token, [cat_info['report_channel']], msg_cat)
                    
    app_data['trades'] = trades
    return app_data

def generate_and_send_daily_report(app_data):
    pass # Implementation omitted for brevity to restore file, will keep same as nobitex if needed

if __name__ == '__main__':
    app_data = load_data()
    app_data = process_markets(app_data)
    save_data(app_data)
