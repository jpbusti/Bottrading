# Auditoría preliminar: dashboard "USTEC" (Exness MT5), 2026-10-09

**Veredicto preliminar: NO APROBADA y NO VERIFICADA.** Solo hay un dashboard; sin lista de trades ni extracto del bróker no se puede probar nada de lo que reporta. Los números, tomados al pie de la letra, no son absurdos, pero no demuestran una ventaja y tienen varias señales de alerta.

## 1. Lo que cuadra y lo que no (calculado solo con las cifras del dashboard)
| Verificación | Resultado |
|---|---|
| 393 trades × 77.35 % = 304 ganadores, 89 perdedores | OK |
| 304 × 61.39 − 89 × 159.06 = 4 506 | OK, coincide con la ganancia neta |
| PF = 18 663 / 14 157 | 1.318, coincide con 1.32 |
| Payoff esperado 4 506 / 393 | 11.47, coincide |
| **ROI +401.45 % con $4 506 sobre $1 000** | **NO cuadra**: serían 450.6 %. 401.45 % implicaría un capital base de ≈ $1 122 [VERIFICAR] |
| **Sharpe 2.33** | Con estas cifras el Sharpe por trade es 0.124; anualizado con ~262 trades/año da ≈ 2.0. 2.33 no se reproduce sin saber la frecuencia usada [VERIFICAR] |
| Racha 18 ganadas / 3 perdidas | Con 77 % de aciertos y 393 trades, lo esperado es ≈ 17.5 y ≈ 3.8: **normal, no es alerta** |

## 2. Señales de alerta
1. **Estructura de pocas ganancias grandes pérdidas.** Ganancia media $61 contra pérdida media $159 (payoff 0.39). El win rate de equilibrio es 72.2 %; el real es 77.35 %. La expectativa es ≈ 0.07 R por trade, es decir, la ventaja depende de ~5 puntos de win rate. Un win rate de 72 % con la misma estructura da pérdida (simulación: a riesgo 5 %, mediana final ×0.79).
2. **Win rate alto + salida por trailing sin TP:** es el patrón típico de estrategias que cortan ganancias pequeñas y dejan correr pérdidas grandes. Hay que descartar que sea grid, martingala o promedio a la baja [PREGUNTA, ver §3].
3. **Periodo de 18 meses (ene 2025 - jun 2026) en un mercado muy alcista del Nasdaq.** Si la estrategia es mayormente larga, el resultado puede ser solo beta del mercado. Sin 2022 (mercado bajista) y 2023-2024 no se sabe nada. Mi propio historial USTEC de IC Markets muestra ese tramo alcista.
4. **Parámetros "redondos y específicos"** (trailing +$40 de inicio, paso $1): puede ser el resultado de optimizar sobre el mismo periodo. Sin rejilla de sensibilidad no se sabe si $39 o $45 destruyen el resultado.
5. **El trailing está en dólares, y el lote es dinámico** (5 % de riesgo por SL): el mismo $40 equivale a menos puntos cuando el lote crece. El comportamiento cambia con el capital: mezcla de efecto de tamaño y de señal.
6. **Riesgo por trade de 5 %**, 2.5-5 veces el del plan (1-2 %). A ese riesgo, con las mismas estadísticas, la simulación da DD mediana ≈ 31 % y p95 ≈ 51 %: el **21.65 % reportado está en la parte favorable** de lo esperado. Con 2 % el DD mediano sería ≈ 13 %.
7. **Resultado compuesto:** ROI de 400 % sale en buena parte del interés compuesto con 5 % de riesgo; la métrica útil es R por trade, no el dinero.
8. **Origen del dashboard desconocido.** Un dashboard no es un extracto. Puede ser demo, cuenta real, copia de otro, o curado. Exness es otro bróker con otros spreads y horarios que mi data de IC Markets.
9. **Con intervalos de confianza amplios.** Aun tomando las cifras como ciertas, el IC90 del PF con solo estas dos cifras (ganancia y pérdida medias) es 1.09-1.61: el piso está cerca de 1 y sin la lista real de trades no se puede calcular bien.

## 3. Lo que necesito de ti
1. **Lista de trades** (CSV de MT5: hora de apertura/cierre, lado, lote, precios, SL, comisión, swap, resultado). Es lo más importante.
2. **¿Demo o real?** ¿Quién la operó y desde cuándo? ¿Hay extracto del bróker?
3. **Reglas de entrada** (indicadores, horas, timeframe). ¿Opera largos y cortos? ¿Promedia posiciones? ¿Varias posiciones a la vez?
4. **Cómo se calcularon Sharpe y ROI** (¿el 401 % parte de qué capital? ¿hubo depósitos/retiros?).
5. **Spread y comisión usados en esos resultados** y el horario operado.

## 4. Plan de auditoría (en este orden; nada de esto se corre hasta tener los trades)
1. **Reconstrucción:** recalcular PF, expectativa en R, Sharpe, DD y el ROI desde la lista de trades; verificar que cuadren con el dashboard.
2. **Inferencia:** IC90 del PF y de R/trade por bootstrap por día; PF por mes y por semestre; dependencia de pocos trades grandes.
3. **Beta del mercado:** separar largos y cortos, comparar con comprar y mantener el USTEC en el mismo periodo; correlación con la dirección diaria.
4. **Costos:** repetir con el spread de Exness real por hora y con mis costos IC Markets (spread 1.5-2.0, slippage). Si la ventaja está en 1-2 pts por trade, no sobrevive.
5. **Placebos** (necesitan las reglas): timing aleatorio, dirección invertida, y reglas sobre niveles de otros días.
6. **Robustez de parámetros:** rejilla del inicio del trailing ($30-$55) × paso ($0.5-$2) y del riesgo por SL; exigir una meseta, no un pico.
7. **Fuera de muestra:** implementar las reglas y correrlas sobre **2022-2024**. Para eso hace falta data del USTEC de esos años (mi historial tiene USTEC de IC Markets desde 2018, así que se puede) y la regla escrita; no se puede con solo el dashboard.
8. **Walk-forward** por años 2018-2026 con parámetros fijados antes (pre-registro).
9. **Monte Carlo** de drawdown a 1-2 % de riesgo (el plan operativo), no a 5 %.
10. **Criterios** (los mismos del proyecto): PF ≥ 1.15, IC90 inferior del PF > 1.0, IC90 de R > 0, PF > 1 en ≥ 60 % de años, supera placebos, aguanta costo +50 %.

## 5. Qué NO hacer
No copiar ni fondear esta estrategia con dinero real, ni aumentar el riesgo a 5 %, con base en este dashboard.
