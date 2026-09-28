"""
Configuracion central de QuantSignal AI.
"""

from pathlib import Path

# =====================
# MERCADO
# =====================

SYMBOL = "BTC-USD"

PERIOD = "5y"

INTERVAL = "1d"

# Universo de estudio: 50 activos de 5 clases (tickers de Yahoo Finance).
# Mas activos = mas casos historicos para los analogos, el backtesting
# multi-activo y el entrenamiento de la IA.
UNIVERSE = {
    "Cripto": [
        "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD",
        "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD", "DOT-USD",
    ],
    "Indices y ETF": [
        "SPY", "QQQ", "DIA", "IWM", "EFA", "EEM", "TLT", "HYG", "XLF", "XLE",
    ],
    "Acciones EE.UU.": [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "AVGO",
        "NFLX", "JPM", "V", "MA", "UNH", "XOM", "LLY", "COST", "WMT",
    ],
    "Forex": [
        "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "USDCOP=X",
    ],
    "Materias primas": [
        "GC=F", "SI=F", "CL=F", "NG=F", "HG=F", "ZC=F",
    ],
}

NAMES = {
    "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "SOL-USD": "Solana", "BNB-USD": "BNB",
    "XRP-USD": "XRP", "ADA-USD": "Cardano", "DOGE-USD": "Dogecoin", "AVAX-USD": "Avalanche",
    "LINK-USD": "Chainlink", "DOT-USD": "Polkadot",
    "SPY": "S&P 500", "QQQ": "Nasdaq 100", "DIA": "Dow Jones", "IWM": "Russell 2000",
    "EFA": "Desarrollados ex-EE.UU.", "EEM": "Emergentes", "TLT": "Bonos Tesoro 20+",
    "HYG": "Bonos high yield", "XLF": "Sector financiero", "XLE": "Sector energia",
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "Nvidia", "AMZN": "Amazon", "GOOGL": "Alphabet",
    "META": "Meta", "TSLA": "Tesla", "AMD": "AMD", "AVGO": "Broadcom", "NFLX": "Netflix",
    "JPM": "JPMorgan", "V": "Visa", "MA": "Mastercard", "UNH": "UnitedHealth", "XOM": "Exxon",
    "LLY": "Eli Lilly", "COST": "Costco", "WMT": "Walmart",
    "EURUSD=X": "Euro / Dolar", "GBPUSD=X": "Libra / Dolar", "USDJPY=X": "Dolar / Yen",
    "AUDUSD=X": "Dolar australiano", "USDCAD=X": "Dolar / Dolar canadiense",
    "USDCOP=X": "Dolar / Peso colombiano",
    "GC=F": "Oro", "SI=F": "Plata", "CL=F": "Petroleo WTI", "NG=F": "Gas natural",
    "HG=F": "Cobre", "ZC=F": "Maiz",
}

WATCHLIST = [s for group in UNIVERSE.values() for s in group]


def asset_class(symbol):
    for k, v in UNIVERSE.items():
        if symbol in v:
            return k
    if symbol.endswith("-USD"):
        return "Cripto"
    if symbol.endswith("=X"):
        return "Forex"
    if symbol.endswith("=F"):
        return "Materias primas"
    return "Otros"

# =====================
# INDICADORES
# =====================

EMA_FAST = 50
EMA_SLOW = 200

RSI_PERIOD = 14

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

ADX_PERIOD = 14

ATR_PERIOD = 14

# =====================
# RIESGO
# =====================

ACCOUNT_SIZE = 10000
RISK_PERCENT = 1

# Umbrales para abrir operaciones de paper trading automaticas
PAPER_MIN_PROBABILITY = ["MUY ALTA", "EXTREMA"]
PAPER_MIN_PROFIT_FACTOR = 1.8

# Velas maximas para evaluar el resultado de una senal (etiquetado)
OUTCOME_MAX_BARS = 20

# =====================
# RUTAS
# =====================

BASE_DIR = Path(__file__).resolve().parent.parent

STORAGE_DIR = BASE_DIR / "storage"
OUTPUT_DIR = BASE_DIR / "outputs"
CHARTS_DIR = OUTPUT_DIR / "charts"
REPORTS_DIR = OUTPUT_DIR / "reports"
DATASETS_DIR = OUTPUT_DIR / "datasets"
SCREENSHOTS_DIR = STORAGE_DIR / "screenshots"
MODELS_DIR = BASE_DIR / "models"

DB_PATH = STORAGE_DIR / "quantsignal.db"
CACHE_DIR = STORAGE_DIR / "cache"

# Peso de cada tipo de muestra al entrenar la IA.
# Tus operaciones reales valen mas que las simuladas.
SAMPLE_WEIGHTS = {
    "MARKET": 1.0,
    "SIGNAL": 2.0,
    "PAPER": 2.0,
    "MANUAL": 4.0,
    "LIVE": 4.0,
    "IMPORT": 3.0,
}

ENGINE_VERSION = "2.2.0"

# =====================
# COSTES Y RIESGO AVANZADO
# =====================

FEE_PCT = 0.001          # comision por lado (0.1%)
SLIPPAGE_PCT = 0.0005    # deslizamiento por lado (0.05%)
MAX_RISK_PERCENT = 2.0   # tope de riesgo por operacion aunque Kelly sugiera mas

# Cache local de datos (evita descargar 50 activos cada vez)
CACHE_MAX_AGE_HOURS = 6

# Analogos: buscar situaciones parecidas en TODO el universo ("universo")
# o solo en el mismo activo ("activo")
ANALOG_SCOPE = "universo"
ANALOG_K = 100

# Ignorar la vela que aun no ha cerrado (la del dia en curso)
DROP_INCOMPLETE_CANDLE = True

# Escenarios: stop en ATR y objetivos en R (TP1, TP2, TP3)
SCENARIO_STOP_ATR = 2.0
SCENARIO_TARGETS = (1.0, 2.0, 2.5)

# Paper trading automatico: Decision Score minimo y veredicto
PAPER_MIN_SCORE = 65

# Zona horaria en la que escribes las fechas de tus operaciones
LOCAL_TZ = "America/Bogota"


USER_SETTINGS_FILE = BASE_DIR / "config" / "user_settings.json"

EDITABLE = {
    "ACCOUNT_SIZE": float, "RISK_PERCENT": float, "MAX_RISK_PERCENT": float,
    "WATCHLIST": list, "PERIOD": str, "INTERVAL": str, "FEE_PCT": float,
    "SLIPPAGE_PCT": float, "LOCAL_TZ": str, "PAPER_MIN_SCORE": float,
    "SCENARIO_STOP_ATR": float, "DROP_INCOMPLETE_CANDLE": bool,
    "ANALOG_SCOPE": str, "ANALOG_K": int, "CACHE_MAX_AGE_HOURS": float,
}


def load_user_settings():
    """Aplica config/user_settings.json (lo que cambias desde el menu Configuracion)."""
    import json
    if not USER_SETTINGS_FILE.exists():
        return {}
    try:
        data = json.loads(USER_SETTINGS_FILE.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    g = globals()
    for k, v in data.items():
        if k in EDITABLE:
            g[k] = EDITABLE[k](v) if EDITABLE[k] is not list else list(v)
    return data


def save_user_settings(**changes):
    import json
    data = {}
    if USER_SETTINGS_FILE.exists():
        try:
            data = json.loads(USER_SETTINGS_FILE.read_text(encoding="utf-8"))
        except ValueError:
            data = {}
    for k, v in changes.items():
        if k not in EDITABLE:
            raise KeyError(k)
        data[k] = v
    USER_SETTINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    load_user_settings()
    return data


def ensure_dirs():

    for d in [
        STORAGE_DIR,
        OUTPUT_DIR,
        CHARTS_DIR,
        REPORTS_DIR,
        DATASETS_DIR,
        SCREENSHOTS_DIR,
        MODELS_DIR,
        CACHE_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)


load_user_settings()
