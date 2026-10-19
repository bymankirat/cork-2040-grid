"""Build a ready-to-open Power BI project (PBIP) for the grid readiness dashboard.

    python powerbi/build_pbip.py

Writes powerbi/pbip/:
  Grid_Readiness.pbip                 open this in Power BI Desktop
  Grid_Readiness.SemanticModel/       tables, relationships, measures (model.bim)
  Grid_Readiness.Report/              3 pages of visuals (PBIR format) + theme

The tables load straight from the CSVs in this public repo (raw.githubusercontent.com),
so nothing has to be copied by hand. Power BI asks once how to sign in: choose Anonymous.
"""
import json
import re
import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "pbip"
NAME = "Grid_Readiness"
DATA_URL = "https://raw.githubusercontent.com/bymankirat/cork-2040-grid/main/powerbi/data/"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
VC = SCHEMA + "visualContainer/2.0.0/schema.json"

GREEN, AMBER, RED, GREY = "#1B8A5A", "#E0A100", "#C2362F", "#9AA5B1"
NAVY = "#0E5A8A"

# ------------------------------------------------------------------ semantic model
# column: (name, dataType, summarizeBy, extra)
TABLES = {
    "dim_county": [("County", "string", "none", {}), ("CountyOrder", "int64", "none", {"isHidden": True}),
                   ("Stations", "int64", "none", {"isHidden": True})],
    "dim_station": [("StationID", "string", "none", {}), ("Station", "string", "none", {}),
                    ("County", "string", "none", {}), ("VoltageKV", "int64", "none", {}),
                    ("Latitude", "double", "none", {"dataCategory": "Latitude"}),
                    ("Longitude", "double", "none", {"dataCategory": "Longitude"}),
                    ("HeadroomNowMW", "double", "sum", {"formatString": "0.0"}),
                    ("Extra2040MW", "double", "sum", {"formatString": "0.0"}),
                    ("Shortfall2040MW", "double", "sum", {"formatString": "0.0"}),
                    ("Action2040", "string", "none", {}), ("Status2040", "string", "none", {}),
                    ("YearFull", "int64", "none", {"formatString": "0"})],
    "dim_year": [("Year", "int64", "none", {"formatString": "0"}), ("Decade", "string", "none", {})],
    "fact_demand": [("County", "string", "none", {}), ("Scenario", "string", "none", {}),
                    ("Year", "int64", "none", {"formatString": "0"}), ("Driver", "string", "none", {}),
                    ("MW", "double", "sum", {"formatString": "#,0"})],
    "fact_esbn_headroom": [("StationID", "string", "none", {}), ("Scenario", "string", "none", {}),
                           ("Year", "int64", "none", {"formatString": "0"}),
                           ("HeadroomMW", "double", "sum", {"formatString": "0.0"}),
                           ("IsFull", "int64", "none", {})],
    "fact_cost": [("County", "string", "none", {}), ("Percentile", "string", "none", {}),
                  ("CostEURm", "double", "sum", {"formatString": "#,0"}),
                  ("CostWithFlexEURm", "double", "sum", {"formatString": "#,0"})],
}
M_TYPE = {"string": "type text", "int64": "Int64.Type", "double": "type number"}

FORMATS = {"%": "0.0%", "MW": "#,0", "EURm": "#,0"}
FORMAT_OVERRIDE = {"Avg Years To Full": "0.0", "ESBN First Year Full": "0", "ESBN Headroom MW": "0.0"}

EXTRA_MEASURES = {
    # light cell colours for the headroom matrix (field-value conditional formatting)
    "Headroom Colour": 'VAR h = [ESBN Headroom MW]\nRETURN\n    IF ( ISBLANK ( h ), BLANK (),\n'
                       '        IF ( h <= 0, "#F4C7C3", IF ( h < 5, "#FCE8B2", "#CDEBD8" ) ) )',
}


def lineage():
    return str(uuid.uuid4())


def read_measures():
    """Parse measures.dax (Name = expression blocks, // comments)."""
    out, cur = [], None
    for line in (ROOT / "measures.dax").read_text().splitlines():
        if line.startswith("//"):
            continue
        m = re.match(r"^([A-Za-z0-9 %/]+?) =\s*(.*)$", line)
        if m and not line.startswith(" "):
            cur = [m.group(1), [m.group(2)] if m.group(2) else []]
            out.append(cur)
        elif cur is not None and line.strip():
            cur[1].append(line)
    measures = []
    for name, body in out + [[k, v.splitlines()] for k, v in EXTRA_MEASURES.items()]:
        fmt = FORMAT_OVERRIDE.get(name)
        if fmt is None:
            fmt = next((f for key, f in FORMATS.items() if key in name), None)
        if fmt is None and name in ("Stations", "Stations Short 2040", "Stations Ready 2040", "New Stations Needed",
                                    "ESBN Stations Full"):
            fmt = "#,0"
        m = {"name": name, "expression": body if len(body) > 1 else body[0], "lineageTag": lineage()}
        if fmt:
            m["formatString"] = fmt
        measures.append(m)
    return measures


def table_json(name, cols):
    columns = []
    for c, dt, summ, extra in cols:
        col = {"name": c, "dataType": dt, "sourceColumn": c, "summarizeBy": summ, "lineageTag": lineage(),
               "annotations": [{"name": "SummarizationSetBy", "value": "User"}]}
        col.update(extra)
        columns.append(col)
    types = ", ".join(f'{{"{c}", {M_TYPE[dt]}}}' for c, dt, _, _ in cols)
    expr = [
        "let",
        f'    Source = Csv.Document(Web.Contents("{DATA_URL}", [RelativePath = "{name}.csv"]),',
        f'        [Delimiter = ",", Columns = {len(cols)}, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        '    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),',
        f'    Typed = Table.TransformColumnTypes(Promoted, {{{types}}}, "en-US")',
        "in",
        "    Typed",
    ]
    return {"name": name, "lineageTag": lineage(), "columns": columns,
            "partitions": [{"name": name, "mode": "import", "source": {"type": "m", "expression": expr}}],
            "annotations": [{"name": "PBI_ResultType", "value": "Table"}]}


def model_bim():
    tables = [table_json(n, c) for n, c in TABLES.items()]
    tables.insert(0, {
        "name": "_Measures", "lineageTag": lineage(),
        "columns": [{"name": "Value", "dataType": "int64", "sourceColumn": "Value", "isHidden": True,
                     "summarizeBy": "none", "lineageTag": lineage()}],
        "partitions": [{"name": "_Measures", "mode": "import",
                        "source": {"type": "m", "expression": ["let", "    Source = #table(type table [Value = Int64.Type], {})",
                                                               "in", "    Source"]}}],
        "measures": read_measures(),
        "annotations": [{"name": "PBI_ResultType", "value": "Table"}]})
    rel = lambda ft, fc, tt, tc: {"name": lineage(), "fromTable": ft, "fromColumn": fc, "toTable": tt, "toColumn": tc}
    relationships = [
        rel("dim_station", "County", "dim_county", "County"),
        rel("fact_demand", "County", "dim_county", "County"),
        rel("fact_cost", "County", "dim_county", "County"),
        rel("fact_esbn_headroom", "StationID", "dim_station", "StationID"),
        rel("fact_esbn_headroom", "Year", "dim_year", "Year"),
        rel("fact_demand", "Year", "dim_year", "Year"),
    ]
    order = ["_Measures"] + list(TABLES)
    return {
        "compatibilityLevel": 1567,
        "model": {
            "culture": "en-US",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True},
            "tables": tables,
            "relationships": relationships,
            "annotations": [{"name": "PBI_QueryOrder", "value": json.dumps(order)},
                            {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"}],
        },
    }


# ------------------------------------------------------------------ report helpers
def lit(v):
    if isinstance(v, bool):
        s = "true" if v else "false"
    elif isinstance(v, (int, float)):
        s = f"{v}D"
    else:
        s = "'" + str(v).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": s}}}


def col(entity, prop):
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def mea(entity, prop):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def avg(entity, prop):
    return {"Aggregation": {"Expression": col(entity, prop), "Function": 1}}


def ref(field):
    if "Aggregation" in field:
        c = field["Aggregation"]["Expression"]["Column"]
        return f'Avg({c["Expression"]["SourceRef"]["Entity"]}.{c["Property"]})'
    k = "Column" if "Column" in field else "Measure"
    return f'{field[k]["Expression"]["SourceRef"]["Entity"]}.{field[k]["Property"]}'


def proj(field, display=None):
    p = {"field": field, "queryRef": ref(field), "nativeQueryRef": ref(field).split(".", 1)[-1].rstrip(")")}
    if display:
        p["displayName"] = display
    return p


def in_filter(entity, prop, values):
    lits = [[{"Literal": {"Value": f"{v}L" if isinstance(v, int) else f"'{v}'"}}] for v in values]
    return {"Version": 2, "From": [{"Name": "t", "Entity": entity, "Type": 0}],
            "Where": [{"Condition": {"In": {"Expressions": [
                {"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": prop}}], "Values": lits}}}]}


def visual_filter(entity, prop, values, name):
    return {"filters": [{"name": name, "field": col(entity, prop), "type": "Categorical",
                         "filter": in_filter(entity, prop, values), "howCreated": "User"}]}


def container_title(text, size=12):
    return {"title": [{"properties": {"show": lit(True), "text": lit(text), "fontSize": lit(size)}}]}


def status_colours(entity, prop, mapping):
    return [{"properties": {"fill": {"solid": {"color": lit(c)}}},
             "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": col(entity, prop),
                                                               "Right": {"Literal": {"Value": f"'{v}'"}}}}}]}}
            for v, c in mapping.items()]


STATUS = {"Green": GREEN, "Amber": AMBER, "Red": RED}


class Page:
    def __init__(self, name, display):
        self.name, self.display, self.visuals, self.interactions = name, display, [], []
        self.z = 0

    def add(self, name, x, y, w, h, visual, filters=None):
        self.z += 1000
        v = {"$schema": VC, "name": name,
             "position": {"x": x, "y": y, "z": self.z, "width": w, "height": h, "tabOrder": self.z},
             "visual": visual}
        if filters:
            v["filterConfig"] = filters
        self.visuals.append(v)
        return name

    # ---- visual builders
    def textbox(self, name, x, y, w, h, text, size=20, colour="#1C2433", sub=None):
        paras = [{"textRuns": [{"value": text, "textStyle": {"fontWeight": "bold", "fontSize": f"{size}pt",
                                                              "color": colour}}]}]
        if sub:
            paras.append({"textRuns": [{"value": sub, "textStyle": {"fontSize": "10pt", "color": "#5D6877"}}]})
        return self.add(name, x, y, w, h, {"visualType": "textbox",
                                           "objects": {"general": [{"properties": {"paragraphs": paras}}]},
                                           "visualContainerObjects": {
                                               "background": [{"properties": {"show": lit(False)}}]}})

    def slicer(self, name, x, y, w, h, entity, prop, title, select=None, single=True, tiles=True):
        general = {"orientation": lit(1 if tiles else 0)}
        if select:
            general["filter"] = {"filter": in_filter(entity, prop, select)}
        objects = {"data": [{"properties": {"mode": lit("Basic")}}],
                   "general": [{"properties": general}],
                   "selection": [{"properties": {"singleSelect": lit(single), "strictSingleSelect": lit(single)}}],
                   "header": [{"properties": {"show": lit(True), "text": lit(title), "fontSize": lit(10)}}],
                   "items": [{"properties": {"textSize": lit(11)}}]}
        return self.add(name, x, y, w, h, {
            "visualType": "slicer",
            "query": {"queryState": {"Values": {"projections": [proj(col(entity, prop)) | {"active": True}]}}},
            "objects": objects, "drillFilterOtherVisuals": True})

    def card(self, name, x, y, w, h, measure, label, filters=None, size=24):
        return self.add(name, x, y, w, h, {
            "visualType": "card",
            "query": {"queryState": {"Values": {"projections": [proj(mea("_Measures", measure), label)]}}},
            "objects": {"labels": [{"properties": {"fontSize": lit(size), "labelDisplayUnits": lit(1),
                                                   "color": {"solid": {"color": lit("#1C2433")}}}}],
                        "categoryLabels": [{"properties": {"show": lit(True), "fontSize": lit(10)}}]},
            "visualContainerObjects": {"border": [{"properties": {"show": lit(True),
                                                                  "color": {"solid": {"color": lit("#E3E7EC")}},
                                                                  "radius": lit(8)}}]},
            "drillFilterOtherVisuals": True}, filters)

    def chart(self, name, x, y, w, h, vtype, roles, title, sort=None, objects=None, filters=None):
        q = {"queryState": {r: {"projections": [proj(f, d) for f, d in fields]} for r, fields in roles.items()}}
        if sort:
            q["sortDefinition"] = {"sort": [{"field": sort[0], "direction": sort[1]}]}
        vis = {"visualType": vtype, "query": q, "visualContainerObjects": container_title(title),
               "drillFilterOtherVisuals": True}
        if objects:
            vis["objects"] = objects
        return self.add(name, x, y, w, h, vis, filters)

    def no_filter(self, source, target):
        self.interactions.append({"source": source, "target": target, "type": "NoFilter"})

    def page_json(self):
        p = {"$schema": SCHEMA + "page/2.0.0/schema.json", "name": self.name, "displayName": self.display,
             "displayOption": "FitToPage", "height": 720, "width": 1280,
             "objects": {"background": [{"properties": {"color": {"solid": {"color": lit("#F6F8FA")}},
                                                        "transparency": lit(0)}}]}}
        if self.interactions:
            p["visualInteractions"] = self.interactions
        return p


def build_pages():
    S, Y, D, H, C = "dim_station", "dim_year", "fact_demand", "fact_esbn_headroom", "dim_county"
    pages = []

    # ---------------------------------------------------------------- 1 Overview
    p = Page("overview", "Overview")
    p.textbox("title", 20, 12, 700, 60, "Grid readiness to 2040",
              sub="Cork and Dublin demand substations · winter peak · independent model on public CSO, Census 2022 "
                  "and ESB Networks data")
    county = p.slicer("countySlicer", 760, 14, 230, 62, C, "County", "County", select=["Dublin"])
    scen = p.slicer("scenarioSlicer", 1000, 14, 260, 62, D, "Scenario", "Model scenario", select=["Central"])
    cards = [("Peak 2025 MW", "Winter peak 2025 (MW)"), ("Peak 2040 MW", "Winter peak 2040 (MW)"),
             ("Peak Growth %", "Growth to 2040"), ("Stations Short 2040", "Stations short by 2040"),
             ("New Stations Needed", "Need a new station"), ("Cost Range", "Station investment (P10–P90)")]
    w = (1240 - 5 * 12) / 6
    for i, (m, label) in enumerate(cards):
        p.card(f"card{i + 1}", 20 + i * (w + 12), 92, w, 100, m, label, size=20 if m == "Cost Range" else 26)
    line = p.chart("demandLine", 20, 210, 610, 490, "lineChart",
                   {"Category": [(col(Y, "Year"), "Year")], "Y": [(mea("_Measures", "Peak MW"), "Peak MW")],
                    "Series": [(col(D, "Scenario"), "Scenario")]},
                   "Winter peak demand by model scenario (MW)", sort=(col(Y, "Year"), "Ascending"))
    p.no_filter(scen, line)
    p.chart("driverBar", 645, 210, 330, 490, "clusteredBarChart",
            {"Category": [(col(D, "Driver"), "Driver")], "Y": [(mea("_Measures", "Extra Demand MW"), "Extra MW")]},
            "What adds demand by 2040 (MW)", sort=(mea("_Measures", "Extra Demand MW"), "Descending"),
            filters=visual_filter(Y, "Year", [2040], "year2040"),
            objects={"dataPoint": [{"properties": {"fill": {"solid": {"color": lit(NAVY)}}}}],
                     "labels": [{"properties": {"show": lit(True), "labelDisplayUnits": lit(1)}}]})
    p.chart("statusDonut", 990, 210, 270, 490, "donutChart",
            {"Category": [(col(S, "Status2040"), "Status")], "Y": [(mea("_Measures", "Stations"), "Stations")]},
            "Station status in 2040 (model)",
            objects={"dataPoint": status_colours(S, "Status2040", STATUS),
                     "legend": [{"properties": {"show": lit(True), "position": lit("Bottom")}}],
                     "labels": [{"properties": {"labelStyle": lit("Data value")}}]})
    pages.append(p)

    # ---------------------------------------------------------------- 2 Readiness
    p = Page("readiness", "Readiness")
    p.textbox("title", 20, 12, 700, 60, "Readiness: ESB Networks' own forecast",
              sub="Spare capacity at each station under ESB Networks' four scenarios, against my model's 2040 result")
    p.slicer("countySlicer", 760, 14, 230, 62, C, "County", "County", select=["Dublin"])
    esbn = p.slicer("esbnSlicer", 1000, 14, 260, 62, H, "Scenario", "ESB Networks scenario", select=["Base"])
    p.card("cardModel", 20, 92, 300, 100, "Stations Short 2040", "My model: stations short by 2040")
    p.card("cardEsbn", 335, 92, 300, 100, "ESBN Stations Full", "ESB Networks: stations full by 2040",
           filters=visual_filter(Y, "Year", [2040], "year2040"))
    p.card("cardTotal", 650, 92, 300, 100, "Stations", "Demand stations")
    p.card("cardFirst", 965, 92, 295, 100, "ESBN First Year Full", "First year a station is full")
    full = p.chart("fullLine", 20, 210, 560, 490, "lineChart",
                   {"Category": [(col(Y, "Year"), "Year")],
                    "Y": [(mea("_Measures", "ESBN Stations Full"), "Stations full")],
                    "Series": [(col(H, "Scenario"), "Scenario")]},
                   "Stations with no spare capacity, all four ESB Networks scenarios",
                   sort=(col(Y, "Year"), "Ascending"))
    p.no_filter(esbn, full)
    p.chart("headroomMatrix", 595, 210, 665, 490, "pivotTable",
            {"Rows": [(col(S, "Station"), "Station")], "Columns": [(col(Y, "Year"), "Year")],
             "Values": [(mea("_Measures", "ESBN Headroom MW"), "Spare MW")]},
            "Spare capacity by station (MW): red = full, amber = under 5 MW",
            filters=visual_filter(Y, "Year", [2025, 2030, 2035, 2040, 2045, 2050], "yearsShown"),
            objects={"values": [{"properties": {"backColor": {"solid": {"color": {"expr": mea("_Measures",
                                                                                            "Headroom Colour")}}}},
                                 "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                                              "metadata": "_Measures.ESBN Headroom MW"}}]})
    pages.append(p)

    # ---------------------------------------------------------------- 3 Scorecard
    p = Page("scorecard", "Scorecard")
    p.textbox("title", 20, 12, 700, 60, "Site scorecard",
              sub="Which stations run short, by how much, from which year, and what they need")
    p.slicer("countySlicer", 760, 14, 230, 62, C, "County", "County", select=["Dublin"])
    p.slicer("actionSlicer", 1000, 14, 260, 62, S, "Action2040", "Action needed", single=False)
    p.chart("siteMap", 20, 92, 520, 608, "scatterChart",
            {"Category": [(col(S, "Station"), "Station")], "Series": [(col(S, "Status2040"), "Status")],
             "X": [(avg(S, "Longitude"), "Longitude")], "Y": [(avg(S, "Latitude"), "Latitude")],
             "Size": [(mea("_Measures", "Shortfall 2040 MW"), "Shortfall MW")]},
            "Where the short stations are (bubble = 2040 shortfall)",
            objects={"dataPoint": status_colours(S, "Status2040", STATUS),
                     "legend": [{"properties": {"show": lit(True), "position": lit("Top")}}]})
    cols = [("Station", "Station"), ("VoltageKV", "kV"), ("HeadroomNowMW", "Spare now (MW)"),
            ("Extra2040MW", "Extra by 2040 (MW)"), ("Shortfall2040MW", "Shortfall (MW)"),
            ("Action2040", "Action"), ("YearFull", "Full from")]
    p.chart("siteTable", 555, 92, 705, 608, "tableEx",
            {"Values": [(col(S, c), d) for c, d in cols]}, "Station scorecard (sorted by shortfall)",
            sort=(col(S, "Shortfall2040MW"), "Descending"),
            objects={"values": [{"properties": {"backColor": {"solid": {"color": {"expr": mea("_Measures",
                                                                                            "Status Colour")}}},
                                                "fontColor": {"solid": {"color": lit("#FFFFFF")}}},
                                 "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                                              "metadata": "dim_station.Action2040"}}]})
    pages.append(p)
    return pages


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def main(base_theme):
    if OUT.exists():
        shutil.rmtree(OUT)
    sm, rp = OUT / f"{NAME}.SemanticModel", OUT / f"{NAME}.Report"
    write_json(OUT / f"{NAME}.pbip", {"version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
                                      "settings": {"enableAutoRecovery": True}})
    write_json(sm / "definition.pbism", {"version": "4.0", "settings": {}})
    write_json(sm / "model.bim", model_bim())
    write_json(rp / "definition.pbir", {"version": "4.0",
                                        "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}})
    theme = "grid_readiness_theme.json"
    (rp / "StaticResources/SharedResources/BaseThemes").mkdir(parents=True)
    shutil.copy(base_theme, rp / "StaticResources/SharedResources/BaseThemes/CY24SU10.json")
    (rp / "StaticResources/RegisteredResources").mkdir(parents=True)
    shutil.copy(ROOT / "theme" / theme, rp / "StaticResources/RegisteredResources" / theme)
    d = rp / "definition"
    write_json(d / "version.json", {"$schema": SCHEMA + "versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    write_json(d / "report.json", {
        "$schema": SCHEMA + "report/1.3.0/schema.json",
        "themeCollection": {"baseTheme": {"name": "CY24SU10", "reportVersionAtImport": "5.61", "type": "SharedResources"},
                            "customTheme": {"name": theme, "reportVersionAtImport": "5.61",
                                            "type": "RegisteredResources"}},
        "layoutOptimization": "None",
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": theme, "path": theme, "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True}})
    pages = build_pages()
    write_json(d / "pages/pages.json", {"$schema": SCHEMA + "pagesMetadata/1.0.0/schema.json",
                                        "pageOrder": [p.name for p in pages], "activePageName": pages[0].name})
    for p in pages:
        write_json(d / "pages" / p.name / "page.json", p.page_json())
        for v in p.visuals:
            write_json(d / "pages" / p.name / "visuals" / v["name"] / "visual.json", v)
    print(f"wrote {OUT} ({sum(len(p.visuals) for p in pages)} visuals on {len(pages)} pages)")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT / "theme" / "CY24SU10.json")
