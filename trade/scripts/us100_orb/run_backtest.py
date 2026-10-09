"""Backtest US100 ORB filtrado (rejilla k x m completa). NO ejecutar hasta firmar docs/PREREGISTRO_US100_ORB.md.

Uso (desde la raiz):  python scripts/us100_orb/run_backtest.py [--fuente us100|nq]
Salida: resultados/us100_orb/trades.csv y resumen en pantalla. Los placebos y walk-forward van en sus propios scripts.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts._comun.config import cargar_config  # noqa: E402
from scripts.us100_orb import analysis, datos, simulador, strategy  # noqa: E402

CARPETA = Path(__file__).resolve().parent
OUT = CARPETA.parents[1] / "resultados" / "us100_orb"


def cargar(cfg):
    """Barras 5m RTH con ATR diario previo, VWAP y volumen relativo."""
    return strategy.agregar_indicadores(datos.preparar(cfg), cfg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuente", choices=["us100", "nq"])
    a = ap.parse_args()
    cfg = cargar_config(CARPETA)
    if a.fuente:
        cfg["datos"]["fuente"] = a.fuente
    b = cargar(cfg)
    sen = strategy.generar_senales(b, cfg)
    tr = simulador.simular_trades(b, sen, cfg)
    OUT.mkdir(parents=True, exist_ok=True)
    tr.to_csv(OUT / f"trades_{cfg['datos']['fuente']}.csv", index=False)
    res = analysis.resumen_central(tr, cfg)
    rob = analysis.robustez(tr, cfg)
    analysis.imprimir(res, rob, analysis.criterios(res, rob, None, cfg))


if __name__ == "__main__":
    main()
