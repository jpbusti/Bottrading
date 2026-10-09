# US100 v1 (H1 ORB, H2 VWAP, H3 PDH/PDL, H4 area de valor) - LEGADO, NINGUNA APROBADA

CFD USTEC (IC Markets demo), velas 1m desde 2018, ventana 8-12 Colombia (09:45-11:59 ET). Pre-registro: `docs/PREREGISTRO_US100_V1.md`. Resultado: `docs/RESULTADO_US100_V1.md`.
Resultados: `resultados/us100_v1/`. Estado: **ninguna de las 4 hipotesis aprobada**. Congelada. (Antes se llamaba `scripts/us100/`.)

## Como correr
```powershell
python scripts/us100_v1/run_us100.py     # requiere data/raw/us100/USTEC_ICMarkets_demo_1m.csv
python -m pytest tests/test_us100_v1.py
```
## Estandar
Legado: `config.yaml` (constantes de ventana/datos/costos, vigiladas por `tests/test_config_legado.py`). Siguen en `senal()` [VERIFICAR] los umbrales de cada hipotesis (0.10-0.60 ATR del OR, 0.15/0.50 ATR de offset/tope, 0.20 ATR de desvio VWAP, area de valor 70%).
La estrategia nueva con estandar completo es `scripts/us100_orb/`.

## Checklist
- [x] pre-registro  - [x] backtest  - [x] placebos  - [x] robustez  - [x] veredicto: ninguna aprobada
