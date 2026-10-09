# Pre-registro: US100 PDH/PDL, reversion en la sesion de Nueva York

- **Fecha de redaccion:** 2026-10-09, ANTES de correr cualquier backtest (este archivo y `config.yaml` se commitean antes de ejecutar).
- **Origen:** Juan pidio probar la idea "al abrir Nueva York, marcar maximo y minimo del dia anterior, ver hacia donde apunta el precio al tocarlos, SL/TP por metricas, vender en el maximo y comprar en el minimo", y delego en Claude la eleccion de las metricas (hilo del proyecto, 2026-10-09). Los parametros de abajo son esa eleccion y quedan fijos: no se cambian despues de ver resultados.
- **Antecedente (solo contexto, no veredicto):** un analisis previo de PDH/PDL en NQ con 60 dias de yfinance y 1 ano de Databento no encontro edge (PF OOS marginal, sobreajuste, grid de 210 combos). Este estudio usa datos nuevos (2018-2026), una rejilla de solo 9 puntos y validacion completa.

## Hipotesis
Cuando el precio toca el maximo (PDH) o minimo (PDL) de la sesion RTH anterior durante la sesion de NY y la barra cierra de vuelta del lado de rechazo, el precio revierte lo suficiente como para dar expectativa neta positiva despues de costos.

## Logica de mercado
PDH/PDL concentran stops y ordenes de ruptura. Si el precio los barre y se rechaza, los que compraron la ruptura quedan atrapados y alimentan la reversion (quien esta al otro lado son los traders de ruptura). En un indice mean-reverting intradia esto podria pagar; si en cambio el nivel es solo una linea sin informacion, los placebos de nivel lo mostraran.

## Reglas exactas (identicas a `scripts/us100_pdhpdl/config.yaml`)
| Elemento | Regla |
|---|---|
| Datos | US100: `USTEC_1m_clean_2018_2026.csv` (CFD IC Markets, hora ET) agregado a 5m dentro de RTH 09:30-16:00. NQ front-month v2 (desde 2016) como proxy secundario (`--fuente nq`); el US100 es el resultado primario |
| Niveles | PDH = maximo y PDL = minimo de la sesion RTH del dia habil anterior (solo dias con >= 70% de las barras) |
| Toque | primera barra 5m del dia, de 09:30 a 15:00 inclusive, con `high >= PDH` (corto) o `low <= PDL` (largo). Cada nivel se evalua una sola vez por dia (primer toque) |
| Reaccion (rechazo) | la barra del primer toque debe CERRAR del lado de rechazo: `close < PDH` (corto) / `close > PDL` (largo). Si cierra mas alla del nivel (ruptura), ese nivel no se opera ese dia |
| Entrada | apertura de la barra siguiente a la barra de senal. Hasta un trade por nivel y dia (maximo 2 por dia, uno corto en PDH y uno largo en PDL) |
| ATR | ATR(14) diario RTH con datos hasta D-1 |
| SL / TP | SL = k x ATR, TP = m x ATR, desde el precio de entrada. Si SL y TP tocan en la misma barra cuenta SL. Salida forzada al cierre de la barra de 15:55 |
| Costos | spread 1.5 (maximo IC Markets) + slippage 0.5 por lado = 2.5 pts por trade; estres con spread 3.0. Sensibilidad por anio con el spread mediano observado en el CSV (09:30-16:00) de cada anio. Comision 0 (cuenta Standard). `cost_model` no tiene historico por anio, por eso la sensibilidad por anio se calcula con el spread observado |
| Riesgo | R = (pnl - costo) / SL. Max DD en % = DD en R x 0.5% de riesgo por trade [VERIFICAR] |

## Rejilla de parametros (robustez, NO selecciona el parametro final)
k (SL) en {0.5, 0.75, 1.0} x m (TP) en {0.5, 0.75, 1.0} = 9 puntos. Combo central (0.75, 0.75) (relacion 1:1, sin asumir asimetria). Variaciones de senal, de a una: ultima entrada {14:00, 15:00, 15:30}; con y sin condicion de rechazo.

## Criterio de aprobacion (todos, combo central salvo donde se indica; resultado primario = US100)
1. PF neto >= 1.15.
2. IC90 inferior del PF (bootstrap por dia) > 1.0.
3. >= 300 trades.
4. Max drawdown < 20% (DD en R x 0.5%).
5. Supera los tres placebos: nivel (PDH/PDL de hace 2, 3, 5 y 10 dias; el PF real debe superarlos a todos), timing aleatorio (200 sorteos, p <= 0.05), direccion invertida (re-simulada; el PF real debe superarla).
6. Rejilla: los 9 puntos con PF >= 1.15 e IC90 inferior > 1.0.
7. Walk-forward expansivo por anio (2019 en adelante, min 30 trades de entrenamiento): PF OOS > 1 en todos los folds e IC90 inferior del PF OOS agrupado > 1.0.
8. Sensibilidad temporal: excluir cada anio no cambia el PF mas de 0.05 ni lo hace depender de un solo anio. Con spread 3.0 el PF sigue > 1 y con el spread por anio no cambia la conclusion.

NQ proxy: informativo; no puede aprobar una estrategia que falle en US100.

## Reglas de proceso
Sin cambios de parametros despues de ver resultados. El resultado negativo se publica igual en `docs/RESULTADO_US100_PDHPDL.md`. `validacion/` se usa sin modificarlo.
