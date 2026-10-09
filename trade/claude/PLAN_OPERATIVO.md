# Plan operativo — actualizado 2026-10-09

Parámetros dictados por el usuario. Lo que no pude comprobar va como **[VERIFICAR]**.

| Parámetro | Valor |
|---|---|
| Instrumento real | **US100 Cash (CFD)** |
| Bróker objetivo | **IC Markets** (principal) / **Pepperstone** (alternativo). XM solo como referencia. |
| Capital demo | USD 200-500 |
| Capital real inicial | USD 200 |
| Tamaño | 0.01-0.05 lotes |
| Riesgo por trade | 1-2 % = USD 2-4 |
| Duración demo | 3-6 meses |
| Muestra mínima | 50-100 trades |
| Criterio para pasar a real | PF demo ≥ 1.10, drawdown controlado, disciplina |
| Instrumentos de expansión | XAUUSD, BTCUSD |

## Migración

XM (demo actual) → IC Markets (demo) → IC Markets (real). No se opera real hasta cumplir el criterio de arriba en la demo de IC Markets.

## Consistencia del tamaño con el riesgo **[VERIFICAR]**

Riesgo USD 2-4 con 0.01-0.05 lotes solo es coherente si 1 lote de US100 = USD 1 por punto (supuesto de `cost_model.py`, **no verificado**). En ese caso, con 0.05 lotes el stop máximo es 2/0.05 ≈ 40 pts a 4/0.05 = 80 pts; con 0.01 lotes, 200-400 pts. Si el bróker define 1 lote = USD 10/pt, los stops de 40 pts con 0.05 lotes serían USD 20 de riesgo (10 % de USD 200) y hay que bajar el lote. Confirmar en la ficha del bróker antes de operar.

Regla práctica: el spread (1.0-1.5 pts en IC Markets según el usuario) se resta en cada trade; un stop corto lo hace pesar mucho en R. El backtest debe incluirlo como costo en puntos (modo "cfd").

## Criterios de la demo (para no engañarse)

- **PF ≥ 1.10 con 50-100 trades no demuestra edge**: con esa muestra el IC90 del PF es muy ancho. La demo sirve para validar ejecución, costos reales (spread y slippage observados) y disciplina; la decisión estadística sigue siendo el backtest con IC90 inferior > 1.0, placebo y walk-forward.
- Registrar por trade: hora, spread al entrar, precio solicitado vs ejecutado, motivo, R. Estos datos recalibran `cost_model.py` (modo "cfd": `spread_pts`, `slippage_pts_lado`, swaps).
- Todo criterio se fija **antes** de empezar la demo (pre-registro).

## Dependencias abiertas

1. Costos CFD reales (spread por hora, swap, valor del punto) — **[VERIFICAR CON IC MARKETS / PEPPERSTONE]**.
2. Disponibilidad para clientes de Colombia — **[VERIFICAR con el bróker]**.
3. Pre-registro del plan Auction Market Theory (PDH/PDL + VAH/VAL + POC + AVWAP) y su viabilidad con los datos actuales: ver `AUDITORIA_DATOS_2026-10-09.md` §7-8.
