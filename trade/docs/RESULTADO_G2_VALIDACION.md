# Resultado G2: validación fuera de muestra del marco PDH/PDL + VWAP (NQ/ES)

Fecha: 2026-10-08. Protocolo: PREREGISTRO_G2_VALIDACION.md (escrito antes de correr). Evidencia: nivel A (reproducida con datos propios, costos incluidos).

## Veredicto: G2 NO APROBADO
La regla congelada (barrido + retest + VWAP, antes de 10:30, sin POC, SL 80 / TP 110 normalizados) no tiene expectativa positiva fuera de muestra. El PF 1.63-1.73 del último año de NQ no se sostiene en ningún otro periodo ni instrumento.

## Control del motor
Reproduce el script original en el periodo de selección: n=172, aciertos 54.07%, PF 1.629, +21.5 pts/trade (costo 3). Se usó para validar el motor antes de aplicarlo a datos nuevos.

## Resultados (costo base, niveles del contrato operado, sin saltar días)
| Instrumento | Normalización | n | PF | Exp. neta (R) | IC90 exp. | IC90 PF | Años PF>1 |
|---|---|---|---|---|---|---|---|
| NQ 2016-2021 | ATR | 577 | 0.76 | -0.154 | [-0.229, -0.074] | [0.67, 0.88] | 0% |
| NQ 2016-2021 | % precio | 579 | 0.84 | -0.092 | [-0.167, -0.017] | [0.73, 0.97] | 20% |
| ES 2016-2025 | ATR | 926 | 0.79 | -0.138 | [-0.200, -0.074] | [0.70, 0.88] | 11% |
| ES 2016-2025 | % precio | 925 | 0.94 | -0.030 | [-0.088, +0.028] | [0.84, 1.06] | 44% |
Informativo, puntos fijos 80/110 sin normalizar: NQ PF 1.01 y ES PF 1.05, ambos con IC90 que incluye 0.
Informativo, último año de ES (mismo periodo de selección de NQ): PF 1.08 (ATR) y 0.97 (%), IC90 incluye 0.

## Lectura
- Antes de costos la expectativa es ≈ +0.03 a +0.09 R por trade: un edge mínimo que los costos consumen (0.12-0.21 R por trade con stops normalizados).
- Con costos ×0.5 sigue sin pasar en NQ (PF 0.90 / 0.95). Con ×2 empeora (PF 0.55-0.66).
- El rollover no explica el resultado: omitir 0-3 días tras cada roll mueve el PF de 0.763 a 0.785 (NQ, ATR).
- Exigir 0.5 pt a través del nivel para el fill y aplicar los filtros en modo "post" no cambian la conclusión.
- Año por año (ES, % precio) solo 2020, 2021, 2024 y 2025 superan PF 1; 2022 cae a 0.61. Resultado dependiente de régimen, no estable.
- El PF placebo (niveles de D-2) queda cerca del PF real en NQ con %: los niveles aportan poco o nada.

## Decisión
El marco queda como herramienta visual/discrecional. No se automatiza ni pasa a paper trading. Las variantes con IC90 de expectativa por encima de 0 en la muestra de selección reflejan sobreajuste al último año (múltiples combinaciones SL/TP/filtros probadas sobre 254 sesiones).

## Archivos
Scripts reproducibles: motor_g2.py, extraer_contratos.py, run_validacion.py, control_test.py; log y resumen_decision.csv en trade/scripts/g2/.
