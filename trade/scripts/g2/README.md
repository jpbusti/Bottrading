# G2 (barrido + retest + VWAP, regla congelada) - LEGADO, NO APROBADA

Valida la regla del marco de subastas (`scripts/_archivo/marco_subastas/`) con niveles del contrato operado y escala por ATR/%. Pre-registro: `docs/PREREGISTRO_G2_VALIDACION.md`. Resultado: `docs/RESULTADO_G2_VALIDACION.md`.
Estado: **no aprobada** (PF 0.76-0.94 fuera de muestra con costos). Congelada.

## Como correr
```powershell
python scripts/g2/extraer_contratos.py     # .zst -> data/processed/{NQ,ES}_contratos_rth.pkl
python scripts/g2/control_test.py          # control: debe dar n=172, PF 1.629
python scripts/g2/run_validacion.py        # resultados en resultados/g2/
```
Verificado el 2026-10-09: `control_test.py` reproduce n=172, win 54.07, PF 1.629.

## Estandar
Legado: `config.yaml` (constantes del motor, vigiladas por `tests/test_config_legado.py`). Siguen en codigo [VERIFICAR]: costos y rangos de fechas por instrumento en `run_validacion.py`, umbrales de criterios.

## Checklist
- [x] pre-registro  - [x] backtest  - [x] walk-forward/sensibilidades  - [x] control  - [x] veredicto: no aprobada
