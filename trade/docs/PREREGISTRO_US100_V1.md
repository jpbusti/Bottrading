# Pre-registro US100 v1: cuatro hipótesis intradía en la ventana 8-12 Colombia (CFD USTEC, IC Markets demo)

Fecha de redacción: 2026-10-09, ANTES de correr cualquier resultado sobre estos datos. Este archivo se commitea antes del motor de pruebas.
Estado de la evidencia: nivel C. Nada de lo de abajo se modifica después de ver resultados; si se cambia algo es una versión nueva (v2) y se declara.
Lo que ya se sabía antes (transparencia): LSR v1 (barrido de PDH/PDL en NQ) fue rechazada; G2 (barrido+VWAP) dio PF ≈ 1.02-1.03 con IC90 incluyendo 0 en NQ 2021-25. Ambas tuvieron sus propios criterios; aquí se prueban reglas distintas y simples, sin optimizar.

## 1. Datos y horario
- Fuente: `data/raw/us100/USTEC_ICMarkets_demo_1m.csv` (velas de 1 minuto del CFD USTEC, demo de IC Markets). Periodo: **2018-01-01 → 2026-10-08**. Antes de 2018 no hay datos 1m completos.
- Hora del servidor = hora de Nueva York + 7 (verificado contra NQ en 8 periodos de invierno y verano). Todo se convierte a ET.
- Volumen = `tick_volume` (conteo de cambios de precio del CFD; proxy del volumen real) [VERIFICAR su relación con el volumen del futuro].
- Sesión RTH = 09:30-16:00 ET. ATR14 = promedio del rango (máx-mín) RTH de las 14 sesiones previas válidas. Una sesión es válida si tiene ≥ 350 velas RTH.
- Un día D se opera solo si tiene ≥ 150 velas entre 09:30 y 11:59 ET y existe sesión previa válida.
- Los datos de 8-12 Colombia equivalen a 09:00-13:00 ET (verano EE.UU.) u 08:00-12:00 ET (invierno). La ventana común es 09:00-12:00 ET.

## 2. Reglas comunes
- Ventana de operación: señales evaluadas al **cierre de cada vela de 1 minuto**; entrada en la **apertura de la vela siguiente**, solo si esa apertura es ≤ 11:30 ET; salida forzada al cierre de la vela 11:59 ET (12:00 ET). Todo cae dentro de 8-12 Colombia en ambas estaciones.
- Un trade por día y por hipótesis (la primera señal que cumple todas las condiciones).
- SL/TP evaluados con máximo/mínimo de las velas siguientes; si ambos caen en la misma vela, **gana el SL**. El fill del SL/TP es en su nivel (sin deslizamiento extra: limitación declarada).
- Costo por trade redondo: **2.0 pts** = spread 1.5 (máximo dictado para IC Markets) + slippage 0.25 pts por lado [VERIFICAR CON IC MARKETS], vía `costo_trade_cfd`. Estrés: **3.0 pts**. Sin comisión (cuenta Standard). Sin swap (todo intradía).
- R = (pnl en puntos − costo) / distancia al SL en puntos. PF y expectativa en R.
- Sin look-ahead: niveles, ATR y perfil usan solo datos hasta el cierre de D-1.

## 3. Hipótesis (reglas fijas)
**H1: ruptura del rango de apertura (ORB).** OR = máx/mín de las velas 09:30-09:44 ET. Se omite el día si ancho(OR) < 0.10×ATR14 o > 0.60×ATR14. Desde 09:45: primer cierre > OR alto → largo; < OR bajo → corto. SL = lado opuesto del OR. TP = 1.5 × distancia al SL.

**H2: reversión al VWAP.** VWAP anclado a las 09:30 ET con precio típico (H+L+C)/3 × tick_volume. Señales desde las 10:00 ET. Primer cierre con |cierre − VWAP| ≥ 0.20×ATR14 → operar hacia el VWAP. SL = entrada ± 0.20×ATR14 (lejos del VWAP). TP = valor del VWAP en el momento de la señal (nivel fijo).

**H3: ruptura y sostén de PDH/PDL.** PDH/PDL = máx/mín RTH de D-1. Desde 09:45 ET: primer cierre > PDH → largo; < PDL → corto. SL = nivel ∓ 0.15×ATR14. Se omite si la distancia entrada-SL > 0.50×ATR14. TP = 1.5 × distancia al SL.

**H4: rechazo en el área de valor del día previo.** Perfil de D-1 RTH: contenedores de 2.5 pts, volumen de cada vela de 1 min (tick_volume) repartido uniformemente entre sus contenedores de [mín, máx]; POC = contenedor de mayor volumen; área de valor 70 % expandida desde el POC. Desde 09:45 ET: vela con máx ≥ VAH y cierre < VAH, con cierre anterior < VAH → corto (espejo en VAL → largo). TP = POC. SL = VAH (o VAL) ± 0.15×ATR14. Se omite si |POC − entrada| < 0.15×ATR14 o la distancia al SL > 0.50×ATR14.

## 4. Robustez declarada (no sirve para elegir, solo para descartar)
- Rejilla 3×3 por hipótesis: multiplicador de umbral ATR {0.75, 1.0, 1.25} × TP {1.0, 1.5, 2.0}×SL (en H2 el TP es el VWAP, y la rejilla varía el umbral y el SL {0.15, 0.20, 0.25}×ATR). La regla base es la única que decide.
- PF sin cada año; primera mitad (2018-2022) vs segunda (2023-2026); verano vs invierno de EE.UU.
- Costo ×1 (2.0 pts) y ×1.5 (3.0 pts).

## 5. Placebos
- **Nivel:** el nivel de D-N en lugar del de D-1 (N = 2, 3, 5, 10). H1: OR del día D-N. H2: curva de VWAP del día D-N a la misma hora. H3 y H4: PDH/PDL y perfil de D-N.
- **Timing aleatorio:** en cada día con trade real, entrada en un minuto aleatorio de 09:45-11:29, dirección al azar y las mismas distancias SL/TP del trade real; 200 sorteos; p ≤ 0.05.
- **Dirección invertida:** misma entrada y mismas distancias, sentido contrario.

## 6. Walk-forward
Ninguna regla se ajusta con datos, así que todo el periodo es fuera de muestra. Los folds son los años calendario 2018-2026 y las dos mitades. No se reoptimiza dentro de los folds.

## 7. Criterios de aprobación (los siete, por hipótesis)
1. PF neto ≥ 1.15 con costo 2.0 pts.
2. Límite inferior del IC90 del PF > 1.0 (bootstrap por día, 5 000 remuestreos).
3. Límite inferior del IC90 de la expectativa (R/trade) > 0.
4. PF > 1 en al menos 60 % de los años con ≥ 30 trades.
5. Supera los tres placebos (nivel, timing aleatorio, dirección invertida).
6. PF > 1.0 con costo 3.0 pts.
7. La rejilla 3×3 no se apoya en un solo punto: el PF base no es el único con PF ≥ 1.15.

Se prueban **cuatro hipótesis**: si una pasa, el riesgo de falso positivo por múltiples pruebas es real. Por eso, y solo en ese caso, se pasa a demo de IC Markets (50-100 trades) como validación adicional, no a dinero real. Una hipótesis que no pasa los siete se descarta; no se re-ajusta.

## 8. Limitaciones declaradas
- Datos de demo: spread, volumen (tick) y precios del CFD no son los de la cuenta real [VERIFICAR].
- El spread usado es un máximo dictado, fijo; el spread real varía por hora y se amplía en noticias.
- Sin exclusión de días de noticias (CPI, NFP, FOMC): limitación como en LSR v1.
- La entrada en la apertura de la vela siguiente y el fill del SL/TP en su nivel son supuestos; sin cola ni deslizamiento extra.
- Un solo instrumento y 8.8 años: alrededor de 2 200 sesiones por hipótesis como máximo.
