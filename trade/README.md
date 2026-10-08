# NQ / ES Trading Lab

Laboratorio de backtesting intradia para NQ (Nasdaq-100) y ES (S&P 500) con datos de Databento.
Dos capas:

1. **Motor original** (`main.py` + `src/`): estrategias PDH/PDL, ORB y VWAP con filtros (ATR, VWAP, RSI, Bollinger),
   simulacion vela a vela y walk-forward IS/OOS.
2. **Marco de subastas + validacion G2** (`scripts/marco_subastas/`, `scripts/g2/`): barrido de niveles
   (PDH/PDL/VAH/VAL/POC) con filtro VWAP, probado en 1m con costos, normalizacion por ATR/% y niveles del
   contrato realmente operado.

## Estado (2026-10-08)
- Gate **G2 NO aprobado** para la regla congelada (barrido + retest + VWAP, SL 80 / TP 110): PF 0.76-0.94 fuera de muestra
  en NQ 2016-2021 y ES 2016-2025, con costos. Detalle: `resultados/g2/` y los docs del Project (PREREGISTRO_G2_VALIDACION,
  RESULTADO_G2_VALIDACION).
- El PF 1.6-1.7 del ultimo ano de NQ no se replica en ningun otro periodo ni instrumento.

## Estructura

```
.
├── main.py                      # motor original: estrategias x filtros x parametros
├── requirements.txt
├── config/config.py             # rutas, ticker, intervalo, grids
├── src/                         # motor original reutilizable
│   ├── datos.py  indicadores.py
│   ├── motor/motor_estrategias.py
│   └── estrategias/{base,pdh_pdl,orb,vwap,filtros}.py
├── scripts/
│   ├── pdh_pdl_lab.py           # laboratorio original (lo importan main.py y src/)
│   ├── pdh_pdl_mt5_explorer.py
│   ├── marco_subastas/          # marco de subastas (1m): marco_subastas, stop_amplio, contexto_salidas
│   ├── g2/                      # validacion G2 pre-registrada
│   │   ├── extraer_contratos.py #   .zst crudos -> velas RTH por contrato (data/processed/*.pkl)
│   │   ├── motor_g2.py          #   motor: niveles del contrato operado, escala ATR/%, estadistica
│   │   ├── run_validacion.py    #   corre criterios, sensibilidades, Monte Carlo
│   │   └── control_test.py      #   el motor debe reproducir n=172, PF 1.629 del script original
│   └── descarga/                # descargadores Databento (tramos, reintentos, tope de costo)
├── data/
│   ├── raw/
│   │   ├── NQ_databento_1m_10y_RTH.csv.gz   # NQ 2016-10 -> 2026-10, RTH, continuo sin ajustar
│   │   ├── ES_databento_1m_10y_RTH.csv.gz   # ES 2016-10 -> 2026-10, RTH, continuo sin ajustar
│   │   ├── NQ_databento_1m.csv              # NQ ultimo ano con premercado (unico con Globex)
│   │   ├── NQ_1d.csv  NQ_1h.csv             # yfinance (los usa main.py)
│   │   ├── databento_crudo/*.zst            # FUENTE por contrato (pagada): no borrar
│   │   └── calidad/                         # rolls y reporte de calidad (G1)
│   └── processed/                           # pkl por contrato (regenerables)
├── resultados/{csv,png,reportes,g2}/
├── tests/                       # pytest
└── notebooks/
```

## Datos
- Horas en `America/New_York`, solo 09:30-16:00. Leer con `pd.read_csv("archivo.csv.gz", index_col=0)`.
- **NQ**: 2016-10-10 -> 2021-10-08 sale de los `.zst` (contrato de mayor volumen del dia anterior); desde 2021-10-08 es
  `NQ.c.0` (rolls por calendario). Son series continuas SIN ajustar: en cada roll hay un salto de precio (en NQ ~ +58 pts de media).
  El dia solapado (2021-10-08) coincide vela por vela entre ambas fuentes.
- **ES**: 2016-10-10 -> 2026-10-07 construido desde el `.zst` con la misma regla.
- Para backtests serios usa los `.zst` (por contrato) via `scripts/g2/extraer_contratos.py`: los niveles se calculan con el mismo
  contrato que se opera, sin saltos de roll.

## Uso (desde la raiz, PowerShell)
```powershell
pip install -r requirements.txt
python -m pytest tests                          # tests del motor original
python main.py --intervalo 1h                   # motor original con data/raw/NQ_1h.csv

# Validacion G2 (reproducible)
python scripts/g2/extraer_contratos.py          # .zst -> data/processed/{NQ,ES}_contratos_rth.pkl
python scripts/g2/control_test.py               # control: debe dar n=172, PF 1.629
python scripts/g2/run_validacion.py             # resultados en resultados/g2/
```
Descarga de datos nuevos (requiere `$env:DATABENTO_API_KEY`, nunca en el codigo):
`python scripts/descarga/descargar_validacion.py` (muestra el costo y pide `SI`).

## Reglas del proyecto
- Costos siempre incluidos; cero look-ahead (todo con datos hasta el cierre de D-1); regla pre-registrada antes de mirar datos nuevos.
- Una regla no se aprueba por su mejor ano: se exige expectativa neta con IC90 > 0, PF >= 1.15, estabilidad por ano y vs placebo.
- Nada de dinero real sin pasar los gates; el marco PDH/PDL queda como herramienta visual hasta aprobar G2.

## Changelog
- **2026-10-08 (2)**: datos NQ unidos en un solo archivo; ES igual; fuente por contrato en `databento_crudo/`; scripts de
  descarga/analisis consolidados; obsoletos apartados en `_por_borrar/`; validacion G2 (no aprobada).
- **2026-10-08 (1)**: reorganizacion inicial en `config/`, `src/`, `scripts/`, `tests/` (logica sin cambios).
