"""Walk-forward expansivo por anio (validacion.walk_forward): entrena con anios < Y, elige (k, m), prueba en Y.
Uso (desde trade/):  python scripts/us100_pdhpdl/run_walkforward.py [--fuente us100|nq]
Salida: resultados/us100_pdhpdl/wf_oos_<fuente>.csv y PF por fold."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts._comun.config import cargar_config  # noqa: E402
from scripts.us100_pdhpdl import simulador, strategy  # noqa: E402
from scripts.us100_pdhpdl.run_backtest import CARPETA, OUT, cargar  # noqa: E402
from validacion import pf_inference as pi  # noqa: E402
from validacion.walkforward import fragilidad, pf_por_fold, walk_forward  # noqa: E402


def r_fn(df):
    return df.R.values


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuente", choices=["us100", "nq"])
    a = ap.parse_args()
    cfg = cargar_config(CARPETA)
    if a.fuente:
        cfg["datos"]["fuente"] = a.fuente
    b = cargar(cfg)
    tr = simulador.simular_trades(b, strategy.generar_senales(b, cfg), cfg)
    w = cfg["validacion"]["walkforward"]
    oos, folds = walk_forward(tr, r_fn, combo_defecto=tuple(cfg["riesgo"]["combo_central"]), anio_ini=w["anio_ini"], min_tr=w["min_trades_train"])
    OUT.mkdir(parents=True, exist_ok=True)
    oos.to_csv(OUT / f"wf_oos_{cfg['datos']['fuente']}.csv", index=False)
    print(folds.round(3).to_string())
    pf_f = pf_por_fold(oos, r_fn)
    print("\nPF OOS por anio:\n", pf_f.round(3).to_string(), "\ntodos_gt1:", pf_f.attrs["todos_gt1"])
    print("\nResumen OOS agrupado:", {k: round(v, 3) for k, v in pi.resumen_r(oos.R.values, grupos=oos.fecha.values).items()})
    print("\nFragilidad:\n", fragilidad(oos, r_fn, cfg["validacion"]["fragilidad_umbral_dpf"]).round(3).to_string())


if __name__ == "__main__":
    main()
