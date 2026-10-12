"""Bottom-up model of Cork's electricity need to 2040, by cause and by electoral division.

Start: Cork's metered consumption (CSO) turned into a winter peak. Then add, year by year:
  population and housing growth, business growth, heat pumps, electric cars, new large loads,
minus efficiency. Adoption of heat pumps and EVs follows an S-curve from today to the 2040 share.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import ASSUMPTIONS as A
from config import BASE_YEAR, MC_RUNS, RANDOM_STATE, SCENARIOS, TARGET_YEAR, YEARS

CENSUS_YEAR = 2022
CURRENT_EV_SHARE = 0.03   # electric share of cars around 2025 (already inside today's consumption)
CURRENT_HP_SHARE = 0.04   # heat-pump share of Cork homes around 2025 (already inside today's consumption)


def s_curve(year, start=BASE_YEAR, end=TARGET_YEAR, mid=2033, k=0.45) -> float:
    """0 at start, 1 at end, fastest around mid (typical technology uptake)."""
    f = lambda t: 1 / (1 + np.exp(-k * (t - mid)))  # noqa: E731
    return float(np.clip((f(year) - f(start)) / (f(end) - f(start)), 0, 1))


def linear(year, start, end=TARGET_YEAR) -> float:
    return float(np.clip((year - start) / (end - start), 0, None))


def baseline(cons: pd.DataFrame) -> dict:
    """Latest complete year of Cork consumption, and its peak equivalent."""
    last = int(cons.dropna(subset=["total"]).index.max())
    row = cons.loc[last]
    res = float(row.get("residential", np.nan))
    nonres = float(row.get("non_residential", np.nan))
    total = float(row["total"])
    if np.isnan(res) or np.isnan(nonres):
        res, nonres = 0.36 * total, 0.64 * total
    peak = total * 1000 / 8760 / A["load_factor"]
    return {"year": last, "res_gwh": res, "nonres_gwh": nonres, "total_gwh": total, "peak_mw": peak}


def scenario_params(s: str) -> dict:
    return {"pop": {a: v[s] for a, v in A["pop_growth_2040"].items()}, "hp_share": A["heat_pump_share_2040"][s],
            "ev_share": A["ev_share_2040"][s], "hp_kw": A["hp_peak_kw"][s], "ev_kw": A["ev_peak_kw"][s],
            "nonres_g": A["nonres_growth_pa"][s], "large_mw": A["large_loads_mw"][s],
            "eff": A["res_efficiency_2040"][s]}


def project(eds: pd.DataFrame, base: dict, p: dict, flexible: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (yearly Cork totals by cause, 2040 extra peak per electoral division)."""
    lf = A["load_factor"]
    rows = []
    ed2040 = None
    for y in YEARS:
        g_pop = eds["area"].map(p["pop"]).to_numpy() * linear(y, CENSUS_YEAR)
        g_pop_base = eds["area"].map(p["pop"]).to_numpy() * linear(BASE_YEAR, CENSUS_YEAR)
        hh_y = eds["households"].to_numpy() * (1 + g_pop)
        hh_base = eds["households"].to_numpy() * (1 + g_pop_base)
        new_hh = hh_y - hh_base
        sc = s_curve(y)

        # heat pumps: new homes get them; existing fossil-heated homes convert along the S-curve
        target_hp = p["hp_share"] * hh_y
        existing_hp = CURRENT_HP_SHARE * hh_base
        conv_room = np.maximum(target_hp - existing_hp - new_hh, 0)
        conv_room = np.minimum(conv_room, eds["hh_convertible"].to_numpy() * (1 + g_pop))
        hp_new = new_hh + sc * conv_room
        # electric cars: car numbers grow with households; EV share rises along the S-curve
        cars_y = eds["cars"].to_numpy() * (1 + g_pop)
        ev_share_y = CURRENT_EV_SHARE + sc * (p["ev_share"] - CURRENT_EV_SHARE)
        ev_new = cars_y * ev_share_y - eds["cars"].to_numpy() * (1 + g_pop_base) * CURRENT_EV_SHARE

        hp_kw = p["hp_kw"] * (1 - A["hp_flex_cut"]) if flexible else p["hp_kw"]
        ev_kw = A["ev_peak_kw_smart"] if flexible else p["ev_kw"]

        # existing demand: households grow, use per home falls with efficiency; business grows yearly
        res_gwh = base["res_gwh"] * (hh_y.sum() / hh_base.sum()) * (1 - p["eff"] * linear(y, BASE_YEAR))
        nonres_gwh = base["nonres_gwh"] * (1 + p["nonres_g"]) ** (y - BASE_YEAR)
        homes_peak = (res_gwh - base["res_gwh"]) * 1000 / 8760 / lf
        biz_peak = (nonres_gwh - base["nonres_gwh"]) * 1000 / 8760 / lf
        hp_peak = hp_new.sum() * hp_kw / 1000
        ev_peak = ev_new.sum() * ev_kw / 1000
        large = p["large_mw"] * linear(y, BASE_YEAR)
        extra = homes_peak + biz_peak + hp_peak + ev_peak + large
        if flexible:
            extra -= A["dsr_peak_cut"] * max(extra, 0)
        energy = (res_gwh + nonres_gwh + (hp_new.sum() * A["hp_kwh"] + ev_new.sum() * A["ev_kwh"]) / 1e6
                  + large * 8760 * 0.7 / 1000)
        rows.append({"year": y, "homes_mw": homes_peak, "business_mw": biz_peak, "heat_pumps_mw": hp_peak,
                     "evs_mw": ev_peak, "large_loads_mw": large, "extra_peak_mw": extra,
                     "peak_mw": base["peak_mw"] + extra, "energy_gwh": energy, "heat_pumps": hp_new.sum(),
                     "evs": ev_new.sum(), "households": hh_y.sum()})
        if y == TARGET_YEAR:
            ed_homes = homes_peak * hh_y / hh_y.sum()
            ed2040 = pd.DataFrame({
                "hp_mw": hp_new * hp_kw / 1000, "ev_mw": ev_new * ev_kw / 1000,
                "homes_mw": ed_homes,
                "biz_mw": biz_peak * eds["population"].to_numpy() / eds["population"].sum(),
            }, index=eds.index)
            ed2040["extra_mw"] = ed2040.sum(axis=1)
            if flexible:
                ed2040["extra_mw"] *= (1 - A["dsr_peak_cut"])
    return pd.DataFrame(rows).set_index("year"), ed2040


def run_scenarios(eds: pd.DataFrame, base: dict) -> dict:
    out = {}
    for s in SCENARIOS:
        p = scenario_params(s)
        yearly, ed = project(eds, base, p)
        yflex, edflex = project(eds, base, p, flexible=True)
        out[s] = {"params": p, "yearly": yearly, "ed2040": ed, "yearly_flex": yflex, "ed2040_flex": edflex}
    return out


def _tri(rng, lo, mode, hi, n):
    lo, hi = min(lo, mode, hi), max(lo, mode, hi)
    if hi - lo < 1e-12:
        return np.full(n, mode)
    return rng.triangular(lo, mode, hi, n)


def monte_carlo(eds: pd.DataFrame, base: dict, n: int = MC_RUNS) -> pd.DataFrame:
    """Every uncertain input drawn from a triangular range (low / central / high). Returns one row per draw with
    the 2040 extra peak; heavy model runs are avoided by using the scenario model's linear structure."""
    rng = np.random.default_rng(RANDOM_STATE)
    draws = {
        "pop_city": _tri(rng, *[A["pop_growth_2040"]["Cork City"][s] for s in SCENARIOS], n),
        "pop_county": _tri(rng, *[A["pop_growth_2040"]["Cork County"][s] for s in SCENARIOS], n),
        "hp_share": _tri(rng, *[A["heat_pump_share_2040"][s] for s in SCENARIOS], n),
        "ev_share": _tri(rng, *[A["ev_share_2040"][s] for s in SCENARIOS], n),
        "hp_kw": _tri(rng, *[A["hp_peak_kw"][s] for s in SCENARIOS], n),
        "ev_kw": _tri(rng, *[A["ev_peak_kw"][s] for s in SCENARIOS], n),
        "nonres_g": _tri(rng, *[A["nonres_growth_pa"][s] for s in SCENARIOS], n),
        "large_mw": _tri(rng, *[A["large_loads_mw"][s] for s in SCENARIOS], n),
        "eff": _tri(rng, *[A["res_efficiency_2040"][s] for s in SCENARIOS], n),
    }
    # Evaluate the 2040 model per draw (vectorised over draws, using 2040 only)
    out = []
    for i in range(n):
        p = {"pop": {"Cork City": draws["pop_city"][i], "Cork County": draws["pop_county"][i]},
             "hp_share": draws["hp_share"][i], "ev_share": draws["ev_share"][i], "hp_kw": draws["hp_kw"][i],
             "ev_kw": draws["ev_kw"][i], "nonres_g": draws["nonres_g"][i], "large_mw": draws["large_mw"][i],
             "eff": draws["eff"][i]}
        out.append(_extra_2040(eds, base, p))
    df = pd.DataFrame(draws)
    df["extra_mw"] = [o[0] for o in out]
    df["extra_mw_flex"] = [o[1] for o in out]
    return df


def _extra_2040(eds, base, p) -> tuple[float, float]:
    """Fast 2040-only version of project(), for Monte Carlo."""
    lf = A["load_factor"]
    y = TARGET_YEAR
    g_pop = eds["area"].map(p["pop"]).to_numpy()
    g_pop_base = g_pop * linear(BASE_YEAR, CENSUS_YEAR)
    g_pop = g_pop * linear(y, CENSUS_YEAR)
    hh = eds["households"].to_numpy()
    hh_y, hh_base = hh * (1 + g_pop), hh * (1 + g_pop_base)
    new_hh = hh_y - hh_base
    conv = np.minimum(np.maximum(p["hp_share"] * hh_y - CURRENT_HP_SHARE * hh_base - new_hh, 0),
                      eds["hh_convertible"].to_numpy() * (1 + g_pop))
    hp_new = (new_hh + conv).sum()
    cars = eds["cars"].to_numpy()
    ev_new = (cars * (1 + g_pop) * p["ev_share"] - cars * (1 + g_pop_base) * CURRENT_EV_SHARE).sum()
    res = base["res_gwh"] * (hh_y.sum() / hh_base.sum()) * (1 - p["eff"])
    nonres = base["nonres_gwh"] * (1 + p["nonres_g"]) ** (y - BASE_YEAR)
    common = (res - base["res_gwh"] + nonres - base["nonres_gwh"]) * 1000 / 8760 / lf + p["large_mw"]
    extra = common + hp_new * p["hp_kw"] / 1000 + ev_new * p["ev_kw"] / 1000
    flex = common + hp_new * p["hp_kw"] * (1 - A["hp_flex_cut"]) / 1000 + ev_new * A["ev_peak_kw_smart"] / 1000
    flex -= A["dsr_peak_cut"] * max(flex, 0)
    return float(extra), float(flex)


def sensitivity(eds: pd.DataFrame, base: dict) -> pd.DataFrame:
    """Tornado: swing in 2040 extra peak when one input moves from low to high, others central."""
    names = {"pop": "Population growth", "hp_share": "Heat pump uptake", "ev_share": "EV uptake",
             "hp_kw": "Heat pump peak per home", "ev_kw": "EV peak per car (charging behaviour)",
             "nonres_g": "Business growth", "large_mw": "New large loads", "eff": "Efficiency"}
    central = scenario_params("central")
    rows = []
    for k, label in names.items():
        vals = []
        for s in ("low", "high"):
            p = {**central, k: scenario_params(s)[k]}
            vals.append(_extra_2040(eds, base, p)[0])
        rows.append({"input": label, "low": vals[0], "high": vals[1], "swing": abs(vals[1] - vals[0])})
    c = _extra_2040(eds, base, central)[0]
    return pd.DataFrame(rows).sort_values("swing").assign(central=c)
