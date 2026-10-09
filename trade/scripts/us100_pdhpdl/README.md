# US100 PDH/PDL (reversion en la sesion de NY)

Al abrir NY se marcan el maximo (PDH) y minimo (PDL) de la sesion RTH anterior. Primer toque de cada nivel entre 09:30 y 15:00 ET (barras 5m):
si la barra cierra del lado de rechazo, entrada en contra del nivel (corto en PDH, largo en PDL) en la apertura de la barra siguiente.
SL = k x ATR(14) diario, TP = m x ATR(14) diario, k y m en {0.5, 0.75, 1.0}; salida forzada 15:55 ET. CFD US100 IC Markets (USTEC), NQ como proxy.
Pre-registro: `docs/PREREGISTRO_US100_PDHPDL.md`. Resultado: `docs/RESULTADO_US100_PDHPDL.md`. Salidas: `resultados/us100_pdhpdl/`.

## Como correr (desde `trade/`)
```
python scripts/us100_pdhpdl/run_backtest.py      # rejilla 3x3, robustez temporal, costos de estres y por anio
python scripts/us100_pdhpdl/run_walkforward.py
python scripts/us100_pdhpdl/run_placebo.py       # nivel, timing, direccion
python scripts/us100_pdhpdl/run_robustez.py      # ultima entrada, con/sin rechazo
python scripts/us100_pdhpdl/run_backtest.py --fuente nq   # proxy NQ (idem en los otros scripts)
python -m pytest tests/test_us100_pdhpdl.py
```

## Criterio de aprobacion
PF neto >= 1.15, IC90 inferior > 1.0, >= 300 trades, max DD < 20%, supera los 3 placebos, rejilla 9/9, walk-forward OOS > 1 en todos los folds,
costos de estres con PF > 1. Detalle en el pre-registro.

## Estado
- [x] Pre-registro firmado y commiteado antes de correr (2026-10-09)
- [x] Backtest, walk-forward, placebos, robustez y costos corridos en US100 y NQ
- [x] **NO APROBADA** (PF 0.92, IC90 [0.79, 1.06]; ver resultado)
