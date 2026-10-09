# Trading Lab: validacion de estrategias en CFDs (US100, luego XAUUSD y BTCUSD)

Laboratorio de backtesting con validacion estricta (costos por instrumento, walk-forward, placebos, IC90 del PF).
Instrumento principal: **US100** (CFD USTEC de IC Markets; NQ como proxy/respaldo). Proximos: XAUUSD y BTCUSD.

## Estructura
```
.
├── validacion/        # motor comun (pf_inference, walkforward, placebo, atr_grid, cost_model, event_study). No importa de scripts/
├── scripts/
│   ├── us100_orb/     # estrategia nueva con el estandar completo (plantilla)
│   ├── us100_v1/  lsr/  g2/    # estudios legado cerrados (reproducibles)
│   ├── _comun/        # cargador de config.yaml
│   ├── descarga/      # exportar_mt5_barras.py, descargadores Databento
│   └── _archivo/      # obsoleto conservado
├── docs/              # PREREGISTRO_*, RESULTADO_*, ESTANDAR_ESTRATEGIA.md, informes/, planes/
├── data/raw/{us100,nq,es,xauusd,btcusd}/    # CSV grandes, ignorados por git
├── data/processed/    # pkl regenerables (ignorados)
├── resultados/<estrategia>/
└── tests/
```

## Correr un backtest
```powershell
pip install -r requirements.txt
python -m pytest tests
python scripts/<estrategia>/run_backtest.py     # p.ej. us100_orb, SOLO tras firmar su pre-registro
```
Cada backtest reporta PF neto, IC90 inferior del PF, numero de trades, max drawdown y robustez (rejilla + sensibilidad temporal).

## Anadir una estrategia nueva
1. Leer `docs/ESTANDAR_ESTRATEGIA.md` y copiar `scripts/us100_orb/` a `scripts/<nombre>/`.
2. Poner todos los parametros en `config.yaml` (lo no confirmado, `[VERIFICAR]`).
3. Escribir `docs/PREREGISTRO_<NOMBRE>.md` y commitearlo ANTES de correr nada.
4. Implementar `strategy.py` (solo senales) y `tests/test_<nombre>.py`; correr backtest, walk-forward y placebos.
5. Publicar `docs/RESULTADO_<NOMBRE>.md`. Para otro instrumento: costos verificados en `validacion/cost_model.py` y datos en `data/raw/<instrumento>/`.

## Estado de las estrategias
| Estrategia | Estado | Documentos |
|---|---|---|
| LSR v1 (NQ/ES) | rechazada | `docs/PREREGISTRO_LSR_V1.md`, `docs/RESULTADO_LSR_V1.md` |
| G2 (NQ/ES) | no aprobada | `docs/PREREGISTRO_G2_VALIDACION.md`, `docs/RESULTADO_G2_VALIDACION.md` |
| US100 v1 (4 hipotesis) | ninguna aprobada | `docs/PREREGISTRO_US100_V1.md`, `docs/RESULTADO_US100_V1.md` |
| US100 ORB filtrado | estructura lista, pre-registro pendiente de firma, sin backtest | `docs/PREREGISTRO_US100_ORB.md` |
Aprobadas: ninguna. Regla: nada de dinero real sin pasar los criterios.

Estandar: [docs/ESTANDAR_ESTRATEGIA.md](docs/ESTANDAR_ESTRATEGIA.md). Auditoria de estructura: `docs/informes/AUDITORIA_ESTRUCTURA_2026-10-09.md`.
Claves API (Databento) solo por variable de entorno, nunca en el codigo. Backup previo a la reorganizacion: tag `backup-pre-reorg-2026-10-09`.
