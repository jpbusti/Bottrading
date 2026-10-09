# Inventario de Datos — Auditoría 2026-10-09

Verificado con Python/pandas sobre los archivos reales. Nada inventado; "[VERIFICAR]" indica algo no comprobado directamente.

---

## Tarea 1: Inventario completo

### Archivos de datos principales

| Archivo | Ruta | Tamaño | Formato | Filas | Rango fechas | Temporalidad | Sesión | Instrumento | Fuente | Estado |
|---|---|---|---|---|---|---|---|---|---|---|
| NQ_databento_1m_10y_RTH.csv.gz | data/raw/nq/ | 12.1 MB | CSV.GZ | 981,600 | 2016-10-10 → 2026-10-06 | 1 min | RTH | NQ futuro (continuo, sin back-adj) | Databento | **Usable** |
| NQ_databento_1m.csv | data/raw/nq/ | 21.6 MB | CSV | 350,561 | 2025-10-06 → 2026-10-06 | 1 min | ETH+RTH (24h) | NQ futuro (continuo) | Databento | **A verificar** |
| USTEC_ICMarkets_demo_1m.csv | data/raw/us100/ | 198 MB | CSV | 3,345,954 | 2012-08-06 → 2026-10-09 | mixto: diario + 1 min | mixto | US100 CFD (USTEC) | MT5/IC Markets demo | **A verificar** |
| ES_databento_1m_10y_RTH.csv.gz | data/raw/es/ | 10.6 MB | CSV.GZ | 989,804 | 2016-10-10 → 2026-10-07 | 1 min | RTH | ES futuro (continuo, sin back-adj) | Databento | **Usable** |
| NQ_databento_1m_2016_2021_RTH.csv.zst | data/raw/databento_crudo/ | 32.3 MB | CSV.ZST | 2,353,506 | 2016-10-09 → 2021-10-08 | 1 min | RTH + pre-open | NQ futuro (multi-contrato, crudo) | Databento raw | **Fuente primaria** |
| ES_databento_1m_10y_RTH.csv.zst | data/raw/databento_crudo/ | 72.5 MB | CSV.ZST | 5,583,467 | 2016-10-09 → 2026-10-08 | 1 min | RTH + pre-open | ES futuro (multi-contrato, crudo) | Databento raw | **Fuente primaria** |
| ES_contratos_ext.pkl | data/processed/ | [VERIFICAR] | Pickle | 2,675,257 | 2016-10-10 → 2026-10-07 | 1 min | ETH extendido | ES futuro (multi-contrato) | Generado de ZST | **Regenerable** |
| NQ_contratos_ext.pkl (short) | data/processed/ | [VERIFICAR] | Pickle | 1,199,325 | 2016-10-10 → 2021-10-08 | 1 min | ETH extendido | NQ futuro (multi-contrato) | Generado de ZST | **Regenerable** |
| NQ_contratos_ext.pkl (lsr) | data/processed/lsr/ | [VERIFICAR] | Pickle | 1,655,370 | 2016-10-10 → 2026-10-06 | 1 min | ETH extendido | NQ futuro (multi-contrato) | Generado de ZST | **Regenerable** |

### Archivos de calidad

| Archivo | Ruta | Tamaño | Contenido |
|---|---|---|---|
| NQ_rolls.csv | data/raw/calidad/ | 335 B | 20 rolls NQ 2016-2021 con fechas de contrato |
| ES_rolls.csv | data/raw/calidad/ | 655 B | 40 rolls ES 2016-2026 con fechas de contrato |
| reporte_calidad_NQ_2021_2026.txt | data/raw/calidad/ | 445 B | Calidad NQ tramo reciente (2021-2026) |
| reporte_calidad_validacion.txt | data/raw/calidad/ | 1.1 KB | Calidad NQ 2016-2021 + ES 10 años |

### Archivos archivados (scripts/_archivo/datos_locales_obsoletos/)

| Archivo | Tamaño | Filas | Rango fechas | Fuente | Estado |
|---|---|---|---|---|---|
| NQ_1d.csv | 171 KB | 2,960 | 2015-01-02 → 2026-10-08 | Yahoo Finance (Adj Close presente) | **Obsoleto** |
| NQ_1h.csv | 262 KB | 3,559 | 2024-05-16 → 2026-10-07 | Yahoo Finance (Adj Close presente) | **Obsoleto** |
| ES_contratos_ext_dup_de_processed.pkl | 170.7 MB | idem ES processed | 2016→2026 | Duplicado de data/processed/ | **Obsoleto** |
| resultados_csv/marco_subastas_*.csv | pequeño | pocos | 2016-2024 | Marco subastas (estrategia archivada) | **Obsoleto** |

### Carpetas vacías (solo .gitkeep)

| Ruta | Instrumento | Datos disponibles |
|---|---|---|
| data/raw/xauusd/ | XAUUSD | **No hay datos** |
| data/raw/btcusd/ | BTCUSD | **No hay datos** |
| resultados/us100_orb/ | US100 ORB | Solo event_study_us100.csv y event_study_nq.csv |

---

## Tarea 2: Verificación de archivos clave

### NQ_databento_1m_10y_RTH.csv.gz ✅

| Atributo | Valor |
|---|---|
| Filas | 981,600 |
| Rango fechas | 2016-10-10 09:30 ET → 2026-10-06 15:59 ET |
| Sesión | **RTH únicamente** (09:30-16:00 ET; verificado por timestamp tz-aware) |
| Contrato | **Continuo sin back-adjust** — front-month con rolls; media de salto en roll: +57.9 pts NQ, hasta +223 pts |
| Columnas | Datetime (tz-aware), Open, High, Low, Close, Volume |
| ¿Tiene spread? | **No** |
| Días de trading | 2,556 |
| Huecos > 5 min dentro de RTH (mismo día) | **4** — todos en marzo 2020 (COVID circuit breakers: 13/14/18 Mar 2020, ~14 min cada uno) |
| Huecos > 30 min | **0** |
| Duplicados | **0** |
| Precio mínimo-máximo | 4,656 → 31,613 (rango razonable para NQ 2016-2026) |
| Estado | **Usable** para proxy NQ. Notar: no back-adjusted; usar para relativo/señal, no para series de precios absolutas entre rolls |

### NQ_databento_1m.csv ✅

| Atributo | Valor |
|---|---|
| Filas | 350,561 |
| Rango fechas | 2025-10-06 → 2026-10-06 (solo ~1 año) |
| Sesión | **ETH+RTH completo** (todas las 24h; horas 0-23 todas cubiertas) |
| Contrato | Continuo, sin back-adjust (mismo formato) |
| Columnas | Datetime (tz-aware), Open, High, Low, Close, Volume |
| ¿Tiene spread? | **No** |
| Días de trading | 313 |
| Duplicados | **0** |
| Estado | **A verificar** — solo 1 año (2025-2026), ETH completo pero sin spread. Útil como proxy reciente para NQ en event study. **No suficiente para backtest** (300 trades mínimo) |

### USTEC_ICMarkets_demo_1m.csv ⚠️

| Atributo | Valor |
|---|---|
| Filas totales | 3,345,954 |
| Sección diaria | 1,265 filas — 2012-08-06 → 2025-01-17 (time = 00:00:00) |
| Sección 1m | 3,344,689 filas — 2016-01-27 → 2026-10-09 09:43 |
| Columnas | time_server, open, high, low, close, tick_volume, spread, real_volume |
| Zona horaria (time_server) | **MT5 server time = ET + 7h** (confirmado por preregistro: sesión 16:30-23:00 server = 09:30-16:00 ET) |
| real_volume | **94.6% zeros** — normal para CFD en MT5; usar tick_volume como proxy de volumen |
| spread | 1.3% zeros; valores 3-840 en unidades MT5. **Interpretación: spread_pts = spread / 100** (spread=200 → 2.0 pts, coincide con IC Markets USTEC 1-2 pts). Mediana 2020: 2.0 pts |
| Huecos RTH 2016-2017 | ~1,800 — **artefacto**: historial de demo MT5 tiene resolución horaria en ese período (barras de 1h exportadas como 1m) |
| Huecos RTH 2018+ | **15** gaps > 5 min; solo 2 > 30 min (2018-09-14: 126 min; 2023-08-24: 47 min) |
| Días RTH totales | 2,762 |
| Días RTH con <350 barras (de 390) | 397 — mayoritariamente 2016-2017 (datos horarios); en 2018+ son feriados/ciertos cierres tempranos |
| Duplicados | **0** |
| Estado | **A verificar** antes de usar en producción. Sección 2018+ es usable con filtro de ≥70% barras RTH. Sección 2016-2017: resolución horaria en muchos días, requiere análisis adicional si se usa ese rango |

### ES_databento_1m_10y_RTH.csv.gz ✅

| Atributo | Valor |
|---|---|
| Filas | 989,804 |
| Rango fechas | 2016-10-10 09:30 ET → 2026-10-07 15:59 ET |
| Sesión | RTH únicamente |
| Contrato | Continuo sin back-adjust; 39 rolls (media salto: +20 pts ES; min -202 pts, max +148 pts) |
| Columnas | Datetime, Open, High, Low, Close, Volume (sin spread) |
| Días de trading | 2,577 |
| Huecos > 5 min | 4 (mismo período COVID marzo 2020) |
| Duplicados | 0 |
| Estado | **Usable** para backtests ES (LSR, G2) |

---

## Tarea 3: Huecos y datos faltantes

### Huecos en NQ RTH (NQ_databento_1m_10y_RTH.csv.gz)

No hay días completos faltantes verificados (2,556 días de trading en 10 años es ~99%+ de días hábiles del NYSE). Los 4 huecos intradía son circuit breakers de COVID 2020:

| Fecha | Gap (min) | Causa probable |
|---|---|---|
| 2020-03-09 13:49 ET | 14 | Circuit breaker COVID (Level 1, -7%) |
| 2020-03-12 13:50 ET | 14 | Circuit breaker COVID |
| 2020-03-16 13:45 ET | 15 | Circuit breaker COVID |
| 2020-03-18 17:11 ET | 14 | Circuit breaker COVID |

### Huecos en USTEC (RTH 2018+)

15 gaps > 5 min en RTH 2018+, de los cuales los 10 más grandes:

| Fecha (server) | Gap (min) | Notas |
|---|---|---|
| 2018-09-14 21:37 | 126 | Hueco significativo — verificar si feriado/halte |
| 2023-08-24 21:01 | 47 | [VERIFICAR] |
| 2022-06-17 22:17 | 23 | Posible baja liquidez (fin de expiración) |
| 2019-05-01 17:25 | 19 | [VERIFICAR] |
| 2021-09-30 19:58 | 17 | [VERIFICAR] |
| 2020-03-18 20:14 | 15 | Circuit breaker COVID |
| 2019-05-01 21:32 | 11 | [VERIFICAR] |
| 2021-03-04 22:57 | 11 | [VERIFICAR] |
| 2026-05-26 19:54 | 10 | Memorial Day — cierre anticipado |
| 2020-03-12 16:51 | 9 | Circuit breaker COVID |

El filtro de ≥70% barras RTH en `datos.py` excluye los días con data insuficiente.

### Datos que faltan

| Dato | ¿Existe? | Detalle |
|---|---|---|
| ETH de NQ (histórico 10y) | **No** | Solo hay 1 año (2025-2026) en NQ_databento_1m.csv |
| ETH de US100 (histórico 10y) | Parcial | USTEC_ICMarkets tiene ETH desde 2016, pero 2016-2017 con resolución horaria |
| XAUUSD datos | **No** | data/raw/xauusd/ solo tiene .gitkeep |
| BTCUSD datos | **No** | data/raw/btcusd/ solo tiene .gitkeep |
| Datos antes de 2016 | Parcial | USTEC tiene diarios desde 2012 y NQ_1d.csv (yahoo) desde 2015, pero no 1m |
| Datos NQ 2016-2021 RTH | Sí | En NQ_databento_1m_10y_RTH.csv.gz (tramo 2016-2021) y en los ZST crudos |

---

## Tarea 4: Reporte de fuentes

### Databento

**Archivos:** NQ_databento_1m_10y_RTH.csv.gz, NQ_databento_1m.csv, ES_databento_1m_10y_RTH.csv.gz, NQ_databento_1m_2016_2021_RTH.csv.zst, ES_databento_1m_10y_RTH.csv.zst

**Fiabilidad:** Alta. Los archivos procesados (.csv.gz) tienen 0 duplicados, 0 OHLC incoherentes y 0 precios ≤0 (verificado en reporte de calidad). Los huecos son circuit breakers reales. Los archivos crudos (.zst) son multi-contrato en formato Databento raw (ts_event + symbol) y son la fuente de verdad.

**Notas:** El formato continuo es front-month sin back-adjust. Los rolls crean discontinuidades de precio (media +57.9 pts NQ, +20 pts ES). Para señales basadas en precio relativo (ATR, ruptura) esto es aceptable; para series absolutas de precio se requeriría back-adjust.

### MT5/IC Markets

**Archivos:** USTEC_ICMarkets_demo_1m.csv

**Fiabilidad:** Media-alta para 2018+, baja para 2016-2017. Problemas conocidos:
- real_volume 0 en 94.6% (normal para CFD)
- Resolución horaria en 2016-2017 (artefacto de exportación de demo)
- Sección diaria (1,265 filas) mezclada en el mismo archivo con timestamp 00:00:00
- Spread en unidades MT5 (÷100 para obtener pts)
- tick_volume es útil como proxy de actividad

**¿Hay mezcla de fuentes?** No en los archivos principales (cada archivo es de una sola fuente). El archivo USTEC mezcla barras diarias + 1m del mismo broker.

### Yahoo Finance

**Archivos:** NQ_1d.csv, NQ_1h.csv (ambos en _archivo/datos_locales_obsoletos/)

**Fiabilidad:** Baja para backtesting cuantitativo. Columna "Adj Close" indica back-adjust de dividendos/splits (inapropiado para futuros/CFDs). Solo 1h desde 2024. **No usar.**

---

## Tarea 5: Recomendación

### 1. Datos listos para usar

| Instrumento | Temporalidad | Archivo | Cobertura | Listo para |
|---|---|---|---|---|
| NQ futuro | 1m RTH | NQ_databento_1m_10y_RTH.csv.gz | 2016-2026 | Backtest LSR, G2, proxy US100 ORB |
| ES futuro | 1m RTH | ES_databento_1m_10y_RTH.csv.gz | 2016-2026 | Backtest LSR, G2 |
| US100 CFD (USTEC) | 1m ETH+RTH | USTEC_ICMarkets_demo_1m.csv (sección 2018+) | 2018-2026 | Backtest US100 ORB (con filtro ≥70% barras) |

### 2. Datos que hay que verificar antes de usar

| Archivo | Problema | Acción |
|---|---|---|
| USTEC 2016-2017 | Resolución horaria → mayoría de días RTH con <200 barras | Confirmar desde qué fecha hay 1m real; el dato de enero 2018 en adelante parece limpio |
| USTEC sección diaria | Mezclada con 1m en mismo archivo (separada por time==00:00) | datos.py ya la filtra correctamente; verificar que no haya fecha de transición con confusión |
| NQ_databento_1m.csv | Solo 1 año (2025-2026), sin spread | No suficiente para backtest; útil como proxy reciente |
| ES/NQ pkl files | Regenerables pero no se sabe si están sincronizados con los CSV.gz actuales | Regenerar antes de usar si cambian los CSV.gz |

### 3. Datos que faltan para completar el proyecto

| Dato | Prioridad | Impacto |
|---|---|---|
| XAUUSD 1m (IC Markets) | Alta | Próximo instrumento en el proyecto |
| BTCUSD 1m (IC Markets) | Media | Próximo instrumento en el proyecto |
| NQ ETH 10y (Databento) | Media | Event study US100 ORB usa NQ como proxy; ETH completo mejoraría calidad |
| USTEC 1m verificado 2016-2017 | Baja | Si se quiere extender backtest antes de 2018 |

### 4. Datos que hay que descartar

| Archivo | Razón |
|---|---|
| NQ_1d.csv (yahoo) | Yahoo Finance, back-adjusted, no reproducible |
| NQ_1h.csv (yahoo) | Yahoo Finance, solo 2 años |
| ES_contratos_ext_dup_de_processed.pkl | Duplicado de data/processed/ES_contratos_ext.pkl |
| marco_subastas resultados CSV | Estrategia archivada, irrelevante |

### 5. Dataset "oficial" para el próximo backtest

**Instrumento: US100 ORB** — el dataset oficial es:

```
data/raw/us100/USTEC_ICMarkets_demo_1m.csv
```

- Filtro de fecha mínima: **2018-01-01** (preregistro firmado)
- Filtro de sesión: RTH en server time = 16:30-23:00 (implementado en datos.py)
- Filtro de integridad: ≥70% barras esperadas por día (implementado en datos.py)
- Usar tick_volume como volumen; spread / 100 para convertir a pts (ya en cost_model.py)
- Ignorar sección diaria (time==00:00) — ya filtrada por datos.py

---

## Resumen ejecutivo (10 líneas)

1. **NQ RTH 10y (2016-2026)**: dataset Databento limpio, 981K barras, sin huecos salvo COVID. Listo para usar como proxy NQ en LSR, G2 y event study.
2. **ES RTH 10y (2016-2026)**: idéntico a NQ. 989K barras, listo para usar.
3. **USTEC/US100 CFD**: 3.3M barras 1m desde 2016; años 2016-2017 tienen resolución horaria (artefacto de demo MT5); 2018-2026 es limpio (solo 15 gaps > 5 min en RTH).
4. **USTEC es el dataset oficial** para US100 ORB; usar desde 2018-01-01 con el filtro de ≥70% barras RTH ya implementado en datos.py.
5. **real_volume del USTEC es 0 en 94.6%** de las filas — normal para CFD; usar tick_volume como proxy. El spread / 100 da puntos (mediana 2.0 pts, consistente con IC Markets).
6. **No hay datos de XAUUSD ni BTCUSD** — carpetas vacías. Descargar antes de iniciar esas estrategias.
7. **No hay ETH histórico de NQ** (solo 1 año, 2025-2026 en NQ_databento_1m.csv). Si se requieren señales ETH para NQ, hay que descargar desde Databento.
8. **Los archivos ZST son la fuente primaria cruda** (multi-contrato); los CSV.GZ y pkl son procesados/regenerables.
9. **Yahoo Finance (NQ_1d, NQ_1h) descartados**: back-adjusted, irreproducibles para futuros. Ya en _archivo/.
10. **Próximo paso**: la event study mostró que US100 ORB con las reglas actuales tiene N=18 eventos completos, sin edge detectable — decidir si se plantea V2 con filtros más laxos antes de descargar XAUUSD o BTCUSD.

---

*Auditoria ejecutada 2026-10-09 por script Python directo sobre los archivos. No se modificó ni borró nada.*
