from typing import Dict, Optional

import requests

SINA_QUOTE_URL = "https://hq.sinajs.cn/list={exchange}{symbol}"
SINA_QUOTE_URL_HTTP = "http://hq.sinajs.cn/list={exchange}{symbol}"
TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q={exchange}{symbol}"


def _to_float(text: str) -> Optional[float]:
    if text is None:
        return None
    value = str(text).strip()
    if value in {"", "-", "--"}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_exchange(symbol: str) -> str:
    return "sh" if symbol.startswith("6") else "sz"


def _parse_sina_quote(symbol: str, text: str) -> Dict:
    if '="";' in text:
        raise ValueError("No realtime payload returned by Sina API")

    payload = text.split('="', 1)[1].rsplit('"', 1)[0]
    fields = payload.split(",")
    if len(fields) < 32:
        raise ValueError("Malformed realtime payload")

    name = fields[0].strip() or symbol
    prev_close = _to_float(fields[2])
    current_price = _to_float(fields[3])
    volume = _to_float(fields[8])  # 股
    amount = _to_float(fields[9])  # 元
    quote_date = fields[30].strip()
    quote_time = fields[31].strip()

    if (current_price is None or current_price <= 0) and prev_close and prev_close > 0:
        current_price = prev_close

    vwap = None
    if volume and volume > 0 and amount and amount > 0:
        vwap = amount / volume
    elif current_price and current_price > 0:
        vwap = current_price

    premium_pct = None
    if current_price and vwap and vwap > 0:
        premium_pct = (current_price - vwap) / vwap * 100

    return {
        "symbol": symbol,
        "name": name,
        "current_price": current_price,
        "vwap": vwap,
        "volume": volume,
        "amount": amount,
        "premium_pct": premium_pct,
        "quote_date": quote_date,
        "quote_time": quote_time,
        "is_trading_data": bool(volume and volume > 0),
        "error": None,
    }


def _parse_tencent_quote(symbol: str, text: str) -> Dict:
    if "v_" not in text or "~" not in text:
        raise ValueError("No realtime payload returned by Tencent API")
    payload = text.split('"', 1)[1].rsplit('"', 1)[0]
    fields = payload.split("~")
    if len(fields) < 38:
        raise ValueError("Malformed Tencent payload")

    # 腾讯字段：2=名称, 3=代码, 4=当前价, 5=昨收, 36=成交量(手), 37=成交额(万)
    name = fields[1].strip() or symbol
    current_price = _to_float(fields[3])
    prev_close = _to_float(fields[4])
    volume_lot = _to_float(fields[36])  # 手
    amount_wan = _to_float(fields[37])  # 万元
    quote_time = fields[30].strip() if len(fields) > 30 else ""

    if (current_price is None or current_price <= 0) and prev_close and prev_close > 0:
        current_price = prev_close

    volume = volume_lot * 100 if volume_lot is not None else None
    amount = amount_wan * 10000 if amount_wan is not None else None

    vwap = None
    if volume and volume > 0 and amount and amount > 0:
        vwap = amount / volume
    elif current_price and current_price > 0:
        vwap = current_price

    premium_pct = None
    if current_price and vwap and vwap > 0:
        premium_pct = (current_price - vwap) / vwap * 100

    return {
        "symbol": symbol,
        "name": name,
        "current_price": current_price,
        "vwap": vwap,
        "volume": volume,
        "amount": amount,
        "premium_pct": premium_pct,
        "quote_date": None,
        "quote_time": quote_time,
        "is_trading_data": bool(volume and volume > 0),
        "error": None,
    }


def fetch_realtime_quote(symbol: str) -> Dict:
    exchange = _resolve_exchange(symbol)
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://finance.sina.com.cn",
    }

    errors = []

    try:
        resp = requests.get(
            SINA_QUOTE_URL.format(exchange=exchange, symbol=symbol),
            headers=headers,
            timeout=8,
        )
        resp.raise_for_status()
        resp.encoding = "gbk"
        return _parse_sina_quote(symbol, resp.text)
    except Exception as exc:
        errors.append(f"sina_https: {exc}")

    try:
        resp = requests.get(
            SINA_QUOTE_URL_HTTP.format(exchange=exchange, symbol=symbol),
            headers=headers,
            timeout=8,
        )
        resp.raise_for_status()
        resp.encoding = "gbk"
        return _parse_sina_quote(symbol, resp.text)
    except Exception as exc:
        errors.append(f"sina_http: {exc}")

    try:
        resp = requests.get(
            TENCENT_QUOTE_URL.format(exchange=exchange, symbol=symbol),
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        resp.raise_for_status()
        resp.encoding = "gbk"
        return _parse_tencent_quote(symbol, resp.text)
    except Exception as exc:
        errors.append(f"tencent: {exc}")

    return {
        "symbol": symbol,
        "name": symbol,
        "current_price": None,
        "vwap": None,
        "volume": None,
        "amount": None,
        "premium_pct": None,
        "quote_date": None,
        "quote_time": None,
        "is_trading_data": False,
        "error": " | ".join(errors),
    }


def run_realtime_demo(symbol: str = "601088") -> None:
    data = fetch_realtime_quote(symbol)
    if data["error"]:
        raise RuntimeError(f"Realtime fetch failed: {data['error']}")

    print(
        f"[FastEngine] {data['symbol']} {data['name']} "
        f"price={data['current_price']} vwap={data['vwap']} "
        f"premium={data['premium_pct']}%"
    )


if __name__ == "__main__":
    run_realtime_demo("601088")
