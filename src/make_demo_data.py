"""Simulated inputs with the same shapes as the real ones (CSO tables, ED boundaries, two ESB Networks workbooks
with messy multi-row headers), so the pipeline can be tested offline. Outputs are marked DEMO."""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from config import DEMO_DIR, ESBN


def _wgs_to_itm(lat, lon):
    """Rough forward projection, good enough for demo coordinates (inverse is exact in esbn.py)."""
    a, k0 = 6378137.0, 0.99982
    x = 600000 + k0 * a * math.radians(lon + 8.0) * math.cos(math.radians(lat))
    y = 750000 + k0 * a * math.radians(lat - 53.5)
    return x, y


def make(seed: int = 3) -> dict:
    rng = np.random.default_rng(seed)
    DEMO_DIR.mkdir(parents=True, exist_ok=True)

    # ---------------- electoral divisions: Cork City (dense) and Cork County (spread), plus a few elsewhere
    eds = []
    for i in range(90):
        eds.append(("City", 51.90 + rng.normal(0, 0.025), -8.47 + rng.normal(0, 0.04), "Cork City"))
    for i in range(260):
        eds.append(("Cty", rng.uniform(51.55, 52.3), rng.uniform(-9.8, -7.9), "Cork County"))
    for i in range(40):
        eds.append(("Oth", rng.uniform(52.6, 53.4), rng.uniform(-9.0, -6.5), "Kerry"))
    guids = [f"G{i:05d}" for i in range(len(eds))]
    labels = [f"ED {i}, {e[3]}" for i, e in enumerate(eds)]

    def ed_table(table, cats, values, stat="Permanent private households", extra_cols=None):
        rows = []
        for g, lab, vals in zip(guids, labels, values):
            for c, v in zip(cats, vals):
                rows.append({"STATISTIC": table, "Statistic Label": stat, "TLIST(A1)": "2022", "Census Year": "2022",
                             "C0X": c[:3].upper(), "Cat": c, "C04167V04938": g,
                             "CSO Electoral Divisions 2022": lab, "UNIT": "Number", "VALUE": int(v)})
        df = pd.DataFrame(rows)
        df = df.rename(columns={"C0X": "C03750V04499", "Cat": extra_cols or "Category"})
        return df

    hh = np.array([rng.integers(900, 2600) if e[0] == "City" else rng.integers(250, 1400) for e in eds])
    pop = (hh * rng.uniform(2.3, 2.9, len(hh))).astype(int)
    heat_cats = ["No central heating", "Oil", "Natural gas", "Electricity", "Coal (incl. anthracite)",
                 "Peat (incl. turf)", "Liquid petroleum gas (LPG)", "Wood (incl. wood pellets)", "Other",
                 "Not stated", "Total"]
    hv = []
    for e, h in zip(eds, hh):
        city = e[0] == "City"
        p = np.array([0.01, 0.20 if city else 0.62, 0.55 if city else 0.06, 0.12 if city else 0.10, 0.01, 0.01,
                      0.02, 0.03, 0.02, 0.03])
        p = p / p.sum()
        v = rng.multinomial(h, p)
        hv.append(list(v) + [h])
    heat = ed_table("SAP2022T6T5C01", heat_cats, hv, extra_cols="Central Heating")
    car_cats = ["No motor car", "1 motor car", "2 motor cars", "3 motor cars", "4 or more motor cars", "Total"]
    cv = []
    for e, h in zip(eds, hh):
        p = [0.25, 0.45, 0.25, 0.04, 0.01] if e[0] == "City" else [0.07, 0.38, 0.43, 0.09, 0.03]
        v = rng.multinomial(h, p)
        cv.append(list(v) + [h])
    cars = ed_table("SAP2022T15T1C01", car_cats, cv, stat="Number of households with cars",
                    extra_cols="Number of Cars")
    pv = [[p_, p_] for p_ in pop]
    popt = ed_table("SAP2022T1T1AC01", ["Age 0-4", "Total"], [[int(p_ * 0.06), p_] for p_ in pop],
                    stat="Population", extra_cols="Age Group")
    popt.insert(4, "Sex", "Both sexes")
    _ = pv

    # ---------------- consumption (MEC03 layout)
    rows = []
    for y in range(2015, 2026):
        r = 1000 + 8 * (y - 2015) + rng.normal(0, 10)
        nr = 1810 + 18 * (y - 2015) + rng.normal(0, 15)
        for code, lab, v in (("-", "All sectors", r + nr), ("10", "10 Residential", r), ("20", "20 Non-residential", nr)):
            rows.append({"STATISTIC": "MEC03", "Statistic Label": "Metered Electricity Consumption", "TLIST(A1)": y,
                         "Year": y, "C03815V04565": "CKC", "Counties & Dublin Postal Districts": "Co. Cork",
                         "C03816V04566": code, "Sector": lab, "UNIT": "Gigawatt Hours", "VALUE": round(v)})
            rows.append({**rows[-1], "C03815V04565": "KYC", "Counties & Dublin Postal Districts": "Co. Kerry",
                         "VALUE": round(v * 0.4)})
    cons = pd.DataFrame(rows)

    paths = {}
    for key, df in (("consumption", cons), ("heating", heat), ("cars", cars), ("population", popt)):
        p = DEMO_DIR / f"{key}.csv"
        df.to_csv(p, index=False)
        paths[key] = p

    # ---------------- boundaries: small squares around each ED centre
    feats = []
    for g, lab, e in zip(guids, labels, eds):
        d = 0.008 if e[0] == "City" else 0.035
        lat, lon = e[1], e[2]
        ring = [[lon - d, lat - d * 0.6], [lon + d, lat - d * 0.6], [lon + d, lat + d * 0.6],
                [lon - d, lat + d * 0.6], [lon - d, lat - d * 0.6]]
        if e[3].startswith("Cork"):
            feats.append({"type": "Feature", "properties": {"ED_GUID": g, "ED_ENGLISH": lab, "COUNTY_ENGLISH": e[3]},
                          "geometry": {"type": "Polygon", "coordinates": [ring]}})
    bpath = DEMO_DIR / "cork_ed_boundaries.geojson"
    bpath.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))

    # ---------------- ESB Networks-style workbooks
    names = ["Kilbarry", "Marina", "Trabeg", "Blackpool", "Ballincollig", "Carrigaline", "Ringaskiddy", "Glanmire",
             "Douglas", "Bishopstown", "Midleton", "Cobh", "Mallow", "Fermoy", "Bandon", "Clonakilty", "Macroom",
             "Youghal", "Kinsale", "Skibbereen", "Bantry", "Kanturk", "Charleville", "Dunmanway", "Mitchelstown"]
    st = []
    for i, nm in enumerate(names):
        city = i < 10
        lat = 51.90 + rng.normal(0, 0.03) if city else rng.uniform(51.6, 52.25)
        lon = -8.47 + rng.normal(0, 0.05) if city else rng.uniform(-9.6, -8.0)
        kv = 110 if i in (0, 1, 2, 6, 10, 12, 14, 18) else 38
        firm = rng.choice([63, 80, 126]) if kv == 110 else rng.choice([10, 15, 20])
        load = firm * rng.uniform(0.55, 0.97)
        st.append({"name": f"{nm} {kv}kV", "kv": kv, "county": "Cork", "lat": lat, "lon": lon, "firm": firm,
                   "load": load})
    for i in range(35):  # other counties
        st.append({"name": f"Station{i} {38 if i % 3 else 110}kV", "kv": 38 if i % 3 else 110,
                   "county": rng.choice(["Kerry", "Limerick", "Waterford", "Dublin"]),
                   "lat": rng.uniform(52.4, 53.5), "lon": rng.uniform(-9.5, -6.3), "firm": 20, "load": 12})

    def band(x):
        if x < 1:
            return "< 1 MW"
        for lo, hi in ((1, 5), (5, 10), (10, 20)):
            if x < hi:
                return f"{lo} - {hi} MW"
        return "> 20 MW"

    # heatmap: one big sheet, title row then header (as in the July 2026 download)
    heat_rows = []
    for s_ in st:
        nm = s_["name"].upper()
        nm = {"GLANMIRE 38KV": "GLANMIRE TOWN 38KV", "DOUGLAS 38KV": "DOUGLASS 38KV"}.get(nm, nm)
        heat_rows.append({"Station Name": nm, "Station Type": "HV",
                          "Voltage (kV)": s_["kv"], "Latitude": s_["lat"], "Longitude": s_["lon"],
                          "Demand Available Capacity (MVA)": round(max(0, (s_["firm"] - s_["load"]) * 0.9), 1)})
    for nm, ref in (("BOGGERAGH 110KV", st[0]), ("INNISCARRA 38KV", st[3])):  # wind / hydro, beside Cork stations
        la, lo = ref["lat"] + 0.0004, ref["lon"] + 0.0004
        heat_rows.append({"Station Name": nm, "Station Type": "HV", "Voltage (kV)": 110 if "110" in nm else 38,
                          "Latitude": la, "Longitude": lo, "Demand Available MVA": None})
    for i in range(300):  # MV/LV substations with numeric names
        heat_rows.append({"Station Name": f"{100000 + i}", "Station Type": "MV/LV", "Voltage (kV)": 10,
                          "Latitude": 51.9 + rng.normal(0, 0.1), "Longitude": -8.5 + rng.normal(0, 0.2),
                          "Demand Available Capacity (MVA)": 0.2})
    hm = DEMO_DIR / ESBN["heatmap"][0]
    with pd.ExcelWriter(hm, engine="openpyxl") as w:
        pd.DataFrame([["Heatmap data (DEMO)"]]).to_excel(w, sheet_name="Heatmap data", header=False, index=False)
        pd.DataFrame(heat_rows).to_excel(w, sheet_name="Heatmap data", startrow=1, index=False)

    # headroom workbook in ESB Networks' block layout
    years = list(range(2025, 2041)) + [2045, 2050]
    growth = {"Conservative": 0.012, "Best View": 0.017, "Base Case": 0.022, "Aggressive": 0.035}
    hr = DEMO_DIR / ESBN["headroom"][0]
    rows = [[None] * (8 + len(years)) for _ in range(2)]
    rows.append([None] * 8 + ["Years (Year)"] + [None] * (len(years) - 1))
    rows.append(["Trafo Type", "Substation", "Connection Voltage", "Connection Method", "Scenario", "Values",
                 "Transformer Layout Rules", "Connection Method Identifier"]
                + [2025] + [float(y) for y in years[1:]])
    groups = {"110 - 38 kV": [x for x in st if x["kv"] == 110][:4], "110 - MV": [x for x in st if x["kv"] == 110],
              "38 - MV": [x for x in st if x["kv"] == 38]}
    for trafo, members in groups.items():
        first_t = True
        for s_ in members:
            name = s_["name"].rsplit(" ", 1)[0].upper()
            first_s = True
            for scen, g in growth.items():
                for kind in ("Firm Capacity [MVA] ", "Non-Firm Capacity [MVA] "):
                    extra = 0 if kind.startswith("Firm") else s_["firm"] * 0.5
                    vals = []
                    for y in years:
                        v = s_["firm"] + extra - s_["load"] * (1 + g) ** (y - 2025)
                        vals.append(-0.0001 if v <= 0 else round(v, 4))
                    rows.append([trafo if first_t else None, name if first_s else None,
                                 (38 if trafo == "110 - 38 kV" else 10) if first_s else None, 1 if first_s else None,
                                 scen if kind.startswith("Firm") else None, kind, None, None] + vals)
                    first_t = first_s = False
    intro = [[None] * 3 for _ in range(16)] + [[None, "Demand Capacity Headroom", None], [None] * 3,
                                                 [None, "Version:", 1.6], [None, "Date:", "12/12/2025"]]
    conn = [[None] * 4, ["Station Name", "Substation Voltage Level", "Transformer Type", "Consumer type"]]
    conn += [[x["name"].rsplit(" ", 1)[0].upper(), f"{x['kv']} KV", f"{x['kv']} kV - MV", "Mixed"] for x in st]
    search = [[None, "Substation Selector"], [None] * 2, [None, "Select Substation"],
              ["Select Station here →", "-"]] + [[None] * 2] * 10 + [["38/MV Transformer"] + years,
                                                                       ["conservative"] + [4.0] * len(years)]
    with pd.ExcelWriter(hr, engine="openpyxl") as w:
        pd.DataFrame(intro).to_excel(w, sheet_name="1. Introduction - Demand", header=False, index=False)
        pd.DataFrame(rows).to_excel(w, sheet_name="2. Master Demand Capacity List", header=False, index=False)
        pd.DataFrame(search).to_excel(w, sheet_name="3. Demand Capacity Search", header=False, index=False)
        pd.DataFrame(conn).to_excel(w, sheet_name="Connection methods", header=False, index=False)
    return {"cso": paths, "boundaries": bpath, "esbn": {"headroom": hr, "heatmap": hm}}
