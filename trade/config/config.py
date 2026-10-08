"""
CONFIGURACIÓN CENTRAL del sistema de backtesting multi-estrategia.

Edita este archivo (o usa --config otro_archivo.py, o los argumentos de main.py: --ticker, --intervalo, --periodo)
para cambiar el activo, la temporalidad y la fuente de datos.

Orden de prioridad de las fuentes de datos (ver datos.cargar_datos):
  1) CSV local     -> data/<CSV_PREFIJO>_<INTERVALO>.csv   (ej. data/NQ_5m.csv)
  2) Tiingo (API)  -> solo si TIINGO_API_KEY está definida
  3) yfinance      -> fallback para pruebas rápidas (límite: 60 días en 5m/15m/30m, 730 en 1h)

CÓMO OBTENER UNA API KEY GRATUITA DE TIINGO
  1. Crea una cuenta gratis en https://www.tiingo.com/
  2. Ve a https://www.tiingo.com/account/api/token  y copia tu token.
  3. Pégalo abajo en TIINGO_API_KEY, o (recomendado, para no subirlo a git) defínelo como
     variable de entorno:   PowerShell:  $env:TIINGO_API_KEY = "tu_token"
  OJO: Tiingo NO ofrece futuros (NQ=F). Su feed intradía (IEX) cubre acciones y ETFs,
  por eso TICKER_TIINGO usa QQQ como proxy del Nasdaq-100. Ver README (sección "Escala").
"""
import os
from pathlib import Path

# --- Rutas (siempre relativas a la raíz del proyecto, no al directorio desde el que se ejecute) ---
RAIZ = Path(__file__).resolve().parent.parent
DIR_DATOS_RAW = str(RAIZ / "data" / "raw")               # CSVs originales descargados
DIR_DATOS_PROCESADOS = str(RAIZ / "data" / "processed")  # CSVs con indicadores calculados
DIR_RESULTADOS_CSV = str(RAIZ / "resultados" / "csv")
DIR_RESULTADOS_PNG = str(RAIZ / "resultados" / "png")
DIR_REPORTES = str(RAIZ / "resultados" / "reportes")

# --- Activo y temporalidad -----------------------------------------------------------
TICKER = "NQ=F"            # ticker para yfinance (fallback)
TICKER_TIINGO = "QQQ"      # ticker para Tiingo (ETF proxy del Nasdaq-100; no hay futuros)
CSV_PREFIJO = "NQ"         # busca data/NQ_<INTERVALO>.csv
CARPETA_DATOS = DIR_DATOS_RAW
INTERVALO = "5m"           # 5m, 15m, 30m, 1h
PERIODO = None             # periodo de yfinance; None = automático según INTERVALO (ver abajo)
PERIODOS_YF = {"5m": "60d", "15m": "60d", "30m": "60d", "1h": "730d"}

ZONA_HORARIA = "America/New_York"
HORA_INICIO = "09:30"
HORA_FIN_SESION = "16:00"  # se conservan solo velas de la sesión regular [09:30, 16:00)

# --- Tiingo --------------------------------------------------------------------------
TIINGO_API_KEY = os.environ.get("TIINGO_API_KEY", "")   # o escribe aquí tu token entre comillas
TIINGO_INICIO = "2017-01-01"        # el feed IEX intradía de Tiingo arranca a finales de 2016
TIINGO_GUARDAR_CSV = True           # guarda lo descargado en data/ para no volver a pedirlo
TIINGO_FREQ = {"5m": "5min", "15m": "15min", "30m": "30min", "1h": "1hour"}

# --- Escala de puntos ----------------------------------------------------------------
# Los SL/TP de las grids y el spread están en "puntos de NQ". Si usas un activo de otro
# precio (ej. QQQ ~ 0.03x el nivel del NQ) pon aquí el factor para reescalarlos.
ESCALA_PUNTOS = 1.0

# --- Indicadores ---------------------------------------------------------------------
ATR_PERIODO = 14
RSI_PERIODO = 14
BB_PERIODO = 20
BB_DESV = 2.0
ATR_VENTANA_REL = 100      # ATR_ratio = ATR / media móvil (causal) de las últimas N velas del ATR

# --- Estrategias ---------------------------------------------------------------------
ORB_MINUTOS = 30           # rango de apertura: primeros 30 min (con velas de 1h = la 1ª vela)
FILTRO_RSI_BAJO = 40       # filtro rsi_extremo: LONG solo si RSI < 40
FILTRO_RSI_ALTO = 60       # y SHORT solo si RSI > 60
FILTRO_BB_BAJO = 0.2       # filtro bb_extremo: LONG si %B < 0.2, SHORT si %B > 0.8
FILTRO_BB_ALTO = 0.8

# --- Grid de parámetros del motor (puntos NQ, se multiplican por ESCALA_PUNTOS) ----
GRID_SL = [20, 40, 60]
GRID_TP = [20, 40, 80]
GRID_MAX_TRADES = [1, 2]
HORA_ULTIMA_ENTRADA = "15:00"

# --- Validación walk-forward ---------------------------------------------------------
PCT_IN_SAMPLE = 0.60
MIN_TRADES_IS = 15         # mínimo de trades IS para que una config entre al ranking
MIN_TRADES_OOS = 8         # mínimo de trades OOS para dar un veredicto
MIN_TRADES_FIABLE = 30     # por debajo, se avisa "muestra insuficiente"

CARPETA_RESULTADOS = DIR_RESULTADOS_CSV   # destino de comparacion_estrategias*.csv
