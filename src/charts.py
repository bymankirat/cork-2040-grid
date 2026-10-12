"""Charts. Each title states the finding."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from config import FIG_DIR, SCENARIO_NAMES, TARGET_YEAR  # noqa: E402

BLUE, ORANGE, AQUA, GREY, LIGHT = "#2a78d6", "#eb6834", "#1baf7a", "#9a9a95", "#9fc3ee"
PURPLE, YELLOW = "#8b5cf6", "#e0a100"
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
SEQ = ["#eaf2fc", "#c3dbf6", "#8fbbee", "#4f93e0", "#2a78d6", "#174f96"]
SCOL = {"low": AQUA, "central": BLUE, "high": ORANGE}
CAUSE = {"homes_mw": ("New homes & population", GREY), "business_mw": ("Business growth", PURPLE),
         "heat_pumps_mw": ("Heat pumps", ORANGE), "evs_mw": ("Electric cars", BLUE),
         "large_loads_mw": ("New large loads", YELLOW)}
ACTION = {"none": ("Enough spare capacity", AQUA), "upgrade": ("Upgrade needed", YELLOW),
          "new station": ("New station(s) needed", ORANGE)}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": GRID,
    "axes.labelcolor": INK_2, "axes.titlecolor": INK, "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "xtick.color": INK_2, "ytick.color": INK_2, "font.size": 10.5, "font.family": "DejaVu Sans",
    "legend.frameon": False,
})


def _save(fig, name):
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    p = FIG_DIR / name
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(p)


def _sub(ax, text):
    ax.text(0, 1.02, text, transform=ax.transAxes, color=INK_2, fontsize=10, va="bottom")


def polys(geojson: Path | None):
    if geojson is None:
        return None
    out = []
    for f in json.loads(Path(geojson).read_text())["features"]:
        g, guid = f.get("geometry") or {}, f["properties"].get("ED_GUID")
        if g.get("type") == "Polygon":
            rings = [np.asarray(g["coordinates"][0])]
        elif g.get("type") == "MultiPolygon":
            rings = [np.asarray(p[0]) for p in g["coordinates"]]
        else:
            continue
        out.append((guid, rings))
    return out


# --------------------------------------------------------------------------- 1. history
def history(cons: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(10, 3.8))
    x = cons.index.astype(int)
    r = cons.get("residential", pd.Series(0, index=cons.index))
    nr = cons.get("non_residential", cons["total"] - r)
    ax.bar(x, nr, color=BLUE, width=0.65, label="Business & industry")
    ax.bar(x, r, bottom=nr, color=LIGHT, width=0.65, label="Homes")
    for xi, t in zip(x, cons["total"]):
        ax.text(xi, t + 25, f"{t:,.0f}", ha="center", fontsize=8.5, color=INK_2)
    ax.set_ylabel("GWh per year")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left", ncol=2, bbox_to_anchor=(0, 0.98))
    ax.set_ylim(0, cons["total"].max() * 1.22)
    g = 100 * (cons["total"].iloc[-1] / cons["total"].iloc[0] - 1)
    ax.set_title(f"Cork used {cons['total'].iloc[-1]:,.0f} GWh in {x[-1]}, {g:+.0f}% since {x[0]}", pad=26)
    _sub(ax, "Metered electricity consumption, Co. Cork (CSO). About two-thirds is business and industry.")
    return _save(fig, "01_history.png")


# --------------------------------------------------------------------------- 2. paths
def paths(scen: dict, base: dict, plan: dict) -> str:
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    for s, r in scen.items():
        y = r["yearly"]["peak_mw"]
        ax.plot(y.index, y.values, color=SCOL[s], lw=2.4)
        ax.annotate(f"{SCENARIO_NAMES[s].split(' (')[0]}: {y.iloc[-1]:,.0f} MW", (y.index[-1], y.iloc[-1]),
                    xytext=(6, 0), textcoords="offset points", va="center", fontsize=9.5, color=SCOL[s],
                    fontweight="bold")
    f = scen["central"]["yearly_flex"]["peak_mw"]
    ax.plot(f.index, f.values, color=BLUE, lw=1.8, ls="--")
    ax.annotate(f"Central + flexibility: {f.iloc[-1]:,.0f} MW", (f.index[-1], f.iloc[-1]), xytext=(6, -2),
                textcoords="offset points", va="top", fontsize=9, color=BLUE)
    m = plan["summary"]["extra_mw"]
    ax.errorbar([TARGET_YEAR + 0.25], [base["peak_mw"] + m[50]], yerr=[[m[50] - m[10]], [m[90] - m[50]]],
                color=INK_2, capsize=4, lw=1.2)
    ax.axhline(base["peak_mw"], color=INK_2, lw=0.8, ls=":")
    ax.annotate(f"today ≈ {base['peak_mw']:,.0f} MW", (2040, base["peak_mw"]), xytext=(6, 0),
                textcoords="offset points", va="center", fontsize=9, color=INK_2)
    ax.set_xlim(2025, 2045.5)
    ax.set_xticks(range(2025, 2041, 5))
    ax.set_ylabel("Winter peak demand, Co. Cork (MW)")
    c = scen["central"]["yearly"]["peak_mw"]
    ax.set_title(f"Cork's winter peak could grow {100 * (c.iloc[-1] / base['peak_mw'] - 1):.0f}% by 2040 "
                 f"(central case)", pad=26)
    _sub(ax, "Three scenarios; dashed = central with smart EV charging, heat-pump flexibility and demand response; "
             "bar = 10–90% Monte Carlo range")
    return _save(fig, "02_peak_paths.png")


# --------------------------------------------------------------------------- 3. drivers
def drivers(scen: dict) -> str:
    fig, ax = plt.subplots(figsize=(10.5, 3.6))
    order = ["low", "central", "high"]
    left = np.zeros(3)
    for k, (lab, col) in CAUSE.items():
        v = np.array([scen[s]["yearly"].loc[TARGET_YEAR, k] for s in order])
        pos = np.clip(v, 0, None)
        ax.barh([SCENARIO_NAMES[s] for s in order], pos, left=left, color=col, height=0.6, label=lab)
        for i, (vv, l0) in enumerate(zip(pos, left)):
            if vv > 25:
                ax.text(l0 + vv / 2, i, f"{vv:.0f}", ha="center", va="center", fontsize=9,
                        color="white" if col in (BLUE, PURPLE, ORANGE) else INK)
        left += pos
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.42), ncol=5, fontsize=9)
    ax.set_xlabel("Extra winter peak by 2040 (MW)")
    hp = scen["central"]["yearly"].loc[TARGET_YEAR]
    top = max(CAUSE, key=lambda k: hp[k])
    ax.set_title(f"{CAUSE[top][0]} drive most of the growth", pad=26)
    _sub(ax, "Extra 2040 peak versus today, by cause (efficiency gains offset part of the housing effect)")
    return _save(fig, "03_drivers.png")


# --------------------------------------------------------------------------- 4. map
def cork_map(scen: dict, eds: pd.DataFrame, pl, plan: dict) -> str | None:
    if pl is None:
        return None
    ed = scen["central"]["ed2040"]["extra_mw"]
    area_km2 = {}
    for g, rings in pl:
        a = 0.0
        for r in rings:
            x, y = r[:, 0] * 111.32 * np.cos(np.radians(51.9)), r[:, 1] * 110.57
            a += 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
        area_km2[g] = a
    dens = (ed / pd.Series(area_km2).reindex(ed.index)).replace([np.inf, -np.inf], np.nan)
    bins = np.nanquantile(dens.dropna(), [0, .2, .4, .6, .8, .95, 1]) if dens.notna().any() else [0, 1]
    colour = {g: SEQ[min(int(np.searchsorted(bins[1:-1], v)), len(SEQ) - 1)] if pd.notna(v) else "#dddddd"
              for g, v in dens.items()}

    fig = plt.figure(figsize=(11.5, 7.6))
    ax = fig.add_axes([0.0, 0.0, 0.58, 0.88])
    ax2 = fig.add_axes([0.60, 0.30, 0.39, 0.55])
    for a, bbox in ((ax, None), (ax2, (-8.62, -8.30, 51.83, 51.97))):
        verts, cols = [], []
        for g, rings in pl:
            for r in rings:
                if bbox and not (r[:, 0].max() > bbox[0] and r[:, 0].min() < bbox[1]
                                 and r[:, 1].max() > bbox[2] and r[:, 1].min() < bbox[3]):
                    continue
                verts.append(r)
                cols.append(colour.get(g, "#dddddd"))
        a.add_collection(PolyCollection(verts, facecolors=cols, edgecolors=SURFACE, linewidths=0.15))
        a.autoscale_view()
        if bbox:
            a.set_xlim(bbox[0], bbox[1])
            a.set_ylim(bbox[2], bbox[3])
        a.set_aspect(1 / np.cos(np.radians(51.9)))
        a.set_xticks([])
        a.set_yticks([])
        a.grid(False)
        st = plan.get("stations", {}).get(("central", False))
        if st is not None:
            for act, (lab, col) in ACTION.items():
                s = st[st["action"] == act]
                a.scatter(s["lon"], s["lat"], s=np.where(s["kv"] == 110, 70, 32), color=col, edgecolor=INK,
                          linewidth=0.6, zorder=3, marker="o")
        if bbox:
            for sp in a.spines.values():
                sp.set_visible(True)
                sp.set_color(GRID)
            a.set_title("Cork City close-up", fontsize=10, loc="left")
        else:
            a.axis("off")
    fig.text(0.01, 0.975, "Where Cork's new demand lands by 2040, and which substations can take it",
             fontsize=13, fontweight="bold", color=INK, va="top")
    fig.text(0.01, 0.94, "Extra winter peak per km² (central scenario); dots = 110 kV (large) and 38 kV (small) "
             "stations, coloured by verdict", fontsize=10, color=INK_2, va="top")
    handles = [Patch(color=SEQ[i], label=lab) for i, lab in enumerate(
        ["Lowest 20%", "20–40%", "40–60%", "60–80%", "80–95%", "Top 5%"])]
    if plan.get("stations"):
        handles += [Line2D([], [], marker="o", ls="", color=c, markeredgecolor=INK, label=l)
                    for l, c in ACTION.values()]
    lg = fig.add_axes([0.60, 0.02, 0.39, 0.25])
    lg.axis("off")
    lg.legend(handles=handles, loc="upper left", fontsize=9, ncol=2, title="Extra load density   /   station verdict",
              title_fontsize=9)
    return _save(fig, "04_map.png")


# --------------------------------------------------------------------------- 5. stations
def stations(plan: dict) -> str | None:
    st = plan.get("stations", {}).get(("central", False))
    if st is None or not len(st):
        return None
    s = st.sort_values("deficit_mw", ascending=False).head(14)[::-1]
    fig, ax = plt.subplots(figsize=(10.5, 0.42 * len(s) + 1.6))
    y = np.arange(len(s))
    ax.barh(y, s["extra_mw"], color=LIGHT, height=0.62, label="Extra load by 2040")
    ax.scatter(s["headroom_mw"], y, color=INK, marker="|", s=260, zorder=3, label="Spare capacity today")
    for i, (_, r) in enumerate(s.iterrows()):
        lab, col = ACTION.get(r["action"], ("", GREY))
        yr = plan.get("exhaust_year", pd.Series(dtype=float)).get(_)
        ax.text(max(r["extra_mw"], r["headroom_mw"]) + 1, i,
                f"{lab}" + (f" (full by {int(yr)})" if yr and not pd.isna(yr) else ""), va="center", fontsize=8.8,
                color=col if col != YELLOW else "#a07400")
    ax.set_yticks(y)
    ax.set_yticklabels([n if "kv" in str(n).lower() else f"{n} ({int(k) if pd.notna(k) else '?'} kV)"
                        for n, k in zip(s["station"], s["kv"])], fontsize=9)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, max(s["extra_mw"].max(), s["headroom_mw"].max()) * 1.55)
    ax.legend(loc="lower right", fontsize=9)
    ax.set_xlabel("MW")
    n_short = int((st["deficit_mw"] > 0).sum())
    ax.set_title(f"{n_short} of {len(st)} Cork substations run short of capacity by 2040 (central case)", pad=26)
    _sub(ax, "Stations with the largest shortfall: extra load assigned from nearby areas versus today's spare capacity")
    return _save(fig, "05_stations.png")


# --------------------------------------------------------------------------- 6. budget
def budget(plan: dict) -> str:
    mc = plan["mc"]
    s = plan["summary"]
    fig, ax = plt.subplots(figsize=(10.5, 4))
    hi = np.percentile(mc["cost_m"], 99)
    bins = np.linspace(0, max(hi, 1), 45)
    ax.hist(mc["cost_m"].clip(upper=hi), bins=bins, color=BLUE, alpha=0.85, label="Without flexibility")
    ax.hist(mc["cost_m_flex"].clip(upper=hi), bins=bins, color=AQUA, alpha=0.6, label="With flexibility")
    for p, ls in ((10, ":"), (50, "-"), (90, ":")):
        ax.axvline(s["cost_m"][p], color=INK, lw=1, ls=ls)
    ax.text(s["cost_m"][50], ax.get_ylim()[1] * 0.95, f"  median €{s['cost_m'][50]:,.0f}m", fontsize=9.5,
            va="top", color=INK, fontweight="bold")
    ax.set_xlabel("Station investment needed in Cork by 2040 (€ million, 2026 prices)")
    ax.set_ylabel("Simulations")
    ax.legend(loc="upper right")
    ax.grid(axis="x", visible=False)
    ax.set_title(f"€{s['cost_m'][10]:,.0f}–{s['cost_m'][90]:,.0f}m in substations; flexibility could save about "
                 f"€{max(s['saving_m'], 0):,.0f}m", pad=26)
    _sub(ax, f"{len(mc):,} Monte Carlo runs over demand, station size and unit cost; 10%, 50% and 90% marked. "
             "Stations only: lines, land and transmission excluded.")
    return _save(fig, "06_budget.png")


# --------------------------------------------------------------------------- 7. tornado
def tornado(sens: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(10, 4))
    c = sens["central"].iloc[0]
    y = np.arange(len(sens))
    ax.barh(y, sens["high"] - c, left=c, color=ORANGE, height=0.6, label="Input at its high value")
    ax.barh(y, sens["low"] - c, left=c, color=AQUA, height=0.6, label="Input at its low value")
    ax.axvline(c, color=INK, lw=1)
    ax.set_yticks(y)
    ax.set_yticklabels(sens["input"])
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", fontsize=9)
    ax.set_xlabel("Extra winter peak by 2040 (MW)")
    ax.set_title(f"{sens['input'].iloc[-1]} is the biggest uncertainty", pad=26)
    _sub(ax, "One input moved from low to high, all others central")
    return _save(fig, "07_sensitivity.png")


# --------------------------------------------------------------------------- 8. ESB Networks view
def esbn_chart(view: dict | None) -> str | None:
    if view is None:
        return None
    t = view["table"]
    fig, ax = plt.subplots(figsize=(10.5, 4))
    cols = {"Conservative": AQUA, "Best View": BLUE, "Base": PURPLE, "Aggressive": ORANGE}
    for scn, g in t.groupby("scenario"):
        g = g.sort_values("year")
        ax.plot(g["year"], g["negative"], "o-", color=cols.get(scn, GREY), lw=2, ms=4)
        ax.annotate(scn, (g["year"].iloc[-1], g["negative"].iloc[-1]), xytext=(5, 0), textcoords="offset points",
                    va="center", fontsize=9.5, color=cols.get(scn, GREY), fontweight="bold")
    ax.set_ylabel("Cork stations with no firm headroom")
    ax.set_xlim(t["year"].min() - 0.5, t["year"].max() + 4)
    g40 = t[t["year"] == 2040]
    msg = (f"by 2040, {int(g40['negative'].min())}–{int(g40['negative'].max())} Cork stations are full"
           if len(g40) else "Cork stations over capacity, by scenario")
    ax.set_title("ESB Networks' own forecasts: " + msg, pad=26)
    _sub(ax, f"Cork stations (of {int(t['stations'].max())}) with no firm demand headroom left, by scenario; "
             "Demand Capacity Headroom Report 2025")
    return _save(fig, "08_esbn_view.png")
