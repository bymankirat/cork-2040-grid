"""Build the Power BI tables (star schema) from the Cork and Dublin grid model outputs.

    python powerbi/build_data.py

Writes CSVs to powerbi/data/:
  dim_station.csv          one row per demand substation (Cork + Dublin), readiness status from the model
  fact_esbn_headroom.csv   ESB Networks' own spare-capacity forecast: station x scenario x year
  fact_demand.csv          county winter peak by driver, scenario and year (model)
  fact_cost.csv            station investment ranges per county (Monte Carlo percentiles)
  dim_year.csv, dim_county.csv
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "powerbi" / "data"
OUT.mkdir(parents=True, exist_ok=True)

COUNTIES = {"Cork": (ROOT / "docs" / "map.html", ROOT / "reports", "cork"),
            "Dublin": (ROOT / "docs" / "dublin" / "map.html", ROOT / "reports" / "dublin", "dublin")}
ACTION = {"none": "No action", "upgrade": "Upgrade", "new station": "New station"}
STATUS = {"none": "Green", "upgrade": "Amber", "new station": "Red"}
DRIVERS = {"homes_mw": "New homes", "business_mw": "Business growth", "heat_pumps_mw": "Heat pumps",
           "evs_mw": "Electric cars", "large_loads_mw": "Data centres & large users"}


def map_data(path):
    s = path.read_text()
    i = s.index("const D=") + len("const D=")
    data, _ = json.JSONDecoder().raw_decode(s[i:])
    return data


def write(name, rows, fields):
    with open(OUT / name, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"{name}: {len(rows)} rows")


def main():
    stations, headroom, demand, cost = [], [], [], []
    years, scenarios = set(), set()
    for county, (mp, rep, prefix) in COUNTIES.items():
        D = map_data(mp)
        for s in D["stations"]:
            if s.get("gen"):          # generation-only stations carry no demand
                continue
            sid = f"{county[:3].upper()}-{s['n'].upper().replace(' ', '_')}"
            stations.append({"StationID": sid, "Station": s["n"].title(), "County": county, "VoltageKV": s["kv"],
                             "Latitude": s["lat"], "Longitude": s["lon"],
                             "HeadroomNowMW": s["now"], "Extra2040MW": s["extra"], "Shortfall2040MW": s["short"],
                             "Action2040": ACTION.get(s["act"], "No data"), "Status2040": STATUS.get(s["act"], "Grey"),
                             "YearFull": s["full"] if s["full"] else ""})
            for sc, ys in (s.get("fc") or {}).items():
                for y, v in ys.items():
                    headroom.append({"StationID": sid, "Scenario": sc, "Year": int(y), "HeadroomMW": v,
                                     "IsFull": 1 if v is not None and v <= 0 else 0})
                    years.add(int(y))
                    scenarios.add(("ESB Networks", sc))
        for sc in ("low", "central", "high"):
            f = rep / f"{prefix}_{sc}_yearly.csv"
            for r in csv.DictReader(open(f)):
                y = int(r["year"])
                years.add(y)
                scenarios.add(("Model", sc.title()))
                base = float(r["peak_mw"]) - float(r["extra_peak_mw"])
                demand.append({"County": county, "Scenario": sc.title(), "Year": y, "Driver": "Existing demand", "MW": round(base, 2)})
                for col, label in DRIVERS.items():
                    demand.append({"County": county, "Scenario": sc.title(), "Year": y, "Driver": label, "MW": round(float(r[col]), 2)})
        res = json.loads((rep / "results.json").read_text())["summary"]
        for p in ("10", "50", "90"):
            cost.append({"County": county, "Percentile": f"P{p}", "CostEURm": round(res["cost_m"][p], 1),
                         "CostWithFlexEURm": round(res["cost_m_flex"][p], 1)})
    write("dim_station.csv", stations, list(stations[0]))
    write("fact_esbn_headroom.csv", headroom, list(headroom[0]))
    write("fact_demand.csv", demand, list(demand[0]))
    write("fact_cost.csv", cost, list(cost[0]))
    write("dim_year.csv", [{"Year": y, "Decade": f"{y // 10 * 10}s"} for y in sorted(years)], ["Year", "Decade"])
    # a numeric column so Power BI recognises the first row as the header
    write("dim_county.csv", [{"County": c, "CountyOrder": i + 1, "Stations": sum(st["County"] == c for st in stations)}
                             for i, c in enumerate(COUNTIES)], ["County", "CountyOrder", "Stations"])


if __name__ == "__main__":
    main()
