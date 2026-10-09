# Pre-registro G2: validación fuera de muestra de la regla congelada (NQ/ES)

Fecha de redacción: 2026-10-08, ANTES de correr cualquier resultado sobre NQ 2016-2021 o ES.
Estado de la evidencia: nivel C hasta reproducirse (nivel A solo si pasa este protocolo con costos).
Lo que ya se sabía antes de escribir esto (transparencia): en NQ 2021-10→2025-10 la misma regla dio PF ≈ 1.02-1.03 con IC90 incluyendo 0. Eso hace esperable un resultado débil; no se usa para ajustar nada.

## 1. Regla congelada (no se modifica ni se optimiza)
- Setup A (barrido + recuperación), entrada limit en el nivel (retest, ventana 60 min, toque = fill).
- Niveles: PDH, PDL, VAH, VAL, POC del día previo (perfil 70%, bin 2.5 pts).
- Filtro VWAP anclado a la apertura (largo solo si cierre 5m > VWAP; corto solo si <).
- Solo entradas antes de las 10:30 NY. Se excluye el nivel POC.
- Un trade por día: el primer candidato que cumple TODOS los filtros (los filtros se aplican al flujo de candidatos, no después).
- SL 80 pts / TP 110 pts (calibración NQ, periodo de selección 2025-10-07 → 2026-10-06, 254 sesiones). Si no toca ninguno, cierre de sesión.
- Costos base: NQ 3.0 pts ($60 ida y vuelta); ES 1.25 pts ($62.5). Sensibilidad ×0.5 y ×2.
- Reproducción de control: con el script original (COSTO=3) la regla SL80/TP110 + VWAP da n=172, PF 1.63, +21.5 pts/trade en el periodo de selección. El motor nuevo debe reproducirlo antes de usarse.

## 2. Normalización entre épocas e instrumentos
La regla se calibró con NQ a ~27,206 (precio medio de cierre) y ATR14 diario medio de 445.9 pts (rango RTH).
- 80 pts = 0.294% del precio = 0.179 × ATR14; 110 pts = 0.404% = 0.247 × ATR14. (Corrige la cifra aproximada 0.35%/0.50% dicha antes; la base correcta es el precio del periodo de selección, no 4,800.)
- Método ATR (primario): SL = 0.179 × ATR14(D-1), TP = 0.247 × ATR14(D-1).
- Método % (secundario): SL = 0.294% y TP = 0.404% del cierre D-1.
- Los mismos múltiplos/porcentajes se aplican a ES con SU propio ATR/precio (traslado de la regla, no recalibración).
- Los parámetros en puntos (barrido 2, tolerancia retest 1, bin 2.5) se escalan con el mismo factor del día. ATR14 y precio usan solo datos hasta el cierre de D-1 (sin look-ahead).
- R = pnl neto de costos / distancia SL del día. PF y expectativa se calculan en R.
- Variante informativa (no decide): puntos fijos 80/110 sin normalizar.

## 3. Contratos y rollover
- Contrato del día D = el de mayor volumen RTH del día D-1. Operar el contrato indicado de principio a fin; sin back-adjust.
- Niveles, cierre previo y perfil se calculan con las velas de ESE MISMO contrato en D-1 (no hay salto de roll en los niveles). No se salta ningún día en el caso base.
- Si el contrato no tiene ≥200 velas RTH en D-1 o en D, se omite el día.
- Los trades son intradía y cierran en la sesión: no hay costo de roll sobre posiciones abiertas.
- Sensibilidad (informativa): omitir 1, 2 y 3 días tras cada roll; si el PF cambia de forma material, el resultado se considera frágil.

## 4. Conjuntos de datos y decisión
- NQ fuera de tiempo: 2016-10-10 → 2021-10-08.
- ES: 2016-10-10 → 2025-10-06 (se excluye el último año por coincidir con el periodo de selección de NQ; se reporta aparte).
- NQ 2021-10→2025-10 ya se examinó: se reporta, no decide.

## 5. Criterios de aprobación (los cinco, por instrumento y por método)
1. PF ≥ 1.15 (en R, costos base).
2. Límite inferior del IC90 de la expectativa neta (R/trade, bootstrap 5,000) > 0.
3. Límite inferior del IC90 del PF (bootstrap) > 1.0.
4. PF > 1 en al menos 60% de los años calendario con ≥30 trades (walk-forward con regla congelada: todo el periodo es fuera de muestra).
5. PF real > PF placebo (niveles de D-2).
Aprobado G2 solo si NQ y ES cumplen los cinco con AMBOS métodos (ATR y %). Si solo pasa con uno, se trata como sobreajuste. Si no pasa: el marco queda como herramienta visual, no se automatiza.
Nota de aclaración: el "IC90 > 0" mencionado antes se refería a la expectativa por trade, no al PF (el PF siempre es > 0). Ahora se exige además IC90 inferior del PF > 1.

## 6. Monte Carlo y riesgo
- Remuestreo de la secuencia de trades (bootstrap por bloques de 20) para distribución de max drawdown en R y racha perdedora máxima.

## 7. Limitaciones declaradas
- Fill por toque (sin cola ni slippage adicional en el limit): optimista. Sensibilidad: exigir 0.5 pt (escalado) a través del nivel.
- Costo base fijo en puntos/dólares: conservador para 2016-2019; puede sobrepenalizar esa época en términos de R.
- Los filtros "antes de 10:30" y "sin POC" salieron del mismo periodo de selección (minería posible); solo la prueba fuera de muestra los valida.
- Múltiples pruebas (2 instrumentos × 2 métodos): se exige que todas pasen, lo que reduce el riesgo de falso positivo.
