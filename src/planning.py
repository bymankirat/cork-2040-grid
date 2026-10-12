"""From extra demand to network investment: which stations run out, what to build, and what it costs.

Spatial method (when station locations and spare capacity are available): each electoral division's extra
2040 peak is assigned to its nearest 110 kV / 38 kV station. Where the extra load exceeds the station's spare
capacity, the shortfall is met by an upgrade (if small) or new station(s) (if large). Otherwise an aggregate
method sizes new capacity for Cork as a whole. Costs are Monte Carlo ranges, never single numbers.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from config import ASSUMPTIONS as A
from config import NETWORK, RANDOM_STATE, SHARE_110KV, TARGET_YEAR


def ed_centroids(polys) -> pd.DataFrame:
    rows = []
    for guid, rings in polys:
        r = max(rings, key=len)
        rows.append({"ed_guid": guid, "lon": float(r[:, 0].mean()), "lat": float(r[:, 1].mean())})
    return pd.DataFrame(rows).set_index("ed_guid")


def _km(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = (np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * np.arcsin(np.sqrt(a))


def hv_stations(cork: pd.DataFrame) -> pd.DataFrame:
    if cork is None or not len(cork):
        return pd.DataFrame()
    st = cork.copy()
    if st["kv"].notna().any():
        st = st[st["kv"].isin([38, 110])]
    if "demand_station" in st and st["demand_station"].any():
        st = st[st["demand_station"]]  # only stations that serve demand take new load
    return st


def assign(ed_extra: pd.Series, centroids: pd.DataFrame, st: pd.DataFrame) -> pd.Series:
    """Extra MW per station: each ED to its nearest station."""
    s = st.dropna(subset=["lat", "lon"])
    c = centroids.reindex(ed_extra.index).dropna()
    d = _km(c["lat"].to_numpy()[:, None], c["lon"].to_numpy()[:, None], s["lat"].to_numpy()[None, :],
            s["lon"].to_numpy()[None, :])
    nearest = s.index.to_numpy()[d.argmin(axis=1)]
    return pd.Series(ed_extra.reindex(c.index).to_numpy(), index=nearest).groupby(level=0).sum()


def _mw(mva: float) -> float:
    return mva * A["power_factor"]


def actions(deficit_mw: pd.Series, kv: pd.Series, size: dict | None = None) -> pd.DataFrame:
    """Per station: none / upgrade / new station(s), using most-likely sizes unless 'size' is given."""
    size = size or {k: v["mva"][1] for k, v in NETWORK.items()}
    rows = []
    for k, dmw in deficit_mw.items():
        lvl = "110kv" if kv.get(k) == 110 else "38kv"
        if dmw <= 0:
            rows.append({"key": k, "action": "none", "level": lvl, "n_new": 0, "n_uprate": 0})
        elif dmw <= _mw(size[f"uprate_{lvl}"]):
            rows.append({"key": k, "action": "upgrade", "level": lvl, "n_new": 0, "n_uprate": 1})
        else:  # upgrade the existing station first, then add new station(s) for the rest
            rest = dmw - _mw(size[f"uprate_{lvl}"])
            rows.append({"key": k, "action": "new station", "level": lvl,
                         "n_new": math.ceil(rest / _mw(size[f"new_{lvl}"])), "n_uprate": 1})
    return pd.DataFrame(rows).set_index("key") if rows else pd.DataFrame()


def _tri(rng, t, n):
    return rng.triangular(t[0], t[1], t[2], n) if t[2] > t[0] else np.full(n, t[1])


def plan(scen: dict, mc: pd.DataFrame, cork: pd.DataFrame, centroids: pd.DataFrame | None) -> dict:
    st = hv_stations(cork)
    spatial = (centroids is not None and len(st) >= 3 and st["lat"].notna().sum() >= 3
               and "headroom_now" in st and st["headroom_now"].notna().sum() >= 3)
    out = {"method": "spatial" if spatial else "aggregate", "n_stations": int(len(st))}
    rng = np.random.default_rng(RANDOM_STATE)
    n = len(mc)
    central_extra = scen["central"]["yearly"].loc[TARGET_YEAR, "extra_peak_mw"]

    if spatial:
        st = st.dropna(subset=["lat", "lon"]).copy()
        st["headroom_mw"] = st["headroom_now"].fillna(0).clip(lower=0)
        per = {}
        for s, r in scen.items():
            for flex in (False, True):
                ed = r["ed2040_flex" if flex else "ed2040"]["extra_mw"]
                load = assign(ed, centroids, st).reindex(st.index).fillna(0)
                deficit = (load - st["headroom_mw"]).clip(lower=0)
                act = actions(deficit, st["kv"])
                per[(s, flex)] = pd.DataFrame({"station": st["station"], "kv": st["kv"], "lat": st["lat"],
                                               "lon": st["lon"], "headroom_mw": st["headroom_mw"],
                                               "extra_mw": load, "deficit_mw": deficit}).join(act)
        out["stations"] = per
        base_load = assign(scen["central"]["ed2040"]["extra_mw"], centroids, st).reindex(st.index).fillna(0)
        base_flex = assign(scen["central"]["ed2040_flex"]["extra_mw"], centroids, st).reindex(st.index).fillna(0)
        # year each station runs out (central): station load grows in proportion to Cork's extra peak
        yearly = scen["central"]["yearly"]["extra_peak_mw"]
        frac = (yearly / central_extra).clip(lower=0)
        def first_year(i):
            if base_load[i] <= st["headroom_mw"][i]:
                return None
            hit = frac[frac * base_load[i] > st["headroom_mw"][i]]
            return int(hit.index.min()) if len(hit) else None
        out["exhaust_year"] = pd.Series({i: first_year(i) for i in st.index})
    else:
        headroom_total = float(st["headroom_now"].clip(lower=0).sum()) if len(st) and "headroom_now" in st else 0.0
        out["headroom_total"] = headroom_total

    # ---------------- Monte Carlo cost
    res = {"stations_new": [], "uprates": [], "cost_m": [], "stations_new_flex": [], "cost_m_flex": []}
    sizes = {k: _tri(rng, v["mva"], n) for k, v in NETWORK.items()}
    if spatial:
        hr = st["headroom_mw"].to_numpy()
        is110 = (st["kv"] == 110).to_numpy()
    costs = {k: _tri(rng, v["cost_m"], n) for k, v in NETWORK.items()}
    for i in range(n):
        size = {k: sizes[k][i] for k in NETWORK}
        for flex in (False, True):
            extra = mc["extra_mw_flex" if flex else "extra_mw"].iloc[i]
            if spatial:
                load = (base_flex if flex else base_load) * (extra / max(
                    scen["central"]["yearly_flex" if flex else "yearly"].loc[TARGET_YEAR, "extra_peak_mw"], 1e-9))
                d = np.clip(load.to_numpy() - hr, 0, None)
                counts = {}
                for lvl, m in (("110kv", is110), ("38kv", ~is110)):
                    dd = d[m]
                    upc = _mw(size[f"uprate_{lvl}"])
                    up = dd > 0
                    nw = np.where(dd > upc, np.ceil((dd - upc) / _mw(size[f"new_{lvl}"])), 0)
                    counts[lvl] = (int(nw.sum()), int(up.sum()))
                (n110, u110), (n38, u38) = counts["110kv"], counts["38kv"]
            else:
                need = max(0.0, extra - out["headroom_total"])
                n110 = math.ceil(need * SHARE_110KV / _mw(size["new_110kv"]))
                n38 = math.ceil(need * (1 - SHARE_110KV) / _mw(size["new_38kv"]))
                u110 = u38 = 0
            cost = (n110 * costs["new_110kv"][i] + n38 * costs["new_38kv"][i] + u110 * costs["uprate_110kv"][i]
                    + u38 * costs["uprate_38kv"][i])
            if flex:
                res["stations_new_flex"].append(n110 + n38)
                res["cost_m_flex"].append(cost)
            else:
                res["stations_new"].append(n110 + n38)
                res["uprates"].append(u110 + u38)
                res["cost_m"].append(cost)
                res.setdefault("n110", []).append(n110)
                res.setdefault("n38", []).append(n38)
    mcres = pd.DataFrame(res)
    out["mc"] = mcres

    def q(col):
        return {p: float(np.percentile(mcres[col], p)) for p in (10, 50, 90)}
    out["summary"] = {"cost_m": q("cost_m"), "cost_m_flex": q("cost_m_flex"), "stations_new": q("stations_new"),
                      "stations_new_flex": q("stations_new_flex"), "uprates": q("uprates"), "n110": q("n110"),
                      "n38": q("n38"), "extra_mw": {p: float(np.percentile(mc["extra_mw"], p)) for p in (10, 50, 90)},
                      "extra_mw_flex": {p: float(np.percentile(mc["extra_mw_flex"], p)) for p in (10, 50, 90)}}
    s = out["summary"]
    out["summary"]["saving_m"] = s["cost_m"][50] - s["cost_m_flex"][50]
    return out


def esbn_view(forecast: pd.DataFrame | None, cork: pd.DataFrame) -> dict | None:
    """What ESB Networks' own workbook says about Cork's stations, by scenario and year."""
    if forecast is None or not len(forecast):
        return None
    f = forecast.copy()
    head = f[f["metric"] == "headroom"]
    if not len(head) and "capacity_now" in cork:
        dem = f[f["metric"] == "demand"].copy()
        dem["value"] = dem["key"].map(cork["capacity_now"]) - dem["value"]
        head = dem.dropna(subset=["value"])
    if not len(head):
        return None
    head = head.groupby(["scenario", "year", "key"])["value"].mean().reset_index()
    # ESB Networks publishes 'no headroom' as 0 / -0.0001, so a station counts as full at <= 0.01
    tab = head.groupby(["scenario", "year"]).agg(
        stations=("key", "nunique"), negative=("value", lambda v: int((v <= 0.01).sum())),
        deficit=("value", lambda v: float(-v[v < 0].sum())), headroom=("value", lambda v: float(v.clip(lower=0).sum())))
    years = sorted(head["year"].unique())
    return {"table": tab.reset_index(), "years": years, "per_station": head,
            "unit": next((u for u in f["unit"].unique() if u), "")}
