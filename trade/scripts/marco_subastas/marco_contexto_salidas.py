"""
Backtest del marco "mercado de subastas" (PDH/PDL + perfil de volumen + AVWAP + WOR)
sobre NQ Databento 1m. Reglas objetivas; ver parametros abajo.
"""
import sys, os
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
COSTO_PTS = float(os.environ.get('COSTO', 1.5))      # spread + slippage + comision, ida y vuelta
HORA_MAX = 15 * 60   # ultima senal 15:00 NY
FILL_THROUGH = float(os.environ.get('THROUGH', 0))
RMULT = float(os.environ.get('RMULT', 1.5))
FIXSL = 0
FIXTP = 0
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
            if (d == -1 and h[j] >= lv + FILL_THROUGH) or (d == 1 and l[j] <= lv - FILL_THROUGH):
                ent, j0 = lv, j
                break
        if ent is None:
            return None
    if FIXSL:
        stop = ent - d * FIXSL
    riesgo = abs(stop - ent)
    if FIXSL:
        pass
    elif riesgo < RIESGO_MIN:
        stop = ent - d * RIESGO_MIN
        riesgo = RIESGO_MIN
    if not FIXSL and riesgo > RIESGO_MAX:
        return None
    if FIXSL:
        tgt = ent + d * FIXTP
    elif objetivo == "nivel":
        cand = [p for p in niveles.values() if d * (p - ent) >= riesgo]
        if not cand:
            return None
        tgt = min(cand, key=lambda p: abs(p - ent))
    else:
        tgt = ent + d * RMULT * riesgo
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





def pf_pts(x):
    x = np.asarray(x, float)
    if len(x) == 0: return float("nan")
    p = -x[x < 0].sum()
    return x[x > 0].sum() / p if p > 0 else 99.0

LIM = pd.Timestamp("2025-10-07").date()
idxf = {f: i for i, f in enumerate(fechas)}
rango = {f: niv_dia[f]["PDH"] - niv_dia[f]["PDL"] for f in fechas}
cierre_pos = {}
for f in fechas:
    g = dias[f]; hh, ll, cc = g.High.max(), g.Low.min(), g.Close.values[-1]
    cierre_pos[f] = (cc - ll) / max(hh - ll, 1e-9)

# ===================== TEST X: sesgo por interaccion del dia previo con niveles de D-2 =====================
cls = {}
rows = []
for di in range(2, len(fechas)):
    f, p1, p2 = fechas[di], fechas[di - 1], fechas[di - 2]
    g1 = dias[p1]; H1, L1, C1 = g1.High.max(), g1.Low.min(), g1.Close.values[-1]
    PH, PL = niv_dia[p2]["PDH"], niv_dia[p2]["PDL"]
    if H1 > PH and C1 < PH: c = "barrido_PDH (mecha, cierra dentro)"
    elif L1 < PL and C1 > PL: c = "barrido_PDL (mecha, cierra dentro)"
    elif C1 > PH: c = "ruptura_arriba (cierra con cuerpo)"
    elif C1 < PL: c = "ruptura_abajo (cierra con cuerpo)"
    else: c = "ninguno"
    cls[f] = c
    g = dias[f]
    rows.append((f, c, g.Close.values[-1] - g.Open.values[0]))
r = pd.DataFrame(rows, columns=["fecha", "clase", "mov"])
print("\n=== X. Movimiento del dia siguiente (open->close RTH, pts) segun clase del dia previo ===")
for c, g in r.groupby("clase"):
    m, sd, n = g.mov.mean(), g.mov.std(), len(g)
    pre, post = g[g.fecha < LIM].mov.mean(), g[g.fecha >= LIM].mov.mean()
    print(f"{c:40s} n={n:4d} media={m:7.1f} t={m/(sd/np.sqrt(n)):5.2f} %sube={(g.mov>0).mean()*100:4.0f} | antes={pre:7.1f} ultimo_anio={post:7.1f}")

# ===================== TEST Y: salidas por contexto =====================
def entrada_precio(f, s, modo):
    tipo, d, lv, ext, i1, c5, tfin, nm = s
    I = info[f]; h, l = I["h"], I["l"]; n = len(h)
    if modo == "cierre":
        return c5, i1
    for j in range(i1, min(i1 + RETEST_FILL_1M, n)):
        if (d == -1 and h[j] >= lv + FILL_THROUGH) or (d == 1 and l[j] <= lv - FILL_THROUGH):
            return lv, j
    return None, None

def salir(f, d, ent, j0, modo):
    I = info[f]; h, l, c = I["h"], I["l"], I["c"]; n = len(c)
    stop = ent - d * (80 if modo == "f80/110" else 60)
    tgt = None
    if modo == "f60/80": tgt = ent + d * 80
    if modo == "f80/110": tgt = ent + d * 110
    if modo == "be+tp110": tgt = ent + d * 110
    best = ent; moved = False; cur = stop
    sal = c[-1]
    for j in range(j0, n):
        if d == 1:
            if l[j] <= cur: sal = cur; break
            if tgt is not None and h[j] >= tgt: sal = tgt; break
            best = max(best, h[j])
        else:
            if h[j] >= cur: sal = cur; break
            if tgt is not None and l[j] <= tgt: sal = tgt; break
            best = min(best, l[j])
        if modo == "trail40":
            cur = max(cur, best - 40) if d == 1 else min(cur, best + 40)
        if modo == "be+tp110" and not moved and d * (best - ent) >= 50:
            cur = ent; moved = True
    return (sal - ent) * d - COSTO_PTS

MODOS = ["f60/80", "f80/110", "s60_cierre", "trail40", "be+tp110"]
def recolectar(setup, entrada):
    out = []
    for di, f in enumerate(fechas):
        if di < 21: continue
        niveles = dict(niv_dia[fechas[di - 1]])
        prev_close = dias[fechas[di - 1]].Close.values[-1]
        cands = [s for s in senales(f, niveles, prev_close) if s[0] == setup]
        I = info[f]
        for s in cands:
            tipo, d, lv, ext, i1, c5, tfin, nm = s
            av = I["avwap"][i1 - 1]
            if (d == 1 and c5 <= av) or (d == -1 and c5 >= av): continue
            ent, j0 = entrada_precio(f, s, entrada)
            if ent is None: continue
            rec = dict(fecha=f, setup=setup, dir=d, nivel=nm)
            for m in MODOS: rec[m] = salir(f, d, ent, j0, m)
            rv = np.mean([rango[x] for x in fechas[di - 20:di]])
            rec["vol"] = "vol_alta" if rango[fechas[di - 1]] > rv else "vol_baja"
            rec["hora"] = "antes_10:30" if I["t"][j0] < 630 else "despues_10:30"
            rec["grupo"] = "PDH/PDL" if nm in ("PDH", "PDL") else ("VAH/VAL" if nm in ("VAH", "VAL") else "POC")
            cp = cierre_pos[fechas[di - 1]]
            sesgo = 1 if cp > 0.65 else (-1 if cp < 0.35 else 0)
            rec["vs_cierre_prev"] = "neutro" if sesgo == 0 else ("a_favor" if sesgo == d else "en_contra")
            rec["distVWAP"] = abs(c5 - av)
            rec["clase_prev"] = cls.get(f, "ninguno")
            out.append(rec); break
    return pd.DataFrame(out)

pd.set_option("display.width", 220)
for setup, entrada in [("A", "retest"), ("B", "cierre")]:
    t = recolectar(setup, entrada)
    t["dv"] = np.where(t.distVWAP > t.distVWAP.median(), "lejos_VWAP", "cerca_VWAP")
    print(f"\n\n######## Setup {setup} ({entrada}) + filtro VWAP | n={len(t)} ########")
    print("\n-- Por modo de salida (pts/trade tras costos | PF):  todo / antes de oct-2025 / ultimo anio")
    for m in MODOS:
        pre, post = t[t.fecha < LIM][m], t[t.fecha >= LIM][m]
        print(f"{m:11s} todo {t[m].mean():6.1f} PF {pf_pts(t[m]):.2f} | antes {pre.mean():6.1f} PF {pf_pts(pre):.2f} | ultimo {post.mean():6.1f} PF {pf_pts(post):.2f}")
    for ctx in ["hora", "vol", "grupo", "vs_cierre_prev", "dv", "dir"]:
        print(f"\n-- Contexto: {ctx}  (pts/trade por salida)")
        g = t.groupby(ctx)[MODOS].mean().round(1)
        g.insert(0, "n", t.groupby(ctx).size())
        print(g.to_string())
    if setup == "A":
        print("\n-- Filtro por sesgo de clase del dia previo (Test X) con salida f60/80:")
        t["alin"] = "otros"
        t.loc[(t.clase_prev.str.startswith("barrido_PDH")) & (t.dir == -1), "alin"] = "barrido: a favor"
        t.loc[(t.clase_prev.str.startswith("barrido_PDL")) & (t.dir == 1), "alin"] = "barrido: a favor"
        t.loc[(t.clase_prev.str.startswith("barrido_PDH")) & (t.dir == 1), "alin"] = "barrido: en contra"
        t.loc[(t.clase_prev.str.startswith("barrido_PDL")) & (t.dir == -1), "alin"] = "barrido: en contra"
        t.loc[(t.clase_prev.str.startswith("ruptura_arriba")) & (t.dir == 1), "alin"] = "ruptura: a favor"
        t.loc[(t.clase_prev.str.startswith("ruptura_abajo")) & (t.dir == -1), "alin"] = "ruptura: a favor"
        t.loc[(t.clase_prev.str.startswith("ruptura_arriba")) & (t.dir == -1), "alin"] = "ruptura: en contra"
        t.loc[(t.clase_prev.str.startswith("ruptura_abajo")) & (t.dir == 1), "alin"] = "ruptura: en contra"
        g = t.groupby("alin")[["f60/80", "f80/110"]].agg(["mean", "count"]).round(1)
        print(g.to_string())
