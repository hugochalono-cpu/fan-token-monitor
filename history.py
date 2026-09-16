from http.server import BaseHTTPRequestHandler
import json, requests, concurrent.futures

TIMEOUT = 5

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

def kline_normalize(close, high, low, vol, buyvol, trades, ts):
    close = sf(close); high = sf(high); low = sf(low)
    vol   = sf(vol);   buyvol = sf(buyvol)
    sp    = (high - low) / close * 100 if close > 0 else 0
    return {
        'ts':      int(ts),
        'close':   close, 'high': high, 'low': low,
        'vol':     vol,
        'buyVol':  buyvol,
        'sellVol': max(0, vol - buyvol),
        'trades':  int(trades) if trades else 0,
        'spread':  round(sp, 4),
    }

def hist_binance(token):
    if token not in SYMS['Binance']: return None
    sym = SYMS['Binance'][token]
    try:
        r = requests.get(f'https://api.binance.com/api/v3/klines?symbol={sym}&interval=1d&limit=60', timeout=TIMEOUT).json()
        if not isinstance(r, list): return None
        return [kline_normalize(k[4],k[2],k[3],k[7],k[9],k[8],k[0]) for k in r]
    except: return None

def hist_bybit(token):
    if token not in SYMS['Bybit']: return None
    sym = SYMS['Bybit'][token]
    try:
        r   = requests.get(f'https://api.bybit.com/v5/market/kline?category=spot&symbol={sym}&interval=D&limit=60', timeout=TIMEOUT).json()
        lst = r.get('result', {}).get('list', [])
        if not lst: return None
        return [kline_normalize(k[4],k[2],k[3],k[6],0,0,k[0]) for k in reversed(lst)]
    except: return None

def hist_okx(token):
    if token not in SYMS['OKX']: return None
    sym = SYMS['OKX'][token]
    try:
        r    = requests.get(f'https://www.okx.com/api/v5/market/candles?instId={sym}&bar=1D&limit=60', timeout=TIMEOUT).json()
        data = r.get('data', [])
        if not data: return None
        return [kline_normalize(k[4],k[2],k[3],k[7],0,0,k[0]) for k in reversed(data)]
    except: return None

def hist_bitget(token):
    if token not in SYMS['Bitget']: return None
    sym = SYMS['Bitget'][token]
    try:
        r    = requests.get(f'https://api.bitget.com/api/v2/spot/market/candles?symbol={sym}&granularity=1day&limit=60', timeout=TIMEOUT).json()
        data = r.get('data', [])
        if not data: return None
        return [kline_normalize(k[4],k[2],k[3],k[6],0,0,k[0]) for k in reversed(data)]
    except: return None

def hist_gate(token):
    if token not in SYMS['Gate.io']: return None
    sym = SYMS['Gate.io'][token]
    try:
        r = requests.get(f'https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={sym}&interval=1d&limit=60', timeout=TIMEOUT).json()
        if not isinstance(r, list) or not r: return None
        return [kline_normalize(k[2],k[3],k[4],k[1],0,0,int(k[0])*1000) for k in r]
    except: return None

HIST_FETCHERS = {
    'Binance': hist_binance,
    'Bybit':   hist_bybit,
    'OKX':     hist_okx,
    'Bitget':  hist_bitget,
    'Gate.io': hist_gate,
}

def fetch_all():
    result = {tok: {} for tok in TOKENS}
    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as pool:
        futures = {
            (tok, ex): pool.submit(fn, tok)
            for ex, fn in HIST_FETCHERS.items()
            for tok in TOKENS
        }
        for (tok, ex), fut in futures.items():
            try:
                result[tok][ex] = fut.result(timeout=10)
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
