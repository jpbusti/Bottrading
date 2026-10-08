"""Une NQ por contrato (2016-10 -> 2021-10-08, con premercado) con el continuo c.0 RTH (2021-10-11 -> 2026-10) etiquetando contratos por periodo de roll."""
import sys, datetime as dt, pandas as pd, numpy as np
a = pd.read_pickle(sys.argv[1])
c = pd.read_csv(sys.argv[2])
c["Datetime"] = pd.to_datetime(c["Datetime"], utc=True).dt.tz_convert("America/New_York")
c["fecha"] = c.Datetime.dt.date
ult = a.fecha.max()
c = c[c.fecha > ult].copy()
dias = sorted(c.fecha.unique())
# 3er viernes de mar/jun/sep/dic -> el roll del continuo cae el siguiente dia habil (verificado por saltos de apertura)
cortes = []
for y in range(2021, 2027):
    for mth in (3, 6, 9, 12):
        fr = [x for x in pd.date_range(f"{y}-{mth:02d}-15", f"{y}-{mth:02d}-21") if x.weekday() == 4][0].date()
        cortes.append(fr)
cortes = [x for x in cortes if dias[0] < x < dias[-1]]
lab = {}; drop = set()
for d in dias:
    lab[d] = "NQc%d" % sum(d > x for x in cortes)
for x in cortes:
    pos = [i for i, d in enumerate(dias) if d > x][0]          # dia de switch
    for i in (pos - 2, pos - 1, pos, pos + 1):                    # margen de seguridad (descartar)
        if 0 <= i < len(dias): drop.add(dias[i])
c["symbol"] = c.fecha.map(lab)
c = c[~c.fecha.isin(drop)]
print("cortes", cortes[:3], "...", len(cortes), "dias descartados", len(drop), "dias continuo usados", c.fecha.nunique())
out = pd.concat([a, c[a.columns]], ignore_index=True)
out.to_pickle(sys.argv[3]); print(out.fecha.nunique(), "dias", out.fecha.min(), out.fecha.max())
