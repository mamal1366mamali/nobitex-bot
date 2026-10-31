import json
import os
import math
import time
import requests
import re
import concurrent.futures
from datetime import datetime, timedelta
import jdatetime
import warnings

warnings.filterwarnings('ignore')

BOT_TOKEN = os.environ.get("ROSHD_BOT_TOKEN", "")
CHANNEL_ID = "-1003961062602"
DATA_FILE = "ourbit_data.json"

OURBIT_TICKER_URL = "https://futures.ourbit.com/api/v1/contract/ticker"
OURBIT_KLINE_URL = "https://futures.ourbit.com/api/v1/contract/kline"

# هر ۲ ساعت یک بار = هر ۱۲۰ دقیقه
REPORT_INTERVAL_MINUTES = 120


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception:
        pass


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_report_minute": -1, "ref_cache": {}}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


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
                    except Exception:
                        pass
    except Exception as e:
        print(f"Error fetching market data: {e}")
    return prices, stats_data


def _kline_ref_24h(pair, tries=2, sleep_base=0.3):
    """کلوز دقیق ۲۴ ساعت قبل (بر اساس کندل ۵ دقیقه‌ای)"""
    target = time.time() - 24 * 3600
    for i in range(tries):
        try:
            r = requests.get(
                f"{OURBIT_KLINE_URL}/{pair}?interval=Min5&limit=300",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=20
            )
            res = r.json()
            d = res.get("data") or {}
            times = d.get("time") if isinstance(d, dict) else None
            closes = d.get("close") if isinstance(d, dict) else None
            if times and closes:
                best = None
                for ts, c in zip(times, closes):
                    try:
                        t = float(ts)
                    except Exception:
                        continue
                    if t > 1e11:
                        t /= 1000.0
                    if t <= target:
                        best = float(c)
                    else:
                        break
                if best and best > 0:
                    return best
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
    """شمارش مثبت/منفی بر اساس ۲۴ ساعت واقعی"""
    hour_key = int(time.time() // 3600)
    cache = data.get("ref_cache") or {}
    if force or cache.get("hour") != hour_key:
        refs = {}
    else:
        refs = dict(cache.get("prices") or {})

    syms = list(stats_data.keys())
    missing = [s for s in syms if not refs.get(s)]

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
    up_pct = int(round((up_count / total) * 100))
    if up_count * 3 <= total:
        return f"نزولی {up_pct} %"
    elif up_count * 3 >= total * 2:
        return f"صعودی {up_pct} %"
    return f"رنج {up_pct} %"


def should_send_report(data, iran_time):
    """بررسی اینکه آیا وقت ارسال گزارش ۲ ساعته رسیده یا نه"""
    # دقیقه کلی روز (0 تا 1439)
    minute_of_day = iran_time.hour * 60 + iran_time.minute

    # هر ۱۲۰ دقیقه یک slot داریم: 0-119, 120-239, 240-359, ...
    current_slot = minute_of_day // REPORT_INTERVAL_MINUTES

    last_slot = data.get("last_report_slot", -1)
    last_date = data.get("last_report_date", "")

    iran_date_str = jdatetime.datetime.fromgregorian(datetime=iran_time).strftime("%Y/%m/%d")

    # اگر روز جدید شد، slot را ریست کن
    if last_date != iran_date_str:
        last_slot = -1

    return current_slot != last_slot, current_slot, iran_date_str


def main():
    data = load_data()

    iran_time = datetime.utcnow() + timedelta(hours=3, minutes=30)

    should_report, current_slot, today_str = should_send_report(data, iran_time)

    if not should_report:
        print("هنوز وقت ارسال گزارش نرسیده.")
        save_data(data)
        return

    # دریافت داده‌های بازار
    prices, stats_data = get_market_data()

    if not stats_data:
        print("خطا در دریافت داده‌های بازار.")
        save_data(data)
        return

    # محاسبه حال بازار
    up_count, down_count, covered = get_true_24h_counts(stats_data, data)

    if (up_count + down_count) == 0:
        up_count, down_count, covered = get_true_24h_counts(stats_data, data, force=True)

    if (up_count + down_count) == 0:
        print("داده‌های ارجاع ۲۴ ساعته دریافت نشد.")
        save_data(data)
        return

    trend = build_market_status_line(up_count, down_count)
    if not trend:
        save_data(data)
        return

    time_str = iran_time.strftime('%H : %M')
    shamsi_date = jdatetime.datetime.fromgregorian(datetime=iran_time).strftime('%Y/%m/%d')

    msg = (
        f"حال بازار {trend}\n"
        f"تعداد ارزهای مثبت {up_count}\n"
        f"تعداد ارزهای منفی {down_count}\n\n"
        f"تاریخ {shamsi_date} ساعت {time_str}"
    )

    send_telegram_message(msg)
    print(f"گزارش حال بازار ارسال شد: {trend}")

    # ذخیره slot فعلی تا دوباره ارسال نشه
    data["last_report_slot"] = current_slot
    data["last_report_date"] = today_str
    save_data(data)


if __name__ == "__main__":
    main()
