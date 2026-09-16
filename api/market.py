from http.server import BaseHTTPRequestHandler
import json, requests, concurrent.futures

TIMEOUT = 3

TOKENS = [
    'ACM', 'AFC', 'ALA', 'AM', 'ARG', 'ASR', 'ATM', 'BAR',
    'CITY', 'GAL', 'INTER', 'ITA', 'JUV', 'MENGO', 'NAP',
    'OG', 'POR', 'PSG', 'SPURS', 'TRA',
]

SYMS = {
    'Binance': {
        'ACM': 'ACMUSDT', 'ASR': 'ASRUSDT', 'ATM': 'ATMUSDT', 'BAR': 'BARUSDT',
        'CITY': 'CITYUSDT', 'JUV': 'JUVUSDT', 'OG': 'OGUSDT', 'PSG': 'PSGUSDT',
    },
    'Bybit': {
        'CITY': 'CITYUSDT', 'JUV': 'JUVUSDT', 'PSG': 'PSGUSDT',
    },
    'Bitget': {
        'ACM': 'ACMUSDT', 'ASR': 'ASRUSDT', 'ATM': 'ATMUSDT',
        'JUV': 'JUVUSDT', 'PSG': 'PSGUSDT',
    },
    'OKX': {
        'ARG': 'ARG-USDT', 'CITY': 'CITY-USDT', 'GAL': 'GAL-USDT',
        'MENGO': 'MENGO-USDT', 'POR': 'POR-USDT', 'SPURS': 'SPURS-USDT',
        'TRA': 'TRA-USDT',
    },
    'Gate.io': {
        'ACM': 'ACM_USDT', 'AFC': 'AFC_USDT', 'ALA': 'ALA_USDT', 'AM': 'AM_USDT',
        'ARG': 'ARG_USDT', 'ASR': 'ASR_USDT', 'ATM': 'ATM_USDT', 'CITY': 'CITY_USDT',
        'GAL': 'GAL_USDT', 'INTER': 'INTER_USDT', 'ITA': 'ITA_USDT', 'JUV': 'JUV_USDT',
        'MENGO': 'MENGO_USDT', 'NAP': 'NAP_USDT', 'OG': 'OG_USDT', 'POR': 'POR_USDT',
        'PSG': 'PSG_USDT', 'SPURS': 'SPURS_USDT',
    },
}

def sf(v, d=0.0):
    try:
        return float(v) if v not in (None, '', 'null') else d
    except:
        return d

def buy_ratio(bids, asks, n=10):
    bq = sum(sf(b[1]) for b in bids[:n])
    aq = sum(sf(a[1]) for a in asks[:n])
    t  = bq + aq
    return bq / t if t > 0 else 0.5

def make_result(price, bid, ask, qvol, bids, asks):
    bid, ask = sf(bid), sf(ask)
    spread = (ask - bid) / bid * 100 if bid > 0 else 0
    ratio  = buy_ratio(bids, asks)
    return {
        'price':   sf(price),
        'bid':     bid,
        'ask':     ask,
        'spread':  round(spread, 6),
        'buyVol':  sf(qvol) * ratio,
        'sellVol': sf(qvol) * (1 - ratio),
        'bids':    [[sf(b[0]), sf(b[1])] for b in bids[:50]],
        'asks':    [[sf(a[0]), sf(a[1])] for a in asks[:50]],
    }

def fetch_binance(token):
    if token not in SYMS['Binance']: return None
    sym = SYMS['Binance'][token]
    try:
        tick  = requests.get(f'https://api.binance.com/api/v3/ticker/24hr?symbol={sym}', timeout=TIMEOUT).json()
        if 'code' in tick: return None
        depth = requests.get(f'https://api.binance.com/api/v3/depth?symbol={sym}&limit=50', timeout=TIMEOUT).json()
        return make_result(tick.get('lastPrice'), tick.get('bidPrice'), tick.get('askPrice'),
                           tick.get('quoteVolume'), depth.get('bids', []), depth.get('asks', []))
    except: return None

def fetch_bybit(token):
    if token not in SYMS['Bybit']: return None
    sym = SYMS['Bybit'][token]
    try:
        tick = requests.get(f'https://api.bybit.com/v5/market/tickers?category=spot&symbol={sym}', timeout=TIMEOUT).json()
        lst  = tick.get('result', {}).get('list', [])
        if not lst: return None
        t     = lst[0]
        depth = requests.get(f'https://api.bybit.com/v5/market/orderbook?category=spot&symbol={sym}&limit=50', timeout=TIMEOUT).json()
        res   = depth.get('result', {})
        return make_result(t.get('lastPrice'), t.get('bid1Price'), t.get('ask1Price'),
                           t.get('turnover24h'), res.get('b', []), res.get('a', []))
    except: return None

def fetch_okx(token):
    if token not in SYMS['OKX']: return None
    sym = SYMS['OKX'][token]
    try:
        tick  = requests.get(f'https://www.okx.com/api/v5/market/ticker?instId={sym}', timeout=TIMEOUT).json()
        data  = tick.get('data', [])
        if not data: return None
        t     = data[0]
        depth = requests.get(f'https://www.okx.com/api/v5/market/books?instId={sym}&sz=50', timeout=TIMEOUT).json()
        dd    = (depth.get('data') or [{}])[0]
        return make_result(t.get('last'), t.get('bidPx'), t.get('askPx'),
                           t.get('volCcy24h'), dd.get('bids', []), dd.get('asks', []))
    except: return None

def fetch_bitget(token):
    if token not in SYMS['Bitget']: return None
    sym = SYMS['Bitget'][token]
    try:
        tick  = requests.get(f'https://api.bitget.com/api/v2/spot/market/tickers?symbol={sym}', timeout=TIMEOUT).json()
        data  = tick.get('data', [])
        if not data: return None
        t     = data[0]
        depth = requests.get(f'https://api.bitget.com/api/v2/spot/market/orderbook?symbol={sym}&limit=50', timeout=TIMEOUT).json()
        dd    = depth.get('data', {})
        return make_result(t.get('lastPr'), t.get('bidPr'), t.get('askPr'),
                           t.get('quoteVolume'), dd.get('bids', []), dd.get('asks', []))
    except: return None

def fetch_gate(token):
    if token not in SYMS['Gate.io']: return None
    sym = SYMS['Gate.io'][token]
    try:
        tick  = requests.get(f'https://api.gateio.ws/api/v4/spot/tickers?currency_pair={sym}', timeout=TIMEOUT).json()
        if not tick: return None
        t     = tick[0]
        depth = requests.get(f'https://api.gateio.ws/api/v4/spot/order_book?currency_pair={sym}&limit=50', timeout=TIMEOUT).json()
        return make_result(t.get('last'), t.get('highest_bid'), t.get('lowest_ask'),
                           t.get('quote_volume'), depth.get('bids', []), depth.get('asks', []))
    except: return None

FETCHERS = {
    'Binance': fetch_binance,
    'Bybit':   fetch_bybit,
    'OKX':     fetch_okx,
    'Bitget':  fetch_bitget,
    'Gate.io': fetch_gate,
}

def fetch_all():
    result = {tok: {} for tok in TOKENS}
    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as pool:
        futures = {
            (tok, ex): pool.submit(fetcher, tok)
            for ex, fetcher in FETCHERS.items()
            for tok in TOKENS
        }
        for (tok, ex), fut in futures.items():
            try:
                result[tok][ex] = fut.result(timeout=6)
            except:
                result[tok][ex] = None
    return result

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        data = fetch_all()
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass
