import json
import os
import requests
import pandas as pd
import jdatetime
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')

# تنظیمات و توکن‌های تلگرام
ENTRY_BOT_TOKEN = "8843721628:AAE_ppEzKf0Am0CUC_WfjkkuBTRlsO1Bd2g"
EXIT_BOT_TOKEN = "8781543538:AAGCr8Rjc70KouCmrfAbNcu_FhPneFJTCMs"
REPORT_BOT_TOKEN = "8865582989:AAHRhGoMjnVUsBpCNj_FlZAm-Hmk7p_SR0E"

PERSONAL_ID = "114669886"
CHANNEL_EXIT_MAIN = "-1004415777827"
CHANNEL_REPORT_MAIN = "-1004304608564"

# تنظیمات دسته‌بندی‌ها
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
        "name_fa": "مثبت 50 ثابت",
        "entry_channel": "-1004290922830",
        "report_channel": "-1003781040656",
        "entry_drop": 0.15,
        "tp_drop": 0.15,
        "stop_rise": 0.14,
        "trade_type": "short",
        "is_fixed": True,
        "fixed_growth_target": 0.50
    },
    "long_20_30": {
        "name_fa": "+20 الی 30 ٪ (خرید)",
        "entry_channel": "-1004310315552",
        "report_channel": "-1003820960180",
        "entry_drop": 0.20,
        "tp_rise": 0.15,
        "stop_drop": 0.14,
        "trade_type": "long"
    },
    "long_30_80": {
        "name_fa": "+30 الی 80 ٪ (خرید)",
        "entry_channel": "-1004310315552",
        "report_channel": "-1004379515603",
        "entry_drop": 0.35,
        "tp_rise": 0.15,
        "stop_drop": 0.14,
        "trade_type": "long"
    }
}

TRADES_FILE = "trades.json"
BASE_URL = 'https://apiv2.nobitex.ir/market/udf/history'
ORDERBOOK_URL = 'https://apiv2.nobitex.ir/v3/orderbook/all'

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
        if data.get('status') == 'ok':
            all_symbols = [key for key in data.keys() if key != 'status']
            return [s for s in all_symbols if s.endswith('USDT')]
    except Exception:
        pass
    return []

def get_candles(symbol, resolution=60, num_candles=24):
    minutes_needed = num_candles * resolution
    from_ts = int((iran_time - timedelta(minutes=minutes_needed)).timestamp())
    to_ts = int(iran_time.timestamp())
    params = {'symbol': symbol, 'resolution': resolution, 'from': from_ts, 'to': to_ts}
    try:
        response = requests.get(BASE_URL, params=params, timeout=15)
        data = response.json()
        if data.get('s') == 'ok' and data.get('t'):
            df = pd.DataFrame({
                'time': pd.to_datetime(data['t'], unit='s'),
                'open': data['o'],
                'high': data['h'],
                'low': data['l'],
                'close': data['c'],
                'volume': data['v'],
            })
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

def generate_entry_message(symbol, cat_name, growth, neg_percent, low, high, entry, tp, stop, vol, date_str):
    name = clean_symbol(symbol).lower()
    return (
        f"1 نام: {name}\n"
        f"2 دسته بندی رشد: {cat_name}\n"
        f"3 میزان رشد: +{growth:.2f}%\n"
        f"4 درصد منفی: -{neg_percent} ٪\n"
        f"5 low: {low} usdt\n"
        f"6 hi: {high} usdt\n"
        f"7 Entri: {entry}\n"
        f"8 tp: {tp} usdt\n"
        f"9 stop: {stop}\n"
        f"10 حجم: {vol}\n"
        f"11 تاریخ: {date_str}"
    )

def generate_exit_message(exit_type, symbol, cat_name, growth, neg_percent, low, high, entry, tp, stop, vol, date_str):
    name = clean_symbol(symbol).lower()
    msg = f"{exit_type}\n"
    msg += f"1 نام: {name}\n"
    msg += f"2 دسته بندی رشد: {cat_name}\n"
    msg += f"3 میزان رشد: +{growth:.2f}%\n"
    msg += f"4 درصد منفی: -{neg_percent} ٪\n"
    msg += f"5 low: {low} usdt\n"
    msg += f"6 hi: {high} usdt\n"
    msg += f"7 Entri: {entry}\n"
    if exit_type == "tp":
        msg += f"8 tp: {tp} usdt\n"
    else:
        msg += f"8 stop: {stop}\n"
    msg += f"9 حجم: {vol}\n"
    msg += f"10 تاریخ: {date_str}"
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
        
    if 30 < growth <= 80:
        cats.append("long_30_80")
    
    if growth >= 50:
        cats.append("fixed_50")
        
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
        total_volume_usdt = (df['volume'] * df['close']).sum()
        vol_str = format_volume(total_volume_usdt)
        
        growth = 0
        if low_24h > 0:
            growth = ((high_24h - low_24h) / low_24h) * 100

        valid_cats = get_valid_categories(growth)
        
        open_trades_for_symbol = [t for t in trades if t['symbol'] == symbol and t['status'] == 'OPEN']
        
        # 1. Check existing open trades for exits
        for trade in open_trades_for_symbol:
            cat_id = trade.get('category_id', '20_30')
            
            cat_info = CATEGORIES.get(cat_id, CATEGORIES['20_30'])
            trade_type = cat_info.get('trade_type', 'short')
            
            exit_type = None
            if trade_type == 'short':
                if current_close <= trade['tp']:
                    exit_type = "tp"
                elif current_close >= trade['stop']:
                    exit_type = "stop"
            else:
                if current_close >= trade['tp']:
                    exit_type = "tp"
                elif current_close <= trade['stop']:
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
                msg = generate_exit_message(
                    exit_type, symbol, cat_info['name_fa'], trade['growth'], neg_pct,
                    trade['low'], trade['high'], trade['entry'], trade['tp'], trade['stop'], vol_str, current_date_str
                )
                
                chats = [PERSONAL_ID, CHANNEL_EXIT_MAIN, cat_info['report_channel']]
                send_telegram_message(EXIT_BOT_TOKEN, chats, msg)

        # 2. Check 72h Cooldown and Open New Trades
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
                        if (current_ts - trade_ts) < (72 * 3600): # 72 hours cooldown
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
                msg = generate_entry_message(
                    symbol, cat_info['name_fa'], growth, neg_pct, low_24h, high_24h, 
                    entry_price, tp_price, stop_price, vol_str, current_date_str
                )
                
                chats = [PERSONAL_ID, cat_info['entry_channel'], cat_info['report_channel']]
                send_telegram_message(ENTRY_BOT_TOKEN, chats, msg)
                    
    app_data['trades'] = trades
    return app_data

def generate_and_send_daily_report(app_data):
    trades = app_data.get('trades', [])
    
    cat_stats = {cat: {'tp': 0, 'stop': 0, 'opening': 0, 'past_tp': 0, 'past_stop': 0, 'closed_pnl': 0.0, 'open_pnl': 0.0, 'strings': [], 'excel': []} for cat in CATEGORIES.keys()}
    
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
            
            if trade_type == 'short':
                live_pnl = calculate_short_pnl(t['entry'], current_close, leverage=7)
            else:
                live_pnl = calculate_long_pnl(t['entry'], current_close, leverage=7)
                
            stats['open_pnl'] += live_pnl
            
            pnl_str = f"+{live_pnl}%" if live_pnl > 0 else f"{live_pnl}%"
            stats['strings'].append(f"{name} : opening {pnl_str}")
            
            row = {'دسته': CATEGORIES[cat_id]['name_fa'], 'وضعیت عرض': 'opening', 'نام': name, 'کمترین قیمت': t['low'], 'بیشترین قیمت': t['high'], 'قیمت باز شدن معامله': t['entry'], 'قیمت بسته شدن': current_close}
            stats['excel'].append(row)
            all_excel_data.append(row)
            
        elif t['status'] in ['tp', 'stop']:
            if t['close_time'] == today_str:
                stats['closed_pnl'] += t['pnl']
                pnl_str = f"+{t['pnl']}%" if t['pnl'] > 0 else f"{t['pnl']}%"
                
                if t['open_time'] == today_str:
                    if t['status'] == 'tp':
                        stats['tp'] += 1
                        stats['strings'].append(f"{name} tp {pnl_str}")
                    else:
                        stats['stop'] += 1
                        stats['strings'].append(f"{name} stop {pnl_str}")
                else:
                    if t['status'] == 'tp':
                        stats['past_tp'] += 1
                        stats['strings'].append(f"{name} : opening and cloce tp {pnl_str}")
                    else:
                        stats['past_stop'] += 1
                        stats['strings'].append(f"{name} : opening and cloce stop {pnl_str}")
            
            row = {'دسته': CATEGORIES[cat_id]['name_fa'], 'وضعیت عرض': t['status'], 'نام': name, 'کمترین قیمت': t['low'], 'بیشترین قیمت': t['high'], 'قیمت باز شدن معامله': t['entry'], 'قیمت بسته شدن': t['close_price']}
            stats['excel'].append(row)
            all_excel_data.append(row)

    # Send report for each category
    total_all_transactions = 0
    for cat_id, stats in cat_stats.items():
        total = stats['tp'] + stats['stop'] + stats['opening'] + stats['past_tp'] + stats['past_stop']
        total_all_transactions += total
        
        if total == 0:
            continue
            
        cat_info = CATEGORIES[cat_id]
        closed_pnl_str = f"+{stats['closed_pnl']:.0f} ٪" if stats['closed_pnl'] > 0 else f"{stats['closed_pnl']:.0f} ٪"
        open_pnl_str = f"+{stats['open_pnl']:.0f} ٪" if stats['open_pnl'] > 0 else f"{stats['open_pnl']:.0f} ٪"

        msg = f"1 میزان رشد مثبت {cat_info['name_fa'].replace('+','')}\n"
        msg += f"2 تعداد معاملات : {total}\n"
        msg += f"2 1 تعداد tp : {stats['tp']}\n"
        msg += f"2 2 تعداد stop : {stats['stop']}\n"
        msg += f"2 3 تعداد opening : {stats['opening']}\n"
        msg += f"2 4 تعداد opening and cloce {stats['past_tp'] + stats['past_stop']} tp {stats['past_tp']} stop {stats['past_stop']}\n"
        msg += f"3 میزان سود یا ضرر تمامی معاملات بسته شده : {closed_pnl_str}\n"
        msg += f"4 میزان سود یا ضرر تمامی معاملات باز {open_pnl_str}\n"
        msg += "5 نام عرض معاملات بسته و باز همراه سود یا ضرر\n"
        
        for i, s in enumerate(stats['strings']):
            msg += f"{i+1} {s}\n"
            
        msg += f"\n6 تاریخ\n{current_date_str}"

        chats = [PERSONAL_ID, CHANNEL_REPORT_MAIN, cat_info['report_channel']]
        send_telegram_message(REPORT_BOT_TOKEN, chats, msg)

    if total_all_transactions == 0:
        msg = f"تعداد معاملات 0\nتاریخ {current_date_str}"
        chats = [PERSONAL_ID, CHANNEL_REPORT_MAIN]
        for c in CATEGORIES.values():
            chats.append(c['report_channel'])
        chats = list(set(chats))
        send_telegram_message(REPORT_BOT_TOKEN, chats, msg)
        return

    # Excel Generation
    df_excel = pd.DataFrame(all_excel_data)
    status_order = {'tp': 1, 'stop': 2, 'opening': 3}
    df_excel['order'] = df_excel['وضعیت عرض'].map(status_order)
    df_excel = df_excel.sort_values(['دسته', 'order']).reset_index(drop=True)
    df_excel['شماره'] = range(1, len(df_excel) + 1)
    
    cols = ['شماره', 'دسته', 'وضعیت عرض', 'نام', 'کمترین قیمت', 'بیشترین قیمت', 'قیمت باز شدن معامله', 'قیمت بسته شدن']
    df_excel = df_excel[cols]
    
    file_name = f"گزارش_{shamsi_date.replace(' ', '-')}_{iran_time.strftime('%H-%M')}.xlsx"
    
    with pd.ExcelWriter(file_name, engine='openpyxl') as writer:
        df_excel.to_excel(writer, index=False, startrow=8)
        ws = writer.sheets['Sheet1']
        ws['A1'] = f"تعداد تمامی معاملات : {total_all_transactions}"
        ws['A8'] = "شماره"; ws['B8'] = "دسته"; ws['C8'] = "وضعیت"; ws['D8'] = "نام"
        ws['E8'] = "کمترین قیمت"; ws['F8'] = "بیشترین قیمت"
        ws['G8'] = "قیمت باز شدن معامله"; ws['H8'] = "قیمت بسته شدن"

        chats = [PERSONAL_ID, CHANNEL_REPORT_MAIN]
        for c in CATEGORIES.values():
            chats.append(c['report_channel'])
        chats = list(set(chats))
        
        send_telegram_document(REPORT_BOT_TOKEN, chats, file_name, f"گزارش معاملات - {current_date_str}")
        
        try:
            os.remove(file_name)
        except:
            pass

if __name__ == '__main__':
    app_data = load_data()
    app_data = process_markets(app_data)
    
    if iran_time.hour == 20 and iran_time.minute < 15:
        if app_data.get('last_report_date') != today_str:
            generate_and_send_daily_report(app_data)
            app_data['last_report_date'] = today_str

    save_data(app_data)
