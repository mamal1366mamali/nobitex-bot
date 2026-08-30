from datetime import datetime, timedelta
import pandas as pd
import requests
import urllib3
import warnings

warnings.filterwarnings('ignore')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = 'https://apiv2.nobitex.ir/market/udf/history'
ORDERBOOK_URL = 'https://apiv2.nobitex.ir/v3/orderbook/all'

TOKEN = '8456842893:AAHhLRmsDpk6QrmomjKEmPAnOL9xUvi1YnU'
CHAT_ID = '114669886'

peak_prices = {}


def clean_price(val):
  try:
    f_val = float(val)
    if f_val >= 1:
      s = f'{f_val:.4f}'.rstrip('0').rstrip('.')
      return s.replace('.', '/')
    else:
      s = f'{f_val:.8f}'.rstrip('0')
      return s.replace('.', '/')
  except Exception:
    return str(val)


def clean_symbol(symbol):
  s = symbol.replace('USDT', '')
  if s == '' or s == 'BTC':
    return 'BTC'
  return s.lower()


def format_volume(vol_usdt):
  try:
    v = float(vol_usdt)
    if v >= 1_000_000:
      return f'{v / 1_000_000:.1f}M'
    elif v >= 1_000:
      return f'{int(v / 1_000)}k'
    else:
      return f'{int(v)} usdt'
  except Exception:
    return '0 usdt'


def get_all_symbols():
  try:
    response = requests.get(ORDERBOOK_URL, timeout=15, verify=False)
    data = response.json()
    if data.get('status') == 'ok':
      all_symbols = [key for key in data.keys() if key != 'status']
      return [s for s in all_symbols if not s.endswith('IRT')]
    return []
  except Exception:
    return []


def get_candles(symbol, resolution=15, num_candles=100):
  now = datetime.now()
  minutes_needed = num_candles * resolution
  from_ts = int((now - timedelta(minutes=minutes_needed)).timestamp())
  to_ts = int(now.timestamp())

  params = {
      'symbol': symbol,
      'resolution': resolution,
      'from': from_ts,
      'to': to_ts,
  }
  try:
    response = requests.get(
        BASE_URL, params=params, timeout=10, verify=False
    )
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
    return None
  except Exception:
    return None


def analyze_symbol(symbol):
  df = get_candles(symbol, resolution=15, num_candles=100)
  if df is None or len(df) < 50:
    return None

  low_price = float(df['low'].min())
  current_close = float(df['close'].iloc[-1])
  max_high = float(df['high'].max())

  # بررسی رشد حداقل ۵۰ درصدی از کف
  growth_ratio = (max_high - low_price) / low_price
  if growth_ratio < 0.50:
    return None

  growth_percent = int(growth_ratio * 100)

  # محاسبه حجم معاملات به دلار (تخمین حجم کل کندل‌ها یا حجم آخرین کندل در قیمت بسته شدن)
  # در نوبیتکس حجم بر حسب واحد ارز پایه است، پس در قیمت ضرب می‌کنیم تا حجم دلاری به دست آید
  recent_vol = float(df['volume'].iloc[-1])
  vol_in_usdt = recent_vol * current_close

  row_data = {
      'نام ارز': clean_symbol(symbol),
      'متن قله': (
          f'+ {growth_percent} % قیمت قله {clean_price(max_high)}'
      ),
      'حجم': format_volume(vol_in_usdt),
      'Sort_Val': current_close,
  }
  return row_data


def send_to_telegram(message_text):
  url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
  try:
    data = {
        'chat_id': CHAT_ID,
        'text': message_text,
        'parse_mode': 'Markdown',
    }
    requests.post(url, data=data, timeout=20, verify=False)
  except Exception:
    pass


if __name__ == '__main__':
  symbols = get_all_symbols()
  if symbols:
    results = []
    for sym in symbols:
      res = analyze_symbol(sym)
      if res:
        results.append(res)

    if results:
      results = sorted(results, key=lambda x: x['Sort_Val'], reverse=True)

      msg_lines = ['🚨 *ارزهای با رشد بالای ۵۰٪:*']
      for row in results:
        line = (
            f"نام : `{row['نام ارز']}` | میزان رشد {row['متن قله']} | حجم"
            f" `{row['حجم']}`"
        )
        msg_lines.append(line)

      final_message = '\n'.join(msg_lines)
      send_to_telegram(final_message)