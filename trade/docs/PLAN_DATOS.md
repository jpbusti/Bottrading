# Plan de Datos — Proyecto Trading

**Actualizado:** 2026-10-09  
**Autor:** Juan (auditoria y reconstrucción ejecutada por Claude, sesión 2026-10-09)

---

## Instrumento operativo

**US100 CFD (IC Markets)** es el único instrumento de operativa real.  
NQ y ES son proxies para backtest solamente — ninguna estrategia se ejecuta en futuros.

---

## Datasets oficiales

### 1. US100 — dataset principal (operativa real)

| Archivo | Rango | Filas | Notas |
|---|---|---|---|
| `data/raw/us100/USTEC_1m_clean_2018_2026.csv` | 2018-01-01 → 2026-10-09 | ~3.09 M | Dataset limpio oficial |

**Origen:** IC Markets demo account, exportado desde MT5.  
**Temporalidad:** 1 minuto, session time (ET). Incluye RTH y globex.  
**Spread:** columna `Spread_pts` = spread original ÷ 100 (media ~1.50 pts; IC Markets estándar US100).  
**Volumen:** `TickVolume` (proxy de actividad); `RealVolume` = 0 en todos los registros (normal en CFD MT5).  
**Procesamiento aplicado:**
- Tramo diario (time=00:00) archivado en `data/_archivo/USTEC_daily_2012_2025.csv`
- Datos 2016-2017 descartados (resolución horaria, no 1m real)
- Timestamp convertido de server time (ET+7) a ET
- Spread dividido por 100 para obtener puntos

**Modelo de costos:** `validacion/cost_model.py` modo `cfd`, `CONTRATOS_CFD["US100"]`, 1 lote = $100/pt.

---

### 2. NQ — proxy para validación (no operativo)

| Archivo | Rango | Filas | Notas |
|---|---|---|---|
| `data/raw/nq/NQ_1m_RTH_frontmonth.csv.gz` | 2016-10-10 → 2021-10-08 | 495,425 | Front-month reconstruido |
| `data/raw/databento_crudo/NQ_databento_1m_2016_2021_RTH.csv.zst` | 2016-10-09 → 2021-10-08 | ~2.9 M | Crudo multi-contrato (fuente) |

**Origen:** Databento GLBX.MDP3, schema `ohlcv-1m`.  
**Algoritmo front-month:** por cada día se selecciona el contrato con mayor volumen total RTH.  
**Rolls detectados:** 20 rolls en 2016-2021 (trimestral CME).  
**RTH:** exactamente 09:30–15:59 ET (390 barras/día nominal).  
**Saltos en rolls:** existen (basis entre contratos); max verificado < 200 pts.

**Pendiente:** los años 2021-2026 requieren descarga desde Databento:
```
python -c "
from databento import Historical
client = Historical()  # requiere DATABENTO_API_KEY en variable de entorno
data = client.timeseries.get_range(
    dataset='GLBX.MDP3',
    symbols=['NQ.FUT'],
    schema='ohlcv-1m',
    start='2021-10-09',
    end='2026-10-07',
    stype_in='continuous',
)
data.to_csv('data/raw/databento_crudo/NQ_databento_1m_2021_2026_RTH.csv.zst')
"
```
Costo estimado: ~$12–60 USD según plan Databento (verificar en dashboard antes de descargar).

---

### 3. ES — proxy para validación cruzada (no operativo)

| Archivo | Rango | Filas | Notas |
|---|---|---|---|
| `data/raw/es/ES_1m_RTH_frontmonth.csv.gz` | 2016-10-10 → 2026-10-07 | 989,804 | Front-month reconstruido |
| `data/raw/databento_crudo/ES_databento_1m_10y_RTH.csv.zst` | 2016-10-09 → 2026-10-07 | ~5.6 M | Crudo multi-contrato (fuente) |

**Origen:** Databento GLBX.MDP3, schema `ohlcv-1m`.  
**Algoritmo front-month:** idéntico a NQ (mayor volumen por día).  
**Rolls detectados:** 40 rolls en 2016-2026 (trimestral CME).  
**RTH:** exactamente 09:30–15:59 ET.  
**Spreads de roll filtrados:** filas con símbolo conteniendo `-` excluidas del procesamiento.

---

## Archivos descartados / archivados

| Archivo | Razón | Destino |
|---|---|---|
| `USTEC_ICMarkets_demo_1m.csv` (tramo diario) | Resolución diaria mezclada con 1m | `data/_archivo/USTEC_daily_2012_2025.csv` |
| Datos USTEC 2016-2017 | Resolución horaria (6-7 barras/día en RTH) | Filtrados al limpiar, no archivados por separado |
| `NQ_databento_1m.csv` (continuo ajustado) | Reemplazado por front-month reconstruido | Conservar hasta completar 2021-2026 |
| `NQ_databento_1m_10y_RTH.csv.gz` (continuo) | Idem | Conservar como referencia |

---

## Pendientes

- [ ] Descargar NQ 2021-2026 desde Databento (ver comando arriba)
- [ ] Unir `NQ_1m_RTH_frontmonth.csv.gz` (2016-2021) + datos 2021-2026 en un único archivo 10Y
- [ ] Verificar spreads de roll ES max 132 pts en contexto de volatilidad (2020 COVID)
- [ ] Confirmar spreads y comisiones IBKR con extracto real de cuenta (toda la `TABLA_IBKR` lleva [VERIFICAR])

---

## Modelo de costos

Ver `validacion/cost_model.py` y `docs/PREREGISTRO_US100_ORB.md`.

| Instrumento | Modo | Costo RT típico |
|---|---|---|
| US100 CFD 0.01 lote | `cfd` | $2.00–2.50 (spread 1.0-1.5 pts + slip 0.5 pts × $100/pt) |
| US100 CFD 0.10 lote | `cfd` | $20.00–25.00 |
| NQ futuro 1 contrato | `futuros` | $14.30 (slip 0.50 pts × $20 + comisión $4.30) |

---

## Scripts de reconstrucción

| Script | Propósito |
|---|---|
| `scripts/descarga/reconstruir_frontmonth_nq.py` | NQ front-month desde ZST 2016-2021 |
| `scripts/descarga/reconstruir_frontmonth_es.py` | ES front-month desde ZST 2016-2026 |
| `scripts/descarga/limpiar_ustec.py` | USTEC: separar diario, filtrar 2018+, convertir spread y timezone |

---

## Precios de NQ, costos de USTEC (backtest)

- **Precios:** vienen de NQ (OHLC 1 min RTH, proxy limpio). No se opera NQ.
- **Costos:** son los de USTEC en IC Markets, modo `cfd` de `validacion/cost_model.py`: spread fijo 1.5 pts + slippage 0.5 pts RT (0.25 pts/lado) = **2.0 pts redondo** (`costo_backtest_us100`, `COSTO_BACKTEST_US100_PTS`).
- **PF real:** cada trade resta 2.0 pts de P&L bruto (en NQ-puntos, equivalente 1:1 a USTEC) antes de calcular el PF, de modo que refleja la operativa real en USTEC. A 0.01 lote cuesta $2.00 por trade; a 0.10 lote, $20.00.
- Es conservador: el spread real de IC Markets en RTH es 1.0-1.5 pts. Sigue marcado [VERIFICAR CON IC MARKETS].
