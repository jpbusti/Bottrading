# Estandar de estrategia

Toda estrategia nueva vive en `scripts/<nombre>/` con esta estructura. Plantilla de referencia: `scripts/us100_orb/`.

```
scripts/<nombre>/
├── __init__.py
├── config.yaml          # TODOS los parametros (SL, TP, horarios, filtros, costos, criterios de aprobacion)
├── strategy.py          # SOLO logica de senales (sin fills, sin costos)
├── run_backtest.py      # backtest usando validacion/
├── run_walkforward.py   # walk-forward (validacion.walk_forward)
├── run_placebo.py       # placebos (validacion.placebo)
├── analysis.py          # reportes y metricas (validacion.pf_inference / atr_grid)
├── README.md            # descripcion, como correr, criterio de aprobacion, estado (checklist)
├── datos.py             # (opcional) carga y preparacion de barras
└── simulador.py         # (opcional) simulacion de fills, SL/TP y costos
```
`datos.py` y `simulador.py` son opcionales: mantienen `strategy.py` limpio cuando hay carga o simulacion propias.

## Reglas
1. **Dependencia unidireccional.** `validacion/` NUNCA importa de `scripts/`. Lo vigila `tests/test_us100_orb.py::test_validacion_nunca_importa_scripts`.
2. **Parametros en `config.yaml`**, no hardcodeados en `strategy.py`. Un valor sin confirmar se marca `[VERIFICAR]` en el yaml y en el pre-registro; no se inventa. Se carga con `scripts/_comun/config.py::cargar_config`.
3. **Cada estrategia tiene `README.md`** con: descripcion, como correr, criterio de aprobacion y checklist de estado.
4. **Pre-registro** en `docs/PREREGISTRO_<NOMBRE>.md`, firmado ANTES de correr el backtest (y commiteado).
5. **Resultado** en `docs/RESULTADO_<NOMBRE>.md`, DESPUES de correr.
6. **Tests** de la estrategia en `tests/test_<nombre>.py` (datos sinteticos, sin depender de CSV grandes).
7. **Nada se borra:** lo obsoleto se mueve a `scripts/_archivo/`.

## Criterios de aprobacion (minimos, ver skill trading-methodology)
Costos modelados (spread/slippage por instrumento via `validacion/cost_model.py`), walk-forward con varios folds, placebos
(nivel, timing, direccion), IC90 inferior del PF > 1.0, PF neto >= 1.15 y rejilla de parametros + sensibilidad temporal (excluir cada anio).
Cada estrategia fija sus umbrales exactos en su pre-registro y en `config.yaml: aprobacion`.

## Reporte obligatorio de cada backtest
PF neto, IC90 inferior, numero de trades, max drawdown, y robustez (rejilla de parametros y sensibilidad temporal).
`analysis.py` de la plantilla ya lo produce.

## Otras carpetas
`validacion/` (motor comun, no tocar al anadir estrategias), `data/raw/<instrumento>/` (CSV ignorados por git),
`resultados/<nombre>/`, `docs/` (PREREGISTRO_*, RESULTADO_*, `planes/`, `informes/`), `scripts/descarga/` (utilidades de datos),
`scripts/_comun/` (cargador de config), `scripts/_archivo/` (obsoleto).

## Estrategias legado (LSR v1, G2, US100 v1)
Estudios **cerrados y congelados** que se anteceden al estandar. Conservan su motor tal cual para reproducir sus resultados
(verificado: ver `scripts/*/README.md`). Cumplen parcialmente: tienen `config.yaml` (referencia, vigilado por
`tests/test_config_legado.py`) y `README.md`, pero no se separaron en `strategy.py`/`run_*` para no arriesgar la reproduccion.
Si se reabren, se migran al estandar completo en una estrategia nueva (`<nombre>_v2`).
