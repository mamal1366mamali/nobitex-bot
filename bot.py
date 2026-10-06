import json
import os
import requests
import pandas as pd
import jdatetime
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')

# تنظیمات تلگرام
ENTRY_BOT_TOKEN = "8843721628:AAE_ppEzKf0Am0CUC_WfjkkuBTRlsO1Bd2g"
EXIT_BOT_TOKEN = "8781543538:AAGCr8Rjc70KouCmrfAbNcu_FhPneFJTCMs"
REPORT_BOT_TOKEN = "8865582989:AAHRhGoMjnVUsBpCNj_FlZAm-Hmk7p_SR0E"

PERSONAL_ID = "114669886"
CHANNEL_ENTRY = "-1003961062602"
CHANNEL_EXIT = "-1004415777827"
CHANNEL_REPORT = "-1004304608564"
CHANNEL_20_30 = "-1003914385862"

ENTRY_CHATS = [PERSONAL_ID, CHANNEL_ENTRY, CHANNEL_20_30]
EXIT_CHATS = [PERSONAL_ID, CHANNEL_EXIT, CHANNEL_20_30]
REPORT_CHATS = [PERSONAL_ID, CHANNEL_REPORT]

TRADES_FILE = "trades.json"
BASE_URL = 'https://apiv2.nobitex.ir/market/udf/history'
ORDERBOOK_URL = 'https://apiv2.nobitex.ir/v3/orderbook/all'

# محاسبه زمان دقیق ایران
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

def generate_entry_message(symbol, growth, low, high, entry, tp, stop, vol, date_str):
    name = clean_symbol(symbol).lower()
    return (
        f"1 نام\n{name}\n\n"
        f"2 دسته بندی رشد\n+20 الی 30 ٪\n\n"
        f"3 میزان رشد\n+{growth:.2f}%\n\n"
        f"4 درصد منفی\n-14 ٪\n\n"
        f"5 low\n{low} usdt\n\n"
        f"6 hi\n{high} usdt\n\n"
        f"7 Entri\n{entry}\n\n"
        f"8 tp\n{tp} usdt\n\n"
        f"9 stop\n{stop}\n\n"
        f"10 حجم\n{vol}\n\n"
        f"11 تاریخ\n{date_str}"
    )

def generate_exit_message(exit_type, symbol, growth, low, high, entry, tp, stop, vol, date_str):
    name = clean_symbol(symbol).lower()
    msg = f"{exit_type}\n"
    msg += f"1 نام\n{name}\n\n"
    msg += f"2 دسته بندی رشد\n+20 الی 30 ٪\n\n"
    msg += f"3 میزان رشد\n+{growth:.2f}%\n\n"
    msg += f"4 درصد منفی\n-14 ٪\n\n"
    msg += f"5 low\n{low} usdt\n\n"
    msg += f"6 hi\n{high} usdt\n\n"
    msg += f"7 Entri\n{entry}\n\n"
    if exit_type == "tp":
        msg += f"8 tp\n{tp} usdt\n\n"
    else:
        msg += f"8 stop\n{stop}\n\n"
    msg += f"9 حجم\n{vol}\n\n"
    msg += f"10 تاریخ\n{date_str}"
    return msg

def process_markets(app_data):
    trades = app_data.get('trades', [])
    symbols = get_all_usdt_symbols()
    
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

        open_trade_idx = None
        for i, t in enumerate(trades):
            if t['symbol'] == symbol and t['status'] == 'OPEN':
                open_trade_idx = i
                break

        if open_trade_idx is not None:
            trade = trades[open_trade_idx]
            exit_type = None
            
            if current_close <= trade['tp']:
                exit_type = "tp"
            elif current_close >= trade['stop']:
                exit_type = "stop"
                
            if exit_type:
                trade['status'] = exit_type
                trade['close_time'] = today_str
                trade['close_price'] = current_close
                trade['pnl'] = calculate_short_pnl(trade['entry'], current_close, leverage=7)
                
                msg = generate_exit_message(
                    exit_type, symbol, trade['growth'], trade['low'], trade['high'],
                    trade['entry'], trade['tp'], trade['stop'], vol_str, current_date_str
                )
                send_telegram_message(EXIT_BOT_TOKEN, EXIT_CHATS, msg)
        else:
            if 20 < growth < 30:
                entry_trigger = high_24h * (1 - 0.14)
                if current_close <= entry_trigger:
                    entry_price = current_close
                    tp_price = round(entry_price * (1 - 0.07), 5)
                    stop_price = round(entry_price * (1 + 0.14), 5)
                    
                    new_trade = {
                        'symbol': symbol,
                        'growth': growth,
                        'low': low_24h,
                        'high': high_24h,
                        'entry': entry_price,
                        'tp': tp_price,
                        'stop': stop_price,
                        'status': 'OPEN',
                        'open_time': today_str,
                        'close_time': '',
                        'close_price': 0.0,
                        'pnl': 0.0
                    }
                    trades.append(new_trade)
                    
                    msg = generate_entry_message(
                        symbol, growth, low_24h, high_24h, entry_price,
                        tp_price, stop_price, vol_str, current_date_str
                    )
                    send_telegram_message(ENTRY_BOT_TOKEN, ENTRY_CHATS, msg)
                    
    app_data['trades'] = trades
    return app_data

def generate_and_send_daily_report(app_data):
    trades = app_data.get('trades', [])
    tp_count = stop_count = opening_count = 0
    opened_past_closed_today_tp = opened_past_closed_today_stop = 0
    total_closed_pnl = total_open_pnl = 0.0
    
    list_of_strings = []
    excel_data = []

    for t in trades:
        name = clean_symbol(t['symbol']).lower()
        if t['status'] == 'OPEN':
            opening_count += 1
            df = get_candles(t['symbol'], resolution=60, num_candles=1)
            current_close = float(df['close'].iloc[-1]) if df is not None else t['entry']
            live_pnl = calculate_short_pnl(t['entry'], current_close, leverage=7)
            total_open_pnl += live_pnl
            
            pnl_str = f"+{live_pnl}%" if live_pnl > 0 else f"{live_pnl}%"
            list_of_strings.append(f"{name} : opening {pnl_str}")
            
            excel_data.append({
                'وضعیت عرض': 'opening', 'نام': name, 'کمترین قیمت': t['low'],
                'بیشترین قیمت': t['high'], 'قیمت باز شدن معامله': t['entry'], 'قیمت بسته شدن': current_close
            })
            
        elif t['status'] in ['tp', 'stop']:
            if t['close_time'] == today_str:
                total_closed_pnl += t['pnl']
                pnl_str = f"+{t['pnl']}%" if t['pnl'] > 0 else f"{t['pnl']}%"
                
                if t['open_time'] == today_str:
                    if t['status'] == 'tp':
                        tp_count += 1
                        list_of_strings.append(f"{name} tp {pnl_str}")
                    else:
                        stop_count += 1
                        list_of_strings.append(f"{name} stop {pnl_str}")
                else:
                    if t['status'] == 'tp':
                        opened_past_closed_today_tp += 1
                        list_of_strings.append(f"{name} : opening and cloce tp {pnl_str}")
                    else:
                        opened_past_closed_today_stop += 1
                        list_of_strings.append(f"{name} : opening and cloce stop {pnl_str}")
                
                excel_data.append({
                    'وضعیت عرض': t['status'], 'نام': name, 'کمترین قیمت': t['low'],
                    'بیشترین قیمت': t['high'], 'قیمت باز شدن معامله': t['entry'], 'قیمت بسته شدن': t['close_price']
                })

    total_transactions = tp_count + stop_count + opening_count + opened_past_closed_today_tp + opened_past_closed_today_stop

    if total_transactions == 0:
        msg = f"تعداد معاملات 0\nتاریخ {current_date_str}"
        send_telegram_message(REPORT_BOT_TOKEN, REPORT_CHATS, msg)
        return

    closed_pnl_str = f"+{total_closed_pnl:.0f} ٪" if total_closed_pnl > 0 else f"{total_closed_pnl:.0f} ٪"
    open_pnl_str = f"+{total_open_pnl:.0f} ٪" if total_open_pnl > 0 else f"{total_open_pnl:.0f} ٪"

    msg = "1 میزان رشد مثبت 20 الی 30 %\n"
    msg += f"2 تعداد معاملات : {total_transactions}\n"
    msg += f"2 1 تعداد tp : {tp_count}\n"
    msg += f"2 2 تعداد stop : {stop_count}\n"
    msg += f"2 3 تعداد opening : {opening_count}\n"
    msg += f"2 4 تعداد opening and cloce {opened_past_closed_today_tp + opened_past_closed_today_stop} tp {opened_past_closed_today_tp} stop {opened_past_closed_today_stop}\n"
    msg += f"3 میزان سود یا ضرر تمامی معاملات بسته شده : {closed_pnl_str}\n"
    msg += f"4 میزان سود یا ضرر تمامی معاملات باز {open_pnl_str}\n"
    msg += "5 نام عرض معاملات بسته و باز همراه سود یا ضرر\n"
    
    for i, s in enumerate(list_of_strings):
        msg += f"{i+1} {s}\n"
        
    msg += f"\n6 تاریخ\n{current_date_str}"

    send_telegram_message(REPORT_BOT_TOKEN, REPORT_CHATS, msg)

    df_excel = pd.DataFrame(excel_data)
    status_order = {'tp': 1, 'stop': 2, 'opening': 3}
    df_excel['order'] = df_excel['وضعیت عرض'].map(status_order)
    df_excel = df_excel.sort_values('order').reset_index(drop=True)
    df_excel['شماره'] = range(1, len(df_excel) + 1)
    
    cols = ['شماره', 'وضعیت عرض', 'نام', 'کمترین قیمت', 'بیشترین قیمت', 'قیمت باز شدن معامله', 'قیمت بسته شدن']
    df_excel = df_excel[cols]
    
    file_name = f"گزارش_{shamsi_date.replace(' ', '-')}_{iran_time.strftime('%H-%M')}.xlsx"
    
    with pd.ExcelWriter(file_name, engine='openpyxl') as writer:
        df_excel.to_excel(writer, index=False, startrow=8)
        ws = writer.sheets['Sheet1']
        ws['A1'] = f"تعداد تمامی معاملات : {total_transactions}"
        ws['A2'] = f"تعداد معاملات tp : {tp_count + opened_past_closed_today_tp}"
        ws['A3'] = f"تعداد معاملات stop : {stop_count + opened_past_closed_today_stop}"
        ws['A4'] = f"تعداد معاملات opening : {opening_count}"
        ws['A5'] = f"میزان سود یا ضرر معاملات بسته {closed_pnl_str}"
        ws['A6'] = f"میزان سود یا ضرر معاملات باز {open_pnl_str}"
        ws['A8'] = "شماره"; ws['B8'] = "وضعیت"; ws['C8'] = "نام"
        ws['D8'] = "کمترین قیمت"; ws['E8'] = "بیشترین قیمت"
        ws['F8'] = "قیمت باز شدن معامله"; ws['G8'] = "قیمت بسته شدن"

    send_telegram_document(REPORT_BOT_TOKEN, REPORT_CHATS, file_name, f"گزارش معاملات - {current_date_str}")
    
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
