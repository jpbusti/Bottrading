"""
DESCARGA DE DATOS INTRADÍA DE TIINGO -> data/raw/<PREFIJO>_<intervalo>.csv

La API key se lee SOLO de la variable de entorno TIINGO_API_KEY (no se escribe en código):
    PowerShell:  $env:TIINGO_API_KEY = "tu_token"

Uso (desde la raíz del proyecto):
    python -m scripts.descargar_tiingo                       # QQQ, 5m y 1h
    python -m scripts.descargar_tiingo --ticker QQQ --intervalos 5m 1h --inicio 2020-01-01
    python -m scripts.descargar_tiingo --forzar              # sobrescribe CSV existentes

Tiingo NO tiene futuros (NQ): el feed IEX es de acciones/ETFs, por eso el ticker por defecto es
QQQ (proxy del Nasdaq-100). El archivo se llama QQQ_5m.csv para NO pisar tu NQ_5m.csv real.
Para usarlo en main.py:  CSV_PREFIJO = "QQQ" y ESCALA_PUNTOS ~ 0.03 en config/config.py.
"""
import argparse
import os
import sys
import types

from config import config as cfg_base
from src.datos import _desde_tiingo


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Descarga velas intradía de Tiingo a data/raw/")
    ap.add_argument("--ticker", default=cfg_base.TICKER_TIINGO)
    ap.add_argument("--prefijo", help="prefijo del CSV (por defecto = ticker)")
    ap.add_argument("--intervalos", nargs="+", default=["5m", "1h"], choices=list(cfg_base.TIINGO_FREQ))
    ap.add_argument("--inicio", default=cfg_base.TIINGO_INICIO, help="YYYY-MM-DD")
    ap.add_argument("--forzar", action="store_true", help="sobrescribir CSV existentes")
    args = ap.parse_args()

    clave = os.environ.get("TIINGO_API_KEY", "")
    if not clave:
        sys.exit("ERROR: falta la variable de entorno TIINGO_API_KEY.\n"
                 "  Token gratis: https://www.tiingo.com/account/api/token\n"
                 '  PowerShell:   $env:TIINGO_API_KEY = "tu_token"')

    prefijo = args.prefijo or args.ticker
    os.makedirs(cfg_base.DIR_DATOS_RAW, exist_ok=True)
    fallos = 0
    for intervalo in args.intervalos:
        ruta = os.path.join(cfg_base.DIR_DATOS_RAW, f"{prefijo}_{intervalo}.csv")
        if os.path.exists(ruta) and not args.forzar:
            print(f"[{intervalo}] ya existe {ruta} (usa --forzar para sobrescribir)")
            continue
        # misma lógica de descarga que usa main.py (src.datos._desde_tiingo)
        cfg = types.SimpleNamespace(**{k: v for k, v in vars(cfg_base).items() if k.isupper()})
        cfg.INTERVALO, cfg.TICKER_TIINGO, cfg.TIINGO_INICIO, cfg.TIINGO_API_KEY = (
            intervalo, args.ticker, args.inicio, clave)
        try:
            df = _desde_tiingo(cfg)
        except Exception as e:   # no imprimimos la URL: contiene el token
            print(f"[{intervalo}] ERROR: {type(e).__name__}: {str(e).replace(clave, '***')}")
            fallos += 1
            continue
        if df is None or df.empty:
            print(f"[{intervalo}] ERROR: Tiingo no devolvió datos para {args.ticker}")
            fallos += 1
            continue
        df.drop(columns=["Date"]).to_csv(ruta)
        print(f"[{intervalo}] OK: {len(df)} velas ({df.index[0].date()} -> {df.index[-1].date()}) -> {ruta}")
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
