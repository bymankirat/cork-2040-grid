"""Settings and every planning assumption, in one place, each with its source.

Change an assumption here and re-run: the whole report updates. Values marked ASSUMPTION are the author's
judgement, chosen to bracket the published targets; they are shown as such in the report.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
DEMO_DIR = ROOT / "data" / "demo"
REPORTS_DIR = ROOT / "reports"
FIG_DIR = REPORTS_DIR / "figures"
DOCS_DIR = ROOT / "docs"

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
CORK_AREAS = ("Cork City", "Cork County")

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
    # Population growth 2022 -> 2040. Revised National Planning Framework (2025): +950,000 people nationally by
    # 2040 (about +18%), with half of growth targeted at the five cities. ASSUMPTION: Cork City grows faster than
    # the county; ranges bracket the NPF ambition for Cork City and suburbs.
    "pop_growth_2040": {"Cork City": {"low": 0.20, "central": 0.35, "high": 0.50},
                        "Cork County": {"low": 0.08, "central": 0.15, "high": 0.22}},
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
    # New large loads in Cork to 2040, MW at peak (industrial electrification in Cork Harbour, data, ports).
    # ASSUMPTION; ESB Networks' base scenario assumes no new data centres by 2030.
    "large_loads_mw": {"low": 0, "central": 60, "high": 150},
    # Efficiency: existing residential use per home falls this much by 2040 (lighting, appliances). ASSUMPTION.
    "res_efficiency_2040": {"low": 0.10, "central": 0.07, "high": 0.04},
    # Annual load factor (average / peak) used to turn yearly energy into a winter peak. National EirGrid data
    # gives ~0.66 at system level; local networks are peakier (ASSUMPTION).
    "load_factor": 0.60,
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
