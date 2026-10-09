"""
Backtest del marco "mercado de subastas" (PDH/PDL + perfil de volumen + AVWAP + WOR)
sobre NQ Databento 1m. Reglas objetivas; ver parametros abajo.
"""
import sys
import numpy as np
import pandas as pd

NY = "America/New_York"
RUTA = sys.argv[1]
SALIDA = sys.argv[2]

# ---------------- parametros (fijados ANTES de ver resultados) ----------------
BIN = 2.5            # tamano de bin del perfil (puntos)
VA_PCT = 0.70        # area de valor
SWEEP_MIN = 2.0      # pts que debe pasar el nivel para contar como barrido
RECLAIM_BARS = 6     # velas de 5m para recuperar tras el barrido
BREAK_BUF = 2.0      # cierre minimo mas alla del nivel para contar ruptura
RETEST_BARS = 12     # velas de 5m para el retest
RETEST_TOL = 1.0     # tolerancia de toque en retest
STOP_BUF = 2.0
RIESGO_MIN, RIESGO_MAX = 10.0, 60.0
COSTO_PTS = 1.5      # spread + slippage + comision, ida y vuelta
HORA_MAX = 15 * 60   # ultima senal 15:00 NY
RETEST_FILL_1M = 60  # minutos para que el precio vuelva al nivel (modo retest)

# ------------------------------- carga ---------------------------------------
raw = pd.read_csv(RUTA)
raw["Datetime"] = pd.to_datetime(raw["Datetime"], utc=True).dt.tz_convert(NY)
raw = raw.set_index("Datetime").sort_index()
raw = raw[~raw.index.duplicated()]
tod_all = raw.index.hour * 60 + raw.index.minute
rth = raw[(tod_all >= 570) & (tod_all < 960)].copy()
rth["fecha"] = rth.index.date
dias = {}
for f, g in rth.groupby("fecha"):
    if len(g) >= 200:
        dias[f] = g
fechas = sorted(dias)
print(f"Sesiones RTH validas: {len(fechas)}  ({fechas[0]} -> {fechas[-1]})")


def perfil(g):
    tp = ((g.High + g.Low + g.Close) / 3).values
    v = g.Volume.values.astype(float)
    b = np.round(tp / BIN) * BIN
    s = pd.Series(v).groupby(b).sum().sort_index()
    p, vol = s.index.values, s.values
    ip = int(np.argmax(vol))
    lo = hi = ip
    acc, tot = vol[ip], vol.sum()
    while acc < VA_PCT * tot and (lo > 0 or hi < len(vol) - 1):
        up = vol[hi + 1:hi + 3].sum() if hi < len(vol) - 1 else -1
        dn = vol[max(lo - 2, 0):lo].sum() if lo > 0 else -1
        if up >= dn:
            add = vol[hi + 1:hi + 3]
            hi += len(add)
        else:
            add = vol[max(lo - 2, 0):lo]
            lo -= len(add)
        acc += add.sum()
    return dict(POC=p[ip], VAH=p[hi], VAL=p[lo])


niv_dia = {}
for f in fechas:
    g = dias[f]
    d = perfil(g)
    d["PDH"], d["PDL"] = g.High.max(), g.Low.min()
    niv_dia[f] = d

# WOR: rango del primer dia (RTH) de la semana
semana = {}
for f in fechas:
    k = pd.Timestamp(f).isocalendar()[:2]
    semana.setdefault(k, []).append(f)
wor = {}
for k, fs in semana.items():
    g = dias[fs[0]]
    for f in fs[1:]:
        wor[f] = (g.High.max(), g.Low.min())

# ---------------------------- pre-proceso por dia ----------------------------
info = {}
for f in fechas:
    g = dias[f]
    t = (g.index.hour * 60 + g.index.minute).values
    o, h, l, c, v = (g[x].values.astype(float) for x in
                     ["Open", "High", "Low", "Close", "Volume"])
    tp = (h + l + c) / 3
    avwap = np.cumsum(tp * v) / np.maximum(np.cumsum(v), 1)
    k5 = (t - 570) // 5
    barras = []
    for k in np.unique(k5):
        idx = np.where(k5 == k)[0]
        i0, i1 = idx[0], idx[-1] + 1
        barras.append((int(t[i0]) + 5, o[i0], h[i0:i1].max(), l[i0:i1].min(),
                       c[i1 - 1], i1))
    info[f] = dict(t=t, o=o, h=h, l=l, c=c, avwap=avwap, barras=barras)


# ------------------------------- senales --------------------------------------
def senales(f, niveles, prev_close):
    """Devuelve lista cronologica de candidatos (tipo, dir, nivel, extremo, i1, close5, tfin)."""
    B = info[f]["barras"]
    out = []
    sw_up, sw_dn, br_up, br_dn = {}, {}, {}, {}
    pc = prev_close
    for k, (tfin, o, h, l, c, i1) in enumerate(B):
        if tfin > HORA_MAX:
            break
        for nm, lv in niveles.items():
            # --- barrido arriba -> recuperacion (corto)
            if nm in sw_up:
                k0, ext = sw_up[nm]
                ext = max(ext, h)
                sw_up[nm] = (k0, ext)
                if c < lv:
                    out.append(("A", -1, lv, ext, i1, c, tfin, nm))
                    del sw_up[nm]
                elif k - k0 >= RECLAIM_BARS:
                    del sw_up[nm]
            elif h > lv + SWEEP_MIN and pc < lv:
                if c < lv:
                    out.append(("A", -1, lv, h, i1, c, tfin, nm))
                else:
                    sw_up[nm] = (k, h)
            # --- barrido abajo -> recuperacion (largo)
            if nm in sw_dn:
                k0, ext = sw_dn[nm]
                ext = min(ext, l)
                sw_dn[nm] = (k0, ext)
                if c > lv:
                    out.append(("A", 1, lv, ext, i1, c, tfin, nm))
                    del sw_dn[nm]
                elif k - k0 >= RECLAIM_BARS:
                    del sw_dn[nm]
            elif l < lv - SWEEP_MIN and pc > lv:
                if c > lv:
                    out.append(("A", 1, lv, l, i1, c, tfin, nm))
                else:
                    sw_dn[nm] = (k, l)
            # --- ruptura + retest
            if nm in br_up:
                k0 = br_up[nm]
                if k > k0 and l <= lv + RETEST_TOL and c > lv:
                    out.append(("B", 1, lv, min(l, lv), i1, c, tfin, nm))
                    del br_up[nm]
                elif k - k0 >= RETEST_BARS or c < lv - BREAK_BUF:
                    del br_up[nm]
            elif c > lv + BREAK_BUF and pc <= lv + BREAK_BUF:
                br_up[nm] = k
            if nm in br_dn:
                k0 = br_dn[nm]
                if k > k0 and h >= lv - RETEST_TOL and c < lv:
                    out.append(("B", -1, lv, max(h, lv), i1, c, tfin, nm))
                    del br_dn[nm]
                elif k - k0 >= RETEST_BARS or c > lv + BREAK_BUF:
                    del br_dn[nm]
            elif c < lv - BREAK_BUF and pc >= lv - BREAK_BUF:
                br_dn[nm] = k
        pc = c
    return out


def simular(f, s, entrada, objetivo, niveles):
    tipo, d, lv, ext, i1, c5, tfin, nm = s
    I = info[f]
    h, l, c = I["h"], I["l"], I["c"]
    n = len(c)
    stop = ext + STOP_BUF if d == -1 else ext - STOP_BUF
    if entrada == "cierre":
        ent, j0 = c5, i1
    else:  # retest: limite en el nivel
        ent, j0 = None, None
        for j in range(i1, min(i1 + RETEST_FILL_1M, n)):
            if (d == -1 and h[j] >= lv) or (d == 1 and l[j] <= lv):
                ent, j0 = lv, j
                break
        if ent is None:
            return None
    riesgo = abs(stop - ent)
    if riesgo < RIESGO_MIN:
        stop = ent - d * RIESGO_MIN
        riesgo = RIESGO_MIN
    if riesgo > RIESGO_MAX:
        return None
    if objetivo == "nivel":
        cand = [p for p in niveles.values() if d * (p - ent) >= riesgo]
        if not cand:
            return None
        tgt = min(cand, key=lambda p: abs(p - ent))
    else:
        tgt = ent + d * 1.5 * riesgo
    sal, motivo = c[-1], "cierre"
    for j in range(j0, n):
        if d == 1:
            if l[j] <= stop:
                sal, motivo = stop, "SL"; break
            if h[j] >= tgt:
                sal, motivo = tgt, "TP"; break
        else:
            if h[j] >= stop:
                sal, motivo = stop, "SL"; break
            if l[j] <= tgt:
                sal, motivo = tgt, "TP"; break
    pnl = (sal - ent) * d - COSTO_PTS
    return dict(fecha=f, tipo=tipo, dir=d, nivel=nm, ent=ent, stop=stop, tgt=tgt,
                sal=sal, motivo=motivo, riesgo=riesgo, R=pnl / riesgo, pnl=pnl)


def correr(setup, entrada, filtro, objetivo, lag=1, dor=False):
    trades = []
    for di, f in enumerate(fechas):
        if di < lag:
            continue
        fp = fechas[di - lag]
        niveles = dict(niv_dia[fp])
        prev_close = dias[fechas[di - 1]].Close.values[-1]
        cands = senales(f, niveles, prev_close)
        cands = [s for s in cands if s[0] in setup]
        if entrada == "retest":
            cands = [s for s in cands if s[0] == "A"]
        I = info[f]
        for s in cands:
            tipo, d, lv, ext, i1, c5, tfin, nm = s
            if "VWAP" in filtro:
                av = I["avwap"][i1 - 1]
                if (d == 1 and c5 <= av) or (d == -1 and c5 >= av):
                    continue
            if "WOR" in filtro and f in wor:
                wh, wl = wor[f]
                if (d == 1 and c5 < wl) or (d == -1 and c5 > wh):
                    continue
            r = simular(f, s, entrada, objetivo, niveles)
            if r is not None:
                trades.append(r)
                break
    return pd.DataFrame(trades)


def stats(t, rng):
    if len(t) == 0:
        return dict(n=0, win=np.nan, PF=np.nan, expR=np.nan, ci_lo=np.nan, ci_hi=np.nan, ddR=np.nan)
    R = t.R.values
    g, p = R[R > 0].sum(), -R[R < 0].sum()
    pf = g / p if p > 0 else 99
    bs = [rng.choice(R, len(R)).mean() for _ in range(1500)]
    eq = np.cumsum(R)
    dd = (np.maximum.accumulate(eq) - eq).max()
    return dict(n=len(R), win=(R > 0).mean() * 100, PF=pf, expR=R.mean(),
                ci_lo=np.percentile(bs, 5), ci_hi=np.percentile(bs, 95), ddR=dd)


def pf_simple(t):
    if len(t) == 0:
        return np.nan
    R = t.R.values
    p = -R[R < 0].sum()
    return R[R > 0].sum() / p if p > 0 else 99


rng = np.random.default_rng(42)
corte = fechas[int(len(fechas) * 0.6)]

variantes = []
for setup, entrada in [("A", "cierre"), ("A", "retest"), ("B", "cierre"), ("AB", "cierre")]:
    for filtro in ["ninguno", "VWAP", "VWAP+WOR"]:
        for objetivo in ["nivel", "1.5R"]:
            variantes.append((setup, entrada, filtro, objetivo))

filas = []
trades_all = {}
for v in variantes:
    setup, entrada, filtro, objetivo = v
    t = correr(setup, entrada, filtro, objetivo, lag=1)
    pl = correr(setup, entrada, filtro, objetivo, lag=2)  # placebo: niveles de hace 2 dias
    s = stats(t, rng)
    tis, toos = t[t.fecha < corte], t[t.fecha >= corte]
    row = dict(setup=setup, entrada=entrada, filtro=filtro, objetivo=objetivo, **s,
               PF_IS=pf_simple(tis), n_IS=len(tis), PF_OOS=pf_simple(toos), n_OOS=len(toos),
               expR_OOS=toos.R.mean() if len(toos) else np.nan,
               PF_placebo=pf_simple(pl), expR_placebo=pl.R.mean() if len(pl) else np.nan,
               n_placebo=len(pl))
    filas.append(row)
    trades_all[v] = t
    print(f"{setup:2s} {entrada:6s} {filtro:9s} {objetivo:5s} n={s['n']:3d} win={s['win']:5.1f}% "
          f"PF={s['PF']:.2f} expR={s['expR']:+.3f} IC90=[{s['ci_lo']:+.2f},{s['ci_hi']:+.2f}] "
          f"| IS {row['PF_IS']:.2f} OOS {row['PF_OOS']:.2f} | placebo PF {row['PF_placebo']:.2f}",
          flush=True)

res = pd.DataFrame(filas)
res.to_csv(SALIDA + "/marco_subastas_resultados.csv", index=False)
best = res.sort_values("expR", ascending=False).iloc[0]
v = (best.setup, best.entrada, best.filtro, best.objetivo)
trades_all[v].to_csv(SALIDA + "/marco_subastas_mejor_variante_trades.csv", index=False)
print("\nMejor por expectancy:", dict(best[["setup", "entrada", "filtro", "objetivo", "n", "PF", "expR"]]))
print("Variantes con expR>0:", int((res.expR > 0).sum()), "de", len(res))
print("Variantes con IC90 inferior > 0:", int((res.ci_lo > 0).sum()))
print("Variantes con PF_IS>1 y PF_OOS>1:", int(((res.PF_IS > 1) & (res.PF_OOS > 1)).sum()))
print("corte IS/OOS:", corte)
