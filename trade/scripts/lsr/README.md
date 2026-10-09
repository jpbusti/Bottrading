# LSR v1 (Liquidity Sweep Reversal) - LEGADO, RECHAZADA

Barrido de PDH/PDL del contrato operado + reclaim; NQ y ES, bloques A (RTH) y B (premercado). Pre-registro: `docs/PREREGISTRO_LSR_V1.md`. Resultado: `docs/RESULTADO_LSR_V1.md`.
Estado: **rechazada** (WF-OOS sin criterios cumplidos; veredicto NQ y ES = False). Congelada.

## Como correr (reproduce el log y los trades de `resultados/lsr/`)
```powershell
python scripts/lsr/run_lsr.py data/processed/lsr resultados/lsr     # requiere NQ_contratos_ext.pkl y ES_contratos_ext.pkl en la carpeta
python scripts/lsr/run_placebos.py data/processed/lsr resultados/lsr NQ
```
Verificado el 2026-10-09 tras la reorganizacion: `run_lsr.py` produce `trades_{NQ,ES}_{A,B}.csv` identicos y un `resultado_lsr.log` identico a los versionados.

## Estandar
Legado: `config.yaml` (referencia vigilada por `tests/test_config_legado.py`) y este README. El motor (`motor_lsr.py`) no se partio en strategy/run_* para no alterar la reproduccion.
Parametros que siguen en el codigo (marcados [VERIFICAR] para una migracion futura): ventanas horarias de los bloques A/B, umbral de volumen 1.5x/20 velas, fechas FOMC, costos congelados `TABLA_LSR_V1`.

## Checklist
- [x] pre-registro  - [x] backtest  - [x] walk-forward  - [x] placebos  - [x] robustez  - [x] veredicto: rechazada
