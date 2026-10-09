# US100 ORB filtrado (VWAP + volumen + retest)

Opening Range de 15 min en 5m (RTH ET), ruptura por cierre, filtros de pendiente de VWAP, volumen > 1.5x media de 20 barras y retest del nivel roto.
SL = k x ATR(14), TP = m x ATR(14), k en {0.8, 1.0, 1.2}, m en {1.5, 1.75, 2.0}. CFD US100 IC Markets (USTEC), NQ como proxy opcional.
Pre-registro: `docs/PREREGISTRO_US100_ORB.md` (firmado 2026-10-09). Resultados: `resultados/us100_orb/` y `docs/RESULTADO_US100_ORB.md`.

## Archivos
`config.yaml` parametros | `datos.py` carga 1m -> barras 5m RTH + ATR diario previo | `strategy.py` senales | `simulador.py` fills/SL/TP/costos |
`run_backtest.py` | `run_walkforward.py` | `run_placebo.py` | `analysis.py` reporte y criterios | `event_study.py` Fase 0 | `run_robustez.py`.

## Como correr (orden: Fase 0 estudio de eventos -> backtest)
```powershell
python scripts/us100_orb/event_study.py      # Fase 0: retornos forward vs baseline
python scripts/us100_orb/run_backtest.py      # rejilla 3x3, resumen, robustez
python scripts/us100_orb/run_robustez.py      # pendiente VWAP, barras de retest, ultima entrada
python scripts/us100_orb/run_walkforward.py
python scripts/us100_orb/run_placebo.py       # nivel, timing, direccion
python scripts/us100_orb/run_backtest.py --fuente nq    # proxy NQ
python -m pytest tests/test_us100_orb.py
```

## Criterio de aprobacion
PF neto >= 1.15, IC90 inferior del PF > 1.0, >= 300 trades, max DD < 20%, supera los 3 placebos, rejilla robusta (9/9) y walk-forward OOS > 1 en todos los folds. Detalle: pre-registro.

## Estado
- [x] estructura y tests (datos sinteticos)
- [x] parametros confirmados y pre-registro firmado (2026-10-09)
- [ ] Fase 0: estudio de eventos
- [ ] backtest (US100, luego NQ proxy)
- [ ] walk-forward
- [ ] placebos
- [ ] robustez (rejilla + excluir cada anio + costos x2)
- [ ] veredicto en `docs/RESULTADO_US100_ORB.md`
