# Plan de mercados — actualizado 2026-10-09

Aclaración del usuario: la operativa real es **CFD sobre índices/commodities/cripto**, no futuros NQ/ES. El trabajo hecho (LSR v1, G2, `validacion/`) **se conserva**: NQ sigue siendo el **proxy de backtest** del US100 (niveles y patrones prácticamente iguales; **[VERIFICAR]** con una comparación de series cuando haya datos del CFD).

## Prioridades

| # | Instrumento (CFD) | Proxy de backtest | Estado de datos |
|---|---|---|---|
| 1 | **US100 Cash** (Nasdaq-100) | NQ (Databento c.0) | 10 años RTH + 1 año ETH (ver `AUDITORIA_DATOS_2026-10-09.md`) |
| 2 | **XAUUSD** (oro) | GC (futuros CME) | Sin datos en el proyecto |
| 3 | **BTCUSD** (Bitcoin) | BTC/MBT (CME) | Sin datos en el proyecto |

Los CFD de XAUUSD y BTCUSD **no se trabajan** hasta que US100 tenga un resultado validado (prioridad 1 primero). Para ellos no se descarga nada todavía.

## Brókers

- **Objetivo (principal): IC Markets.** Alternativo: **Pepperstone**.
- **Actual: XM** — solo como referencia de comparación de costos, no para operar.
- Plan de migración: XM (demo actual) → IC Markets (demo) → IC Markets (real).

Razones aportadas por el usuario para preferir IC Markets sobre XM. Ninguna fue contrastada por mí: todas **[VERIFICAR]** en las páginas oficiales / reguladores antes de depositar:
- Spread US100 más ajustado: 1.0-1.5 pts frente a 1.5-2.5 en XM **[VERIFICAR con spreads observados en demo, a distintas horas]**.
- Regulación ASIC (Australia) considerada más sólida que CySEC **[VERIFICAR: entidad que te contrata según tu país, y qué protección aplica]**.
- Ejecución ECN más rápida **[VERIFICAR: medir latencia/slippage en demo]**.
- Mejor integración con cTrader, MT5 y API **[VERIFICAR]**.
- Acepta clientes de Colombia **[VERIFICAR con el bróker: el registro depende de la entidad del grupo asignada]**.

## Capital

- Capital mínimo real: **USD 200** (CFD permiten lotes pequeños; 0.01-0.05 lotes). Con 200 dólares el costo fijo del spread pesa mucho en % del riesgo por trade: ver costos en `validacion/cost_model.py` (modo "cfd").

## Costos (modo "cfd" en `validacion/cost_model.py`)

Valores dictados por el usuario, todos **[VERIFICAR CON IC MARKETS / PEPPERSTONE]**; tabla separada de futuros:

| Instrumento | IC Markets (spread) | Pepperstone | XM | Comisión | Swap |
|---|---|---|---|---|---|
| US100 Cash | 1.0-1.5 pts | sin dato | 1.5-2.5 pts | $0 (Standard) | sin cifra ("si aplica") |
| XAUUSD | 0.15-0.30 pts | sin dato | sin dato | $0 | sin cifra |
| BTCUSD | 10-50 pts (variable) | sin dato | sin dato | $0 | sin cifra |

Qué asumí y qué no (ver la cabecera del código):
- El backtest usa por defecto el **extremo alto** del spread (conservador).
- **No hay historia de spread por año**: aplicar el spread actual a 2016-2021 es optimista **[VERIFICAR]**.
- Slippage CFD **no dictado**: 0 por defecto y el resultado lo marca `slippage_modelado=False`. Un backtest serio debe pasar `slippage_pts_lado`.
- Valor del punto por lote (US100 $1/pt, XAUUSD $100/pt, BTCUSD $1/pt) es especificación típica, **no dictada** → **[VERIFICAR en la ficha del bróker]**; si el US100 del bróker es $10/pt por lote, los tamaños de lote del plan operativo cambian.
- Pepperstone y XM sin cifras → la función falla en vez de inventar (se puede pasar `spread_pts=` con un spread observado).

## Qué NO se hace ahora

No se descargan datos CME nuevos, no se configura IBKR, no se compra nada. Las tablas IBKR de futuros se mantienen aparte por si el backtest en NQ necesita costos de futuros como control.
