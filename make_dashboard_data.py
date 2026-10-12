"""Turn the pipeline's outputs into two tidy tables for a Tableau / Power BI dashboard.

    python run_pipeline.py                          # first, if reports/ is empty
    python make_dashboard_data.py                   # Cork: dashboard/cork_substations_2040.csv, cork_peak_scenarios.csv
    python make_dashboard_data.py --county dublin   # Dublin: dashboard/dublin_*.csv (after run_pipeline.py --county dublin)
"""

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
_ap = argparse.ArgumentParser()
_ap.add_argument("--county", default="cork", choices=["cork", "dublin"])
COUNTY = _ap.parse_args().county
REPORTS = ROOT / "reports" if COUNTY == "cork" else ROOT / "reports" / COUNTY
OUT = ROOT / "dashboard"
VERDICT = {"none": "Enough spare capacity", "upgrade": "Upgrade needed", "new station": "New station(s) needed"}
SCENARIOS = {"low": "Slow electrification", "central": "Central", "high": "Fast electrification"}
DRIVERS = {"homes_mw": "New homes & population", "business_mw": "Business growth", "heat_pumps_mw": "Heat pumps",
           "evs_mw": "Electric cars", "large_loads_mw": "New large loads"}


def substations() -> pd.DataFrame:
    st = pd.read_csv(REPORTS / "stations_central_2040.csv")
    return pd.DataFrame({
        "Station": st["station"].str.title(),
        "Voltage": st["kv"].astype(int).astype(str) + " kV",
        "Latitude": st["lat"], "Longitude": st["lon"],
        "Spare capacity today (MW)": st["headroom_mw"].round(2),
        "Extra load by 2040 (MW)": st["extra_mw"].round(2),
        "Shortfall by 2040 (MW)": st["deficit_mw"].round(2),
        "Verdict": st["action"].map(VERDICT).fillna(VERDICT["none"]),
        "New stations": st["n_new"], "Upgrades": st["n_uprate"],
    })


def scenarios() -> pd.DataFrame:
    rows = []
    for key, name in SCENARIOS.items():
        y = pd.read_csv(REPORTS / f"{COUNTY}_{key}_yearly.csv")
        for col, driver in DRIVERS.items():
            rows.append(pd.DataFrame({
                "Year": y["year"].astype(int), "Scenario": name, "Driver": driver,
                "Extra peak (MW)": y[col].round(1), "Total peak (MW)": y["peak_mw"].round(1),
                "Heat pumps (count)": y["heat_pumps"].round(), "Electric cars (count)": y["evs"].round(),
            }))
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    st, sc = substations(), scenarios()
    # quick checks before anyone builds a dashboard on it
    assert st["Station"].is_unique, "duplicate stations"
    assert st[["Latitude", "Longitude"]].notna().all().all(), "stations without a location"
    assert (st["Shortfall by 2040 (MW)"] >= 0).all(), "negative shortfall"
    st.to_csv(OUT / f"{COUNTY}_substations_2040.csv", index=False)
    sc.to_csv(OUT / f"{COUNTY}_peak_scenarios.csv", index=False)
    short = (st["Verdict"] != VERDICT["none"]).sum()
    print(f"dashboard/{COUNTY}_substations_2040.csv: {len(st)} stations, {short} short by 2040")
    print(f"dashboard/{COUNTY}_peak_scenarios.csv: {len(sc)} rows ({sc['Year'].min()}-{sc['Year'].max()}, 3 scenarios)")
    print("Next: open Tableau Public and follow dashboard/TABLEAU_GUIDE.md")


if __name__ == "__main__":
    main()
