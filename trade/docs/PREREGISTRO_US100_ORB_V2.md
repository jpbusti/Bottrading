# Pre-registro v2: US100 ORB (VWAP + retest, sin filtro de volumen)

- **Fecha de redaccion:** 2026-10-09, antes de correr cualquier calculo de la variante.
- **Aprobacion:** Juan aprobo en el hilo del proyecto (2026-10-09) rehacer el estudio de eventos sin el filtro de volumen.
- **Documento base:** `docs/PREREGISTRO_US100_ORB.md` (v1, firmado 2026-10-09). Sigue vigente y su resultado (10 eventos, sin backtest) no se borra.
- **Estandar:** `docs/ESTANDAR_ESTRATEGIA.md`.

## Unico cambio respecto a v1
**Se elimina el filtro de volumen** (volumen de la barra de ruptura > 1.5 x media de 20 barras). `filtros.volumen.activo = false`.

**Motivo (defecto de datos, no resultados de rendimiento):** el tick volume de USTEC no es estacionario (media por barra de 5m: 622 en 2019, 2,018 en 2025). Un umbral relativo
sobre 20 barras casi no se dispara despues de 2019 (fraccion de barras que lo cumplen: 6.6-9.9% en 2018-2019 contra 0.2-2.2% en 2022-2026). El embudo de v1 dejo
10 eventos en 8.8 anios, 9 de ellos en 2018-2019, lo que impide cualquier conclusion. Lo que se observo para tomar esta decision fue el conteo de eventos y la deriva del
volumen, no el retorno de los eventos que pasaron el filtro. La conclusion de v1 ("sin edge detectable") se lee como "no hay datos suficientes", no como rechazo firme.

Reconocimiento de sesgo: el estudio v1 ya mostro retornos de las etapas ORB crudo y +VWAP (diferencia con el baseline ~0). Esos resultados son conocidos; v2 no los trata como
independientes. El estudio v2 es confirmatorio sobre los mismos datos, por eso el criterio de edge es mas exigente que el de v1 (ver abajo).

## Todo lo demas queda igual que v1
OR 09:30-09:45 ET (3 barras de 5m); ruptura = primera barra cuyo CIERRE sale del OR (hasta la barra de las 15:00); pendiente de VWAP de sesion sobre 5 barras a favor;
retest en <= 6 barras (toca el nivel con tolerancia 0 y cierra del lado de la ruptura; si toca y cierra del lado equivocado o cierra dentro del OR antes, no hay evento);
un evento como maximo por dia; entrada al cierre de la barra de retest (estudio de eventos). Mismos datos (`USTEC_1m_clean_2018_2026.csv`, ET, desde 2018-01-01), mismas
exclusiones de dias (gap > 1%, OPEX, NFP aproximado, FOMC, ATR(14) < p10 expansivo, sesion incompleta/sin ATR), mismos horizontes (30 m, 1 h, 2 h, cierre),
mismo baseline (1000 sorteos por evento, misma fecha y hora, solo barras posteriores a la entrada; el "literal" se reporta como informativo), mismo bootstrap por bloques
(5000 remuestras), mismo costo de referencia (2.0 pts redondos) y mismos parametros de backtest (SL/TP k x m, rejilla 3x3) si se llega a esa fase.

## Fases y reglas de parada (fijadas antes de ver resultados)
1. **Estudio de eventos** (`scripts/us100_orb/event_study_v2.py --sin-volumen`).
2. **Suficiencia de eventos:** si hay < 300 eventos, se reporta tal cual y no se sigue (el criterio de aprobacion exige >= 300 trades).
3. **Edge en el estudio de eventos.** Hay edge solo si, en al menos un horizonte:
   a. diferencia pareada contra baseline > 0 con p unilateral < 0.10 **corregido por Bonferroni sobre los 4 horizontes** (p x 4 < 0.10);
   b. el IC90 inferior del bootstrap de la diferencia > 0;
   c. el retorno medio del evento en ese horizonte es > 0 y mayor que el costo de 2.0 pts expresado en % del precio medio de entrada (el edge no puede venir solo de un baseline negativo).
4. **Si no hay edge o no hay eventos suficientes: se detiene aqui**, se escribe el resultado y no se hace backtest.
5. **Si hay edge y >= 300 eventos:** backtest completo con el motor existente (`run_backtest.py` con volumen desactivado), rejilla 3x3 de SL/TP, walk-forward expansivo, los tres placebos
   y robustez (rejilla de senal, excluir cada anio, costo con spread 3.0). Criterios de aprobacion identicos a v1: PF neto >= 1.15, IC90 inferior del PF > 1.0, >= 300 trades,
   max DD < 20%, placebos superados, rejilla 9/9, walk-forward OOS > 1 en todos los folds, sensibilidad temporal.
6. Sin cambios de parametros despues de ver resultados. Un resultado negativo se publica igual.

## Reporte obligatorio
PF neto, IC90 inferior del PF, numero de trades, max drawdown y robustez (rejilla de parametros y sensibilidad temporal). Si el proceso se detiene en la fase 1 o 2, se reporta
lo que se midio (eventos, retornos forward, diferencias y su significancia) y se dice explicitamente que no hay PF ni backtest.

## Advertencias vigentes
Calendario: FOMC escrito a mano, NFP aproximado por 1er viernes, CPI/PPI no excluidos (sin fuente en el repo). El tick volume sigue usandose para el VWAP de sesion (ponderacion),
que es independiente del filtro eliminado.
