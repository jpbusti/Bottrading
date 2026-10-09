# Trading Lab: CFDs (US100, luego XAUUSD y BTCUSD)

Laboratorio de validacion de estrategias intradia. Instrumento principal: **US100** (CFD `USTEC` de IC Markets; NQ como respaldo).
Proximos: XAUUSD y BTCUSD. NQ/ES se conservan solo como estudios cerrados (LSR v1, G2) y como datos de respaldo.

## Estado
- LSR v1: rechazada. G2: no aprobada. US100 v1 (H1 ORB, H2 VWAP, H3 PDH/PDL, H4 area de valor): ninguna hipotesis aprobada.
  Detalle en `docs/informes/`.

## Estructura
```
.
├── validacion/             # motor de validacion comun: cost_model (NQ/ES + CFD), pf_inference (IC90), placebo, walkforward, atr_grid
├── scripts/
│   ├── us100/              # motor_us100.py + run_us100.py (plantilla para otro instrumento)
│   ├── lsr/  g2/           # estudios cerrados NQ/ES (reproducibles)
│   ├── descarga/           # exportar_mt5_barras.py (MT5, solo lectura), descargadores Databento
│   └── calidad_datos.py
├── docs/
│   ├── preregistros/       # PREREGISTRO_* (se escriben ANTES de correr)
│   ├── informes/           # RESULTADO_*, auditorias
│   └── planes/             # PLAN_OPERATIVO, PLAN_MERCADOS
├── data/raw/{us100,nq,es,xauusd,btcusd}/   # CSV grandes: ignorados por git
├── data/processed/         # pkl regenerables (ignorados)
├── resultados/{us100,lsr,g2,xauusd,btcusd}/
├── tests/
└── archivo/                # material cerrado/obsoleto conservado (marco_subastas, docs viejos)
```

## Sumar un instrumento nuevo (XAUUSD, BTCUSD)
1. Exportar barras 1m: `python scripts/descarga/exportar_mt5_barras.py` -> `data/raw/<instrumento>/`.
2. Anadir sus costos verificados al cost_model CFD (`validacion/cost_model.py`); no inventar costos.
3. Escribir `docs/preregistros/PREREGISTRO_<INSTR>_V1.md` y commitearlo antes de correr nada.
4. Copiar `scripts/us100/` a `scripts/<instr>/` adaptando sesion/horario; resultados en `resultados/<instr>/`.
5. Aprobacion solo con placebo, walk-forward multi-fold e IC90 inferior del PF > 1.0, con costos por ano.

## Uso
```powershell
pip install -r requirements.txt
python -m pytest tests
python scripts/us100/run_us100.py     # requiere data/raw/us100/USTEC_ICMarkets_demo_1m.csv
```
Claves API (Databento) solo por variable de entorno, nunca en el codigo.

## Backup previo a esta reorganizacion
Tag `backup-pre-reorg-2026-10-09` y rama `backup/pre-reorg-2026-10-09` (codigo); el motor original NQ/ES (`main.py`, `src/`) se recupera de ahi.
