"""Cork 2040: how much power, how many substations, what budget?

    python run_pipeline.py            # downloads CSO + ESB Networks data (first run a few minutes)
    python run_pipeline.py --demo     # simulated data for testing (outputs marked DEMO)
    python run_pipeline.py --refresh  # re-download everything (run yearly when new data is published)
"""

import argparse
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))
warnings.filterwarnings("ignore")

import charts  # noqa: E402
import data  # noqa: E402
import esbn  # noqa: E402
import planning  # noqa: E402
import quality  # noqa: E402
import report  # noqa: E402
import scenarios  # noqa: E402
import webmap  # noqa: E402
from config import DOCS_DIR, REPORTS_DIR, SCENARIO_NAMES, TARGET_YEAR  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("1/7  Getting data ...")
    if args.demo:
        from make_demo_data import make
        d = make()
        cso, bpath, wb = d["cso"], d["boundaries"], d["esbn"]
    else:
        try:
            cso = data.download_cso(force=args.refresh)
        except Exception as e:  # noqa: BLE001
            sys.exit(f"\n[!] CSO download failed: {e}\n    Check your internet connection and run again.")
        bpath = data.download_boundaries(force=args.refresh)
        wb = data.download_esbn(force=args.refresh)

    print("2/7  Reading Cork's consumption, homes, heating and cars ...")
    cons = data.read_consumption(cso["consumption"])
    eds, ed_meta = data.build_eds(cso)
    pl = charts.polys(bpath)
    if pl is not None:
        pl = [(g, r) for g, r in pl if g in eds.index]

    print("3/7  Reading ESB Networks workbooks (about a minute) ...")
    parsed, texts = {}, []
    for key, path in wb.items():
        if path is None:
            continue
        try:
            parsed[key], txt = esbn.parse_workbook(path, key)
            texts.append(txt)
        except Exception as e:  # noqa: BLE001
            texts.append(f"=== {key}: could not read ({e})")
            print(f"     [!] {key} workbook could not be read: {e}")
    (REPORTS_DIR / "esbn_workbook_structure.txt").write_text("\n\n".join(texts) or "no workbooks", encoding="utf-8")
    cork, forecast, info = esbn.cork_stations(parsed, pl)
    print(f"     Station names matched across workbooks: {len(info.get('name_matches', []))}")
    if info.get("not_demand"):
        print(f"     Not on ESB's demand list (generation/dedicated, excluded from planning): {len(info['not_demand'])}")
    print(f"     Cork stations found: {info.get('n_cork', 0)} ({info.get('method')}); with location "
          f"{info.get('with_location', 0)}, with spare capacity {info.get('with_headroom', 0)}")

    if info.get("name_matches"):
        import pandas as pd
        pd.DataFrame(info["name_matches"], columns=["heatmap_name", "forecast_name"]).to_csv(
            REPORTS_DIR / "name_matches.csv", index=False)
    qc = quality.run_checks(cons, eds, ed_meta, pl, info, cork, forecast, args.demo)
    print(f"     {qc['summary']}  (details: reports/qc_log.txt)")
    for s, c, dd in qc["results"]:
        if s != "PASS":
            print(f"       [{s}] {c}: {dd}")
    if not qc["passed"]:
        sys.exit("\n[!] Quality checks failed, so no report was produced. Paste reports/qc_log.txt to Claude.")

    print("4/7  Projecting demand to 2040 (3 scenarios + Monte Carlo) ...")
    base = scenarios.baseline(cons)
    scen = scenarios.run_scenarios(eds, base)
    mc = scenarios.monte_carlo(eds, base)
    sens = scenarios.sensitivity(eds, base)

    print("5/7  Planning substations and budget ...")
    cent = planning.ed_centroids(pl) if pl is not None else None
    plan = planning.plan(scen, mc, cork, cent)
    view = planning.esbn_view(forecast, cork)

    print("6/7  Charts ...")
    figs = {"history": charts.history(cons), "paths": charts.paths(scen, base, plan), "drivers": charts.drivers(scen),
            "map": charts.cork_map(scen, eds, pl, plan), "stations": charts.stations(plan),
            "budget": charts.budget(plan), "tornado": charts.tornado(sens), "esbn": charts.esbn_chart(view)}

    figs["webmap"] = webmap.build(cork, forecast, plan, scen, bpath, args.demo)

    print("7/7  Report ...")
    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "index.html").write_text(report.build(cons, base, eds, scen, plan, sens, view, qc, figs, info,
                                                      args.demo), encoding="utf-8")
    for sname, r in scen.items():
        r["yearly"].to_csv(REPORTS_DIR / f"cork_{sname}_yearly.csv", float_format="%.1f")
    if plan.get("stations"):
        plan["stations"][("central", False)].to_csv(REPORTS_DIR / "stations_central_2040.csv", float_format="%.2f")
    hl = report.headline(base, scen, plan, view)
    (REPORTS_DIR / "results.json").write_text(json.dumps({"demo": args.demo, "headline": hl, "esbn": info,
                                                          "summary": plan["summary"]}, indent=2, default=str))

    cv = (f"**Cork 2040 Grid Capacity Plan (Python, Monte Carlo):** bottom-up model of Co. Cork's electricity peak to "
          f"2040 from CSO consumption and Census 2022 data for {len(eds)} electoral divisions (heat pumps, EVs, housing, "
          f"business): central peak +{hl['growth_pct']:.0f}% to {hl['peak_2040']['central']:,.0f} MW; "
          + (f"mapped new load onto {hl['stations_total']} ESB Networks substations ({hl['stations_short']} run short); "
             if hl["stations_short"] is not None else "")
          + f"sized ~{hl['new_p50']:.0f} new stations and €{hl['cost'][10]:,.0f}–{hl['cost'][90]:,.0f}m station "
          f"investment, and showed flexibility (smart EV charging, demand response) saves ~€{max(hl['saving'], 0):,.0f}m.")
    (REPORTS_DIR / "summary.md").write_text(("> DEMO DATA - do not publish.\n\n" if args.demo else "") + cv + "\n")

    s = plan["summary"]
    print("\n================ RESULTS ================" + ("  (DEMO DATA - NOT REAL)" if args.demo else ""))
    print(f"Cork today ({base['year']}): {base['total_gwh']:,.0f} GWh (homes {base['res_gwh']:,.0f}, business "
          f"{base['nonres_gwh']:,.0f}) -> peak ≈ {base['peak_mw']:,.0f} MW")
    print(f"Census: {len(eds)} EDs, {eds['population'].sum():,.0f} people, {eds['households'].sum():,.0f} homes, "
          f"{100 * eds['hh_electric_heat'].sum() / eds['households'].sum():.0f}% electric heat, "
          f"{eds['cars'].sum():,.0f} cars")
    for sname, r in scen.items():
        y = r["yearly"].loc[TARGET_YEAR]
        print(f"{TARGET_YEAR} {SCENARIO_NAMES[sname]:32s} peak {y['peak_mw']:,.0f} MW  (homes {y['homes_mw']:+.0f}, "
              f"business {y['business_mw']:+.0f}, heat pumps {y['heat_pumps_mw']:+.0f}, EVs {y['evs_mw']:+.0f}, "
              f"large {y['large_loads_mw']:+.0f})")
    print(f"Central with flexibility: {hl['peak_2040_flex']:,.0f} MW")
    print(f"Monte Carlo extra peak 2040: {s['extra_mw'][10]:,.0f} / {s['extra_mw'][50]:,.0f} / {s['extra_mw'][90]:,.0f} MW")
    print(f"Planning method: {plan['method']}; stations considered: {plan['n_stations']}"
          + (f"; short by 2040 (central): {hl['stations_short']}" if hl["stations_short"] is not None else ""))
    print(f"New stations (10/50/90%): {s['stations_new'][10]:.0f} / {s['stations_new'][50]:.0f} / "
          f"{s['stations_new'][90]:.0f}   (110 kV {s['n110'][50]:.0f}, 38 kV {s['n38'][50]:.0f}, upgrades "
          f"{s['uprates'][50]:.0f})")
    print(f"Station budget €m (10/50/90%): {s['cost_m'][10]:,.0f} / {s['cost_m'][50]:,.0f} / {s['cost_m'][90]:,.0f};"
          f" with flexibility median {s['cost_m_flex'][50]:,.0f} (saves ~{max(s['saving_m'], 0):,.0f})")
    if view:
        t = view["table"]
        print("ESB Networks 2040 stations short: " + ", ".join(
            f"{r['scenario']} {int(r['negative'])}/{int(r['stations'])}" for _, r in t[t['year'] == 2040].iterrows()))
    print(f"Biggest uncertainty: {sens['input'].iloc[-1]}")
    print(f"\nReport: {DOCS_DIR / 'index.html'}\nInteractive heatmap: {figs['webmap']}\nWorkbook layout: {REPORTS_DIR / 'esbn_workbook_structure.txt'}"
          f"\nCV line: {REPORTS_DIR / 'summary.md'}")


if __name__ == "__main__":
    main()
