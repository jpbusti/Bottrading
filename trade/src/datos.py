"""
CARGA DE DATOS: CSV local -> Tiingo -> yfinance.

cargar_datos(config) devuelve un DataFrame con índice datetime (America/New_York),
columnas Open, High, Low, Close, Volume (+ columna auxiliar "Date") y solo velas de
la sesión regular. Devuelve None si ninguna fuente funciona.
"""
import os
import re
import time

import pandas as pd

from scripts import pdh_pdl_lab as lab  # reutiliza descargar_datos (yfinance) del laboratorio existente

COLUMNAS = ["Open", "High", "Low", "Close", "Volume"]


def _normalizar(df, config):
    """Estandariza nombres de columna, zona horaria y sesión. Sirve para cualquier fuente."""
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    mapa = {c: c.strip().title() for c in df.columns if str(c).strip().lower() in
            ("open", "high", "low", "close", "volume")}
    df = df.rename(columns=mapa)
    faltan = [c for c in ["Open", "High", "Low", "Close"] if c not in df.columns]
    if faltan:
        raise ValueError(f"faltan columnas {faltan}; hay {list(df.columns)}")
    if "Volume" not in df.columns:
        df["Volume"] = 0.0
    df = df[COLUMNAS]

    idx = df.index
    if not isinstance(idx, pd.DatetimeIndex):
        txt = idx.astype(str)
        # ¿las cadenas traen offset (-04:00 / Z)? -> parseo en UTC; si no, se asumen hora de NY
        con_offset = bool(re.search(r"([+-]\d\d:?\d\d|Z)$", txt[0]))
        if con_offset:
            idx = pd.to_datetime(txt, utc=True)
        else:
            idx = pd.to_datetime(txt).tz_localize(config.ZONA_HORARIA, ambiguous="NaT", nonexistent="NaT")
    elif idx.tz is None:
        idx = idx.tz_localize(config.ZONA_HORARIA, ambiguous="NaT", nonexistent="NaT")
    df.index = idx.tz_convert(config.ZONA_HORARIA)
    df = df[df.index.notna()]
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.between_time(config.HORA_INICIO, config.HORA_FIN_SESION, inclusive="left")
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    if df.empty:
        return None
    df["Date"] = df.index.date
    return df


# ------------------------------------------------------------------------------ CSV
def _desde_csv(config):
    ruta = os.path.join(config.CARPETA_DATOS, f"{config.CSV_PREFIJO}_{config.INTERVALO}.csv")
    if not os.path.exists(ruta):
        return None, ruta
    df = pd.read_csv(ruta, index_col=0)
    return _normalizar(df, config), ruta


# --------------------------------------------------------------------------- Tiingo
def _desde_tiingo(config):
    """
    Descarga velas intradía del feed IEX de Tiingo en tramos de 90 días.
    Endpoint: https://api.tiingo.com/iex/<ticker>/prices (token en query string).
    """
    import requests   # import local: solo se necesita si hay API key

    freq = config.TIINGO_FREQ.get(config.INTERVALO)
    if freq is None:
        raise ValueError(f"intervalo {config.INTERVALO} no soportado por Tiingo")
    url = f"https://api.tiingo.com/iex/{config.TICKER_TIINGO}/prices"
    ini = pd.Timestamp(config.TIINGO_INICIO)
    fin = pd.Timestamp.today().normalize()
    trozos = []
    print(f"Descargando {config.TICKER_TIINGO} de Tiingo ({freq}) {ini.date()} -> {fin.date()}...")
    while ini <= fin:
        tramo_fin = min(ini + pd.Timedelta(days=89), fin)
        params = {"startDate": ini.strftime("%Y-%m-%d"), "endDate": tramo_fin.strftime("%Y-%m-%d"),
                  "resampleFreq": freq, "columns": "open,high,low,close,volume",
                  "token": config.TIINGO_API_KEY, "format": "json"}
        r = requests.get(url, params=params, timeout=60)
        if r.status_code == 429:   # límite de peticiones: una espera y un reintento
            time.sleep(60)
            r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        datos = r.json()
        if datos:
            t = pd.DataFrame(datos)
            t.index = pd.to_datetime(t.pop("date"), utc=True)   # Tiingo devuelve ISO en UTC
            trozos.append(t)
        ini = tramo_fin + pd.Timedelta(days=1)
        time.sleep(0.3)
    if not trozos:
        return None
    return _normalizar(pd.concat(trozos), config)


# ------------------------------------------------------------------------- yfinance
def _desde_yfinance(config):
    periodo = config.PERIODO or config.PERIODOS_YF.get(config.INTERVALO, "60d")
    df = lab.descargar_datos(config.TICKER, periodo, config.INTERVALO)
    if df is None:
        return None
    return _normalizar(df.drop(columns=["Date"], errors="ignore"), config)


# ------------------------------------------------------------------------ principal
def cargar_datos(config):
    """Prioridad: CSV local -> Tiingo (si hay API key) -> yfinance (fallback)."""
    # 1) CSV local
    try:
        df, ruta = _desde_csv(config)
        if df is not None:
            print(f"Datos: CSV local {ruta} ({len(df)} velas)")
            return _resumen(df, "CSV local")
        print(f"(no existe {ruta})")
    except Exception as e:
        print(f"  ERROR leyendo CSV: {e}")

    # 2) Tiingo
    if config.TIINGO_API_KEY:
        try:
            df = _desde_tiingo(config)
            if df is not None:
                if config.TIINGO_GUARDAR_CSV:
                    os.makedirs(config.CARPETA_DATOS, exist_ok=True)
                    ruta = os.path.join(config.CARPETA_DATOS, f"{config.CSV_PREFIJO}_{config.INTERVALO}.csv")
                    df.drop(columns=["Date"]).to_csv(ruta)
                    print(f"  guardado en {ruta} (la próxima vez se leerá de aquí)")
                return _resumen(df, "Tiingo")
        except Exception as e:
            print(f"  ERROR Tiingo: {e}  -> se usa yfinance")
    else:
        print("(sin TIINGO_API_KEY)")

    # 3) yfinance
    print("Datos: fallback yfinance (solo para pruebas rápidas; historia limitada)")
    df = _desde_yfinance(config)
    return _resumen(df, "yfinance") if df is not None else None


def _resumen(df, fuente):
    print(f"  [{fuente}] {len(df)} velas | {df.index[0]} -> {df.index[-1]} | "
          f"{df['Date'].nunique()} sesiones")
    return df
