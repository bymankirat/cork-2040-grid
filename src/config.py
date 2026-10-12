"""Settings and every planning assumption, in one place, each with its source.

Change an assumption here and re-run: the whole report updates. Values marked ASSUMPTION are the author's
judgement, chosen to bracket the published targets; they are shown as such in the report.
"""

from pathlib import Path

import os

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"

# ----------------------------------------------------------------------------------------------- regions
# The same model runs for any county set up here. Choose with:  python run_pipeline.py --county dublin
# Each region: its CSO labels, how its electoral divisions are named in Census 2022, growth assumptions and map
# settings. Values marked ASSUMPTION are the author's judgement and are shown as such in the report.
REGIONS = {
    "cork": {
        "name": "Cork", "full": "Co. Cork", "parts": "Cork City and Cork County",
        # MEC03 rows that together make the county (lower case)
        "cso_labels": ["co. cork"], "cso_prefixes": [],
        # Census ED labels end in ", Cork City" / ", Cork County"; first rule that matches wins
        "region_terms": ["cork"],
        "areas": [("Cork City", ["city"]), ("Cork County", [""])],
        "boundary_where": "UPPER(COUNTY_ENGLISH) LIKE '%CORK%'",
        "pop_2022": 584_156, "pop_note": "Cork City 224,004 + Cork County 360,152",
        # Population growth 2022 -> 2040. Revised National Planning Framework (2025): +950,000 people nationally by
        # 2040 (about +18%), half of it targeted at the five cities. ASSUMPTION: Cork City grows faster than the county.
        "pop_growth_2040": {"Cork City": {"low": 0.20, "central": 0.35, "high": 0.50},
                            "Cork County": {"low": 0.08, "central": 0.15, "high": 0.22}},
        # New large loads to 2040, MW at peak (industrial electrification in Cork Harbour, ports). ASSUMPTION;
        # ESB Networks' base scenario assumes no new data centres by 2030.
        "large_loads_mw": {"low": 0, "central": 60, "high": 150},
        "large_label": "New large loads", "large_source": "Assumption (industrial electrification in Cork Harbour, ports)",
        "load_factor": 0.60,
        "city": "Cork City", "closeup": (-8.62, -8.30, 51.83, 51.97),
        "view": (51.42, -10.25, 52.40, -7.80), "keep": (51.3, -10.4, 52.5, -7.5),
        "towns": [["Cork City", 51.8985, -8.4756, 1], ["Mallow", 52.1345, -8.6450, 0], ["Fermoy", 52.1386, -8.2756, 0],
                  ["Midleton", 51.9153, -8.1750, 0], ["Youghal", 51.9536, -7.8506, 0], ["Bandon", 51.7460, -8.7425, 0],
                  ["Clonakilty", 51.6231, -8.8706, 0], ["Skibbereen", 51.5500, -9.2667, 0],
                  ["Bantry", 51.6800, -9.4520, 0], ["Macroom", 51.9046, -8.9568, 0], ["Kinsale", 51.7059, -8.5222, 0],
                  ["Cobh", 51.8503, -8.2967, 0], ["Mitchelstown", 52.2656, -8.2683, 0],
                  ["Kanturk", 52.1719, -8.9050, 0], ["Charleville", 52.3556, -8.6833, 0]],
    },
    "dublin": {
        "name": "Dublin", "full": "County Dublin", "cso_note": " (Co. Dublin plus postal districts Dublin 1–24)",
        "parts": "Dublin City, Fingal, South Dublin and Dún Laoghaire–Rathdown",
        # In MEC03 "Co. Dublin" excludes the city: the county total is Co. Dublin plus postal districts Dublin 1-24
        "cso_labels": ["co. dublin"], "cso_prefixes": ["dublin "],
        "region_terms": ["dublin", "fingal", "laoghaire", "rathdown"],
        "areas": [("Dublin City", ["dublin city"]), ("Fingal", ["fingal"]), ("South Dublin", ["south dublin"]),
                  ("Dún Laoghaire–Rathdown", ["laoghaire", "rathdown"])],
        "boundary_where": ("UPPER(COUNTY_ENGLISH) LIKE '%DUBLIN%' OR UPPER(COUNTY_ENGLISH) LIKE '%FINGAL%' "
                           "OR UPPER(COUNTY_ENGLISH) LIKE '%LAOGHAIRE%'"),
        "pop_2022": 1_458_154,
        "pop_note": "Dublin City 592,713 + Fingal 330,506 + South Dublin 301,075 + Dún Laoghaire–Rathdown 233,860",
        # ASSUMPTION: NPF growth for Dublin City and suburbs; Fingal and South Dublin hold most new housing land.
        "pop_growth_2040": {"Dublin City": {"low": 0.10, "central": 0.18, "high": 0.26},
                            "Fingal": {"low": 0.15, "central": 0.26, "high": 0.36},
                            "South Dublin": {"low": 0.12, "central": 0.22, "high": 0.32},
                            "Dún Laoghaire–Rathdown": {"low": 0.08, "central": 0.15, "high": 0.22}},
        # NEW data centres and other large energy users from 2025, extra MW at peak by 2040 (existing data-centre
        # use is not split out of the CSO county figure). CSO: data centres used 23% of
        # Ireland's metered electricity in 2025, much of it in the Dublin area, where EirGrid has limited new
        # connections and the CRU now asks large users to bring on-site generation. ASSUMPTION. They connect mostly
        # to the transmission grid, so they are counted in Dublin's peak but not assigned to ESB Networks stations.
        "large_loads_mw": {"low": 0, "central": 250, "high": 600},
        "large_label": "Data centres & large users",
        "large_source": ("Assumption. CSO: data centres used 23% of metered electricity in 2025; EirGrid limits new "
                         "Dublin connections"),
        # Data centres run almost flat out all year, so Dublin's load is less peaky than Cork's (ASSUMPTION; EirGrid
        # system level ~0.66).
        "load_factor": 0.66,
        "city": "Dublin City", "closeup": (-6.36, -6.15, 53.30, 53.41),
        "view": (53.18, -6.60, 53.64, -5.98), "keep": (53.1, -6.7, 53.7, -5.9),
        "towns": [["Dublin City", 53.3498, -6.2603, 1], ["Swords", 53.4597, -6.2181, 0],
                  ["Balbriggan", 53.6128, -6.1819, 0], ["Skerries", 53.5828, -6.1083, 0], ["Malahide", 53.4508, -6.1544, 0],
                  ["Howth", 53.3786, -6.0667, 0], ["Blanchardstown", 53.3880, -6.3770, 0],
                  ["Lucan", 53.3574, -6.4485, 0], ["Clondalkin", 53.3204, -6.3946, 0], ["Tallaght", 53.2859, -6.3733, 0],
                  ["Dundrum", 53.2925, -6.2456, 0], ["Dún Laoghaire", 53.2944, -6.1339, 0],
                  ["Dublin Airport", 53.4264, -6.2499, 0]],
    },
}
REGION_KEY = os.environ.get("GRID_REGION", "cork").lower()
if REGION_KEY not in REGIONS:
    raise SystemExit(f"Unknown county '{REGION_KEY}'. Choose from: {', '.join(REGIONS)}")
R = REGIONS[REGION_KEY]
AREAS = tuple(a for a, _ in R["areas"])
NAME = R["name"]

# Cork keeps the original paths (so the published site does not move); other regions get their own folders.
_sub = "" if REGION_KEY == "cork" else REGION_KEY
DEMO_DIR = ROOT / "data" / "demo" / _sub if _sub else ROOT / "data" / "demo"
REPORTS_DIR = ROOT / "reports" / _sub if _sub else ROOT / "reports"
FIG_DIR = REPORTS_DIR / "figures"
DOCS_DIR = ROOT / "docs" / _sub if _sub else ROOT / "docs"
# where the other regions' reports live, relative to this region's report (for the switcher in the top bar)
SITE_ROOT = ROOT / "docs"

# ----------------------------------------------------------------------------------------------- data sources
ESBN = {
    # ESB Networks Distribution Network Development Plan: indicative headroom at every 110 kV and 38 kV substation
    # under four growth scenarios (forecasts yearly to 2030, then every 5 years to 2050)
    "headroom": ("demand-capacity-headroom-report-2025.xlsx",
                 "https://media.esbnetworks.ie/media/docs/default-source/publications/"
                 "demand-capacity-headroom-report-2025.xlsx"),
    # ESB Networks customer heatmap: available demand capacity per station (station capacity as of Q4 2025)
    "heatmap": ("customer-heatmap-download-july-2026.xlsx",
                "https://media.esbnetworks.ie/media/docs/default-source/publications/"
                "customer-heatmap-download-july-2026.xlsx"),
}
ESBN_PAGE = "https://www.esbnetworks.ie/services/tools-maps/distribution-network-development-plan"
HEATMAP_PAGE = "https://www.esbnetworks.ie/services/get-connected/renewable-connection/network-capacity-heatmap"

CSO_API = "https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/{table}/CSV/1.0/en"
CSO_TABLES = {
    "consumption": "MEC03",          # metered electricity consumption by county and sector (GWh), 2015 onwards
    "heating": "SAP2022T6T5ED",      # Census 2022: households by central heating fuel, per electoral division
    "cars": "SAP2022T15T1ED",        # Census 2022: households by number of cars, per electoral division
    "population": "SAP2022T1T1AED",  # Census 2022: population by age and sex, per electoral division
}
BOUNDARY_URL = ("https://services-eu1.arcgis.com/BuS9rtTsYEV5C0xh/ArcGIS/rest/services/"
                "CSO_ELECTORAL_DIVISIONS_2022_Genralised_50m_view/FeatureServer/4/query")

# Optional manual mapping for the ESB Networks workbooks, used only if automatic detection fails.
# After the first run, reports/esbn_workbook_structure.txt shows the layout; fill in names from it, e.g.
# {"headroom": {"sheet": "Base", "header_row": 3, "station": "Station Name", ...}}
ESBN_OVERRIDE: dict = {}

# ----------------------------------------------------------------------------------------------- horizon
BASE_YEAR = 2025
YEARS = list(range(2025, 2041))
TARGET_YEAR = 2040      # ESB strategy: Net Zero by 2040

# ----------------------------------------------------------------------------------------------- scenarios
# Three scenarios bracket the published targets. "low"/"central"/"high" growth in electricity need.
SCENARIOS = ["low", "central", "high"]
SCENARIO_NAMES = {"low": "Slow electrification", "central": "Central (targets broadly met)",
                  "high": "Fast electrification"}

ASSUMPTIONS = {
    # Population growth 2022 -> 2040, per area of the region (see REGIONS above)
    "pop_growth_2040": R["pop_growth_2040"],
    # Share of households heated by a heat pump in 2040. Climate Action Plan: ~680,000 heat pumps by 2030
    # (about a third of homes). ASSUMPTION for 2040.
    "heat_pump_share_2040": {"low": 0.35, "central": 0.55, "high": 0.75},
    # Share of cars that are electric in 2040. Climate Action Plan / PR6: up to ~1 million EVs by 2030.
    "ev_share_2040": {"low": 0.45, "central": 0.70, "high": 0.90},
    # Annual electricity per heat pump home (kWh) and per EV (kWh): typical Irish values (ASSUMPTION, SEAI-range).
    "hp_kwh": 4500, "ev_kwh": 2300,
    # Contribution to the winter evening peak, after diversity (kW per home / per car).
    # Heat pumps: UCC field trial of retrofitted Irish homes found 2.33 kW on a typical winter day and 3.84 kW in
    # extreme cold; part of that replaces existing electric load, so the extra is taken as 1.4-2.6 kW
    # (extreme cold is reported separately as a stress test).
    # EVs: ~1.0 kW per car if charging is unmanaged, ~0.25 kW if smart. ESB Networks' base scenario assumes 85%
    # smart charging by 2040, so the blended central value is ~0.5 kW (ASSUMPTION).
    "hp_peak_kw": {"low": 1.4, "central": 2.0, "high": 2.6},
    "hp_peak_kw_extreme": 3.84,
    "ev_peak_kw": {"low": 0.35, "central": 0.5, "high": 0.9},
    "ev_peak_kw_smart": 0.25,
    # Existing homes already heated by electricity are assumed not to add heat-pump load (ASSUMPTION).
    # Business and industry growth per year (ASSUMPTION; ESB Networks scenarios assume limited large-user growth).
    "nonres_growth_pa": {"low": 0.005, "central": 0.012, "high": 0.020},
    # New large loads to 2040, MW at peak (see REGIONS above; data centres for Dublin)
    "large_loads_mw": R["large_loads_mw"],
    # Efficiency: existing residential use per home falls this much by 2040 (lighting, appliances). ASSUMPTION.
    "res_efficiency_2040": {"low": 0.10, "central": 0.07, "high": 0.04},
    # Annual load factor (average / peak) used to turn yearly energy into a winter peak. National EirGrid data
    # gives ~0.66 at system level; local networks are peakier (ASSUMPTION).
    "load_factor": R["load_factor"],
    "power_factor": 0.95,   # MW -> MVA
    # Flexibility (ESB Networks Base scenario: demand-side response cuts peak by 11.2%).
    "dsr_peak_cut": 0.112,
    "hp_flex_cut": 0.15,    # pre-heating / thermal storage trims heat-pump peak (ASSUMPTION)
}

# ----------------------------------------------------------------------------------------------- network costs
# Station sizes and costs (2026 euro, min / most likely / max for Monte Carlo). Published examples:
#   * ~EUR 6m for a new 38 kV substation at Ballymahon (2018), roughly EUR 8m in today's money;
#   * ~EUR 70m each for the new Bracklone and planned West Portlaoise 110 kV stations (2025).
# Uprate costs are ASSUMPTIONS. Station costs only: circuits, land and transmission upstream are excluded,
# so totals are a floor, not a full programme cost.
NETWORK = {
    "new_38kv": {"mva": (10, 15, 20), "cost_m": (5, 8, 12)},
    "new_110kv": {"mva": (40, 63, 80), "cost_m": (35, 55, 80)},
    "uprate_38kv": {"mva": (5, 10, 15), "cost_m": (1.5, 2.5, 4.0)},
    "uprate_110kv": {"mva": (20, 30, 50), "cost_m": (5, 8, 12)},
}
# How the extra MVA is split between the 110 kV and 38 kV levels when station data are unavailable (ASSUMPTION)
SHARE_110KV = 0.5

MC_RUNS = 5000
RANDOM_STATE = 42
