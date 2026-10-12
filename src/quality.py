"""Checks before planning. A FAIL stops the run; WARNs are reported and explained in the report."""

from __future__ import annotations

from datetime import datetime



from config import REPORTS_DIR

CORK_POP_2022 = 584_156   # Census 2022: Cork City 224,004 + Cork County 360,152


def run_checks(cons, eds, ed_meta, polys, esbn_info, cork, forecast, demo) -> dict:
    res = []
    add = lambda s, c, d: res.append((s, c, d))  # noqa: E731

    ok_cons = cons is not None and len(cons) > 3
    add("PASS" if ok_cons else "FAIL", "Cork metered consumption found (CSO MEC03)",
        f"{cons.index.min()}–{cons.index.max()}, latest total {cons['total'].iloc[-1]:,.0f} GWh" if ok_cons else "missing")
    if ok_cons and {"residential", "non_residential"} <= set(cons.columns):
        gap = (cons["residential"] + cons["non_residential"] - cons["total"]).abs().max()
        add("PASS" if gap <= 0.02 * cons["total"].max() else "WARN", "Sectors add up to the total",
            f"largest gap {gap:,.0f} GWh")

    n = len(eds)
    add("PASS" if n > 100 else "FAIL", "Cork electoral divisions found",
        f"{n} EDs: " + ", ".join(f"{k} {v}" for k, v in ed_meta["areas"].items()))
    pop = eds["population"].sum()
    dev = abs(pop / CORK_POP_2022 - 1)
    add("PASS" if demo or dev < 0.06 else "WARN", "Population close to Census 2022 total for Cork",
        f"{pop:,.0f}" + ("" if demo else f" vs {CORK_POP_2022:,} headline ({100 * dev:.1f}% apart; area-level "
                         "census tables use a slightly different population definition from the headline figure)"))
    e_share = eds["hh_electric_heat"].sum() / eds["households"].sum()
    add("PASS" if 0.02 < e_share < 0.4 else "WARN", "Electric heating share plausible", f"{100 * e_share:.1f}% of homes")
    cph = eds["cars"].sum() / eds["households"].sum()
    add("PASS" if 0.7 < cph < 2.3 else "WARN", "Cars per household plausible", f"{cph:.2f}")
    if polys is None:
        add("WARN", "Map boundaries", "not available: maps skipped")
    else:
        matched = len({g for g, _ in polys} & set(eds.index)) / max(n, 1)
        add("PASS" if matched > 0.95 else "WARN", "Boundaries matched to EDs", f"{100 * matched:.1f}%")

    for key in ("headroom", "heatmap"):
        k = esbn_info.get(f"{key}_sheets", 0)
        add("PASS" if k else "WARN", f"ESB Networks {key} workbook read",
            f"{k} sheet(s) with station data" if k else "not available or not recognised: see esbn_workbook_structure.txt")
    nm = len(esbn_info.get("name_matches", []))
    if nm:
        add("PASS", "Station names matched between ESB Networks workbooks",
            f"{nm} matched by near-identical names (listed in reports/name_matches.csv)")
    nc = len(cork) if cork is not None else 0
    add("PASS" if nc >= 10 else "WARN", "Cork substations identified",
        f"{nc} stations ({esbn_info.get('method') or 'no method'}); {esbn_info.get('with_location', 0)} with location, "
        f"{esbn_info.get('with_headroom', 0)} with spare capacity")
    if forecast is not None:
        yrs = sorted(int(y) for y in forecast["year"].unique())
        add("PASS" if 2040 in yrs else "WARN", "ESB Networks forecasts for Cork stations",
            f"scenarios {sorted(forecast['scenario'].unique())}, years {yrs[0]}–{yrs[-1]}")
    else:
        add("WARN", "ESB Networks forecasts for Cork stations", "not found: cross-check skipped")

    n_fail = sum(s == "FAIL" for s, *_ in res)
    n_warn = sum(s == "WARN" for s, *_ in res)
    summary = f"QC {'FAILED' if n_fail else 'PASSED'}: {len(res) - n_fail - n_warn} passed, {n_warn} warnings, {n_fail} failures"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "qc_log.txt").write_text("\n".join(
        [f"Quality control log - {datetime.now():%Y-%m-%d %H:%M}", summary, ""] + [f"[{s}] {c}: {d}" for s, c, d in res]
        + ["", f"Heating categories: {ed_meta['heating_categories']}", f"Car categories: {ed_meta['car_categories']}",
           f"All car columns: {ed_meta.get('car_columns_all')}", f"Population total columns: "
           f"{ed_meta.get('population_columns')}", f"Cork area labels: {ed_meta.get('area_labels')}"])
        + "\n", encoding="utf-8")
    return {"passed": n_fail == 0, "summary": summary, "results": res}


