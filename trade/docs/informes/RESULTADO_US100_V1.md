# Resultado US100 v1: ninguna de las 4 hipótesis pasa

Pre-registro: `docs/preregistros/PREREGISTRO_US100_V1.md` (commit `5783f39`, escrito antes de correr). Motor: `scripts/us100/motor_us100.py`; corrida: `scripts/us100/run_us100.py`; salidas en `resultados/us100/`.
Datos: USTEC (CFD) de la demo de IC Markets, 1 min, 2018-01-02 → 2026-10-08, 2 157 sesiones válidas, ventana de entradas 09:45-11:30 ET (dentro de 8-12 Colombia en verano e invierno). Costo base 2.0 pts por trade (spread 1.5 + slippage 0.25/lado), estrés 3.0 pts. Todos los costos [VERIFICAR CON IC MARKETS].

| Hipótesis | Trades | PF neto | IC90 PF | Exp. R/trade | IC90 exp. | PF bruto (sin costos) | PF con costo 3.0 | Años con PF>1 | Veredicto |
|---|---|---|---|---|---|---|---|---|---|
| H1 ORB (ruptura rango de apertura) | 2 019 | 0.953 | 0.867-1.045 | -0.012 | -0.035 a 0.011 | 1.031 | 0.916 | 33 % | NO APROBADA |
| H2 reversión al VWAP | 1 789 | 0.811 | 0.747-0.879 | -0.103 | -0.142 a -0.064 | 0.916 | 0.763 | 11 % | NO APROBADA |
| H3 ruptura y sostén PDH/PDL | 1 222 | 0.945 | 0.852-1.046 | -0.029 | -0.081 a 0.023 | 1.053 | 0.895 | 44 % | NO APROBADA |
| H4 rechazo VAH/VAL (perfil 1 min) | 468 | 0.846 | 0.714-1.005 | -0.093 | -0.184 a 0.003 | 0.957 | 0.796 | 33 % | NO APROBADA |

Máximo drawdown en R: H1 35.6, H2 207.1, H3 52.7, H4 54.5 (serie cronológica de trades, 1R = distancia al SL).

## Los siete criterios (todos fallan en las cuatro hipótesis)
1 PF ≥ 1.15, 2 IC90 del PF > 1.0, 3 IC90 de la expectativa > 0, 4 ≥ 60 % de años con PF > 1, 5 supera los tres placebos, 6 PF > 1 con costo 3.0, 7 rejilla con ≥ 2 puntos de PF ≥ 1.15. Resultado: ninguna cumple ni siquiera el 1 ni el 6; la rejilla 3×3 (9 puntos en H1-H3, 3 en H4) no tiene ningún punto con PF ≥ 1.15.

## Placebos
- **Timing aleatorio** (200 sorteos, mismas distancias SL/TP): el PF mediano del azar es ≈ 0.89-0.91 en las cuatro. Las reglas reales (H1 0.953, H3 0.945) no se distinguen del azar (p = 0.17 y 0.28); H2 y H4 son peores que el azar (p = 0.97 y 0.70).
- **Nivel D-N:** H3 con niveles de D-N da PF 1.02-1.08, **mejor que con los niveles reales (0.945)**; en H1 los niveles falsos dan 0.94-0.99, igual al real. Los niveles de D-1 no aportan información.
- **Dirección invertida:** H2 invertida da 0.995 (mejor que la real 0.811); H1 0.929 y H3 0.866 son peores que las reales pero ninguna llega a 1; H4 0.817.

## Lectura
- Sin costos, H1 y H3 rozan 1.03 y 1.05: es ruido dentro del IC90. Los costos de 2.0 pts (≈ 2-6 % del SL en R por trade) los llevan por debajo de 1.
- H2 (reversión al VWAP) pierde incluso sin costos (0.916): en esta ventana el precio no revierte al VWAP con esta regla.
- H4 depende de una aproximación del perfil de volumen con velas de 1 min y tick_volume; el resultado negativo no demuestra que el perfil verdadero no sirva, solo que esta aproximación con esta regla no da ventaja [VERIFICAR con ticks].
- La separación por estación (verano/invierno de EE.UU.) y por mitades (2018-2022 / 2023-2026) no rescata a ninguna: ninguna tiene PF > 1 en ambas mitades.

## Qué NO se hace ahora
No se ajustan umbrales, SL/TP ni horas hasta que salga PF > 1: eso sería sobreajuste y exigiría un pre-registro v2 con una hipótesis nueva. No se pasa a demo con estas reglas. LSR v1, G2 y estas cuatro suman seis reglas rechazadas.

## Limitaciones
Spread, volumen (tick) y precios de la demo no son los de la cuenta real; el spread de 1.5 pts es fijo; sin filtro de noticias; fill del SL/TP en su nivel (optimista); H4 usa aproximación de perfil; 4 hipótesis probadas (riesgo de múltiples pruebas, que aquí no hizo falta aplicar porque ninguna pasó).
