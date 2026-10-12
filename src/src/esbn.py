"""Read the ESB Networks workbooks without knowing their exact layout in advance.

For each sheet: find the header row (or two-row header), work out which columns are station names, locations,
voltage, today's capacity or headroom, and which are forecasts by scenario and year. Then keep the region's stations
(by county/area column, or by location inside the region's electoral-division boundaries).

A plain-text description of every sheet is always written to reports/esbn_workbook_structure.txt, so the
mapping can be checked or overridden (config.ESBN_OVERRIDE).
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

from config import ESBN_OVERRIDE, NAME, REPORTS_DIR, R

KEY = re.compile(r"\b(?:station|substation|name|county|region|area|capacity|headroom|available|demand|load|"
                 r"forecast|mva|mw|kv|voltage|firm|scenario|years?|latitude|longitude|lat|lon|long|easting|"
                 r"northing|itm|rating|spare|type|values?)\b", re.I)
YEAR = re.compile(r"(20[2-5]\d)")
SCEN = {"best view": "Best View", "bestview": "Best View", "best-view": "Best View", "base": "Base",
        "conservative": "Conservative", "aggressive": "Aggressive", "accelerated": "Aggressive",
        "low": "Conservative", "high": "Aggressive"}


# --------------------------------------------------------------------------- helpers
def _num(v) -> float:
    """Numbers, also from text such as '5-10 MW', '>20', '< 1', '12.5 MVA'."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return np.nan
    if isinstance(v, (int, float, np.number)):
        return float(v)
    s = str(v).replace(",", "").strip().lower()
    nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", s)]
    if not nums:
        return np.nan
    if len(nums) >= 2 and re.search(r"\d\s*(-|to|–)\s*\d", s):
        return (nums[0] + nums[1]) / 2
    if s.startswith("<"):
        return nums[0] / 2
    return nums[0]


def norm_name(s) -> str:
    s = str(s).lower()
    s = re.sub(r"\b(110|38|20|10)\s*kv\b|\bkv\b|\bsubstation\b|\bstation\b|\bs/s\b|\bss\b", " ", s)
    return re.sub(r"[^a-z]", "", s)


def _scenario(text: str) -> str | None:
    t = str(text).lower()
    for k in sorted(SCEN, key=len, reverse=True):
        if re.search(rf"\b{re.escape(k)}\b", t):
            return SCEN[k]
    return None


def itm_to_wgs84(e: np.ndarray, n: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Irish Transverse Mercator (EPSG:2157) to latitude/longitude, inverse transverse Mercator on GRS80.
    Accurate to well under 10 m, plenty for maps."""
    a, f = 6378137.0, 1 / 298.257222101
    k0, lat0, lon0, fe, fn = 0.99982, math.radians(53.5), math.radians(-8.0), 600000.0, 750000.0
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)

    def m(phi):
        return a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * phi
                    - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * np.sin(2 * phi)
                    + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * np.sin(4 * phi)
                    - (35 * e2 ** 3 / 3072) * np.sin(6 * phi))

    mm = m(lat0) + (np.asarray(n, float) - fn) / k0
    mu = mm / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * np.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32)
            * np.sin(4 * mu) + (151 * e1 ** 3 / 96) * np.sin(6 * mu) + (1097 * e1 ** 4 / 512) * np.sin(8 * mu))
    c1 = ep2 * np.cos(phi1) ** 2
    t1 = np.tan(phi1) ** 2
    n1 = a / np.sqrt(1 - e2 * np.sin(phi1) ** 2)
    r1 = a * (1 - e2) / (1 - e2 * np.sin(phi1) ** 2) ** 1.5
    d = (np.asarray(e, float) - fe) / (n1 * k0)
    lat = phi1 - (n1 * np.tan(phi1) / r1) * (d ** 2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4 / 24
                                             + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2 - 3 * c1 ** 2)
                                             * d ** 6 / 720)
    lon = lon0 + (d - (1 + 2 * t1 + c1) * d ** 3 / 6 + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2 + 24 * t1 ** 2)
                  * d ** 5 / 120) / np.cos(phi1)
    return np.degrees(lat), np.degrees(lon)


# --------------------------------------------------------------------------- structure report
def describe(path: Path, sheets: dict[str, pd.DataFrame], max_rows: int = 12, max_cols: int = 22) -> str:
    out = [f"=== {Path(path).name} ({len(sheets)} sheets) ==="]
    for name, raw in sheets.items():
        out.append(f"\n--- sheet '{name}': {raw.shape[0]} rows x {raw.shape[1]} columns")
        shown = 0
        for i, row in raw.iterrows():
            vals = [("" if pd.isna(v) else str(v))[:24] for v in row.tolist()[:max_cols]]
            if not any(vals):
                continue
            out.append(f"  r{i}: " + " | ".join(vals))
            shown += 1
            if shown >= max_rows:
                break
    return "\n".join(out)


def read_workbook(path: Path) -> dict[str, pd.DataFrame]:
    return pd.read_excel(path, sheet_name=None, header=None, engine="openpyxl")


# --------------------------------------------------------------------------- table detection
def _header(raw: pd.DataFrame, forced: int | None = None) -> tuple[int, list[str]] | None:
    if forced is not None:
        h = forced
    else:
        scores = []
        for i in range(min(60, len(raw))):
            row = raw.iloc[i]
            # header cells are words like "Station Name"; data cells such as "110 KV" start with a number
            sc = sum(1 for v in row if isinstance(v, str) and KEY.search(v) and not re.match(r"\s*\d", v))
            sc += sum(1 for v in row if YEAR.fullmatch(str(v).split(".")[0].strip() or "x"))
            scores.append(sc)
        best = max(scores) if scores else 0
        if best < 2:
            return None
        h = next(i for i, sc in enumerate(scores) if sc >= max(2, 0.8 * best))
    top = raw.iloc[h].tolist()
    # a row above the header is a group header (e.g. scenario names over year columns) only if it has
    # several labels; a single title cell is not spread across every column
    prev = raw.iloc[h - 1] if h > 0 else None
    above = (prev.ffill().tolist() if prev is not None and prev.notna().sum() >= 2 else [None] * len(top))
    names = []
    for u, t in zip(above, top):
        parts = [str(x).strip() for x in (u, t) if x is not None and not pd.isna(x) and str(x).strip()]
        if len(parts) == 2 and parts[0] == parts[1]:
            parts = parts[:1]
        names.append(" | ".join(parts))
    # make names unique
    seen: dict[str, int] = {}
    for j, n in enumerate(names):
        n = n or f"col{j}"
        if n in seen:
            seen[n] += 1
            n = f"{n} #{seen[n]}"
        else:
            seen[n] = 0
        names[j] = n
    return h, names


def _first(cols, pattern, exclude=None):
    rx, ex = re.compile(pattern, re.I), re.compile(exclude, re.I) if exclude else None
    return next((c for c in cols if rx.search(c) and not (ex and ex.search(c))), None)


def _block_list(sheet: str, df: pd.DataFrame) -> dict | None:
    """ESB Networks' Master Demand Capacity List: one block per substation x scenario, label cells filled only on
    the first row of each block, a 'Values' column (Firm / Non-Firm Capacity [MVA]) and one column per year.
    Values are headroom in MVA; ESB Networks shows 'no headroom' as -0.0001 or 0."""
    cols = list(df.columns)
    find = lambda pat: next((c for c in cols if re.search(pat, c, re.I) and not YEAR.search(c)), None)  # noqa: E731
    sub, scen, vals = find(r"^substation$|substation"), find(r"scenario"), find(r"^values?$|values")
    trafo, method = find(r"trafo|transformer type"), find(r"connection method$|^connection method")
    ycols = [c for c in cols if YEAR.search(c)]
    if not (sub and scen and vals and len(ycols) >= 5):
        return None
    lab = [c for c in (trafo, sub, find(r"connection voltage"), method, scen) if c]
    df = df.copy()
    df[lab] = df[lab].ffill()
    df = df[df[vals].astype(str).str.contains("firm", case=False) & ~df[vals].astype(str).str.contains("non", case=False)]
    if method:
        m = pd.to_numeric(df[method], errors="coerce")
        df = df[m == m.groupby(df[sub]).transform("min")]
    df["kv"] = df[trafo].astype(str).str.extract(r"^\s*(\d+)")[0].astype(float) if trafo else np.nan
    df["is_mv"] = df[trafo].astype(str).str.contains("MV", case=False) if trafo else True
    has_mv = df.groupby(sub)["is_mv"].transform("any")
    df = df[df["is_mv"] | ~has_mv]          # customer (MV) transformers where the station has them
    long = df.melt(id_vars=[sub, scen, "kv"], value_vars=ycols, var_name="ycol", value_name="value")
    long["year"] = long["ycol"].map(lambda c: int(YEAR.search(c).group(1)))
    long["value"] = pd.to_numeric(long["value"], errors="coerce").clip(lower=0)
    long = long.dropna(subset=["value"])
    agg = long.groupby([sub, scen, "year"]).agg(value=("value", "sum"), kv=("kv", "max")).reset_index()
    forecast = pd.DataFrame({"station": agg[sub].astype(str).str.strip(), "year": agg["year"],
                             "scenario": agg[scen].map(lambda v: _scenario(v) or str(v)), "metric": "headroom",
                             "unit": "MVA", "value": agg["value"]})
    st = agg.groupby(sub)["kv"].max().reset_index()
    stations = pd.DataFrame({"station": st[sub].astype(str).str.strip(), "sheet": sheet, "area": "",
                             "voltage": st["kv"].map(lambda k: f"{int(k)} kV" if pd.notna(k) else ""),
                             "lat": np.nan, "lon": np.nan})
    return {"sheet": sheet, "header_row": None, "station_col": sub, "area_cols": [], "has_location": False,
            "stations": stations, "forecast": forecast, "n": len(stations), "layout": "block list"}


def parse_sheet(sheet: str, raw: pd.DataFrame, override: dict | None = None) -> dict | None:
    override = override or {}
    hd = _header(raw, override.get("header_row"))
    if not hd:
        return None
    h, names = hd
    df = raw.iloc[h + 1:].copy()
    df.columns = names
    df = df.dropna(how="all").dropna(axis=1, how="all")
    if len(df) < 5:
        return None
    blk = _block_list(sheet, df)
    if blk is not None:
        blk["header_row"] = h
        return blk
    cols = list(df.columns)
    text_cols = [c for c in cols if df[c].map(lambda v: isinstance(v, str)).mean() > 0.6]

    station = override.get("station") or _first(cols, r"(sub)?station.*name|name.*(sub)?station|^(sub)?station$",
                                                r"county|region|area|type|kv|volt|id$|code")
    if station is None or station not in text_cols:
        station = _first(text_cols, r"name|station") or (max(text_cols, key=lambda c: df[c].nunique())
                                                         if text_cols else None)
    if station is None:
        return None
    area_cols = [c for c in text_cols if re.search(r"county|region|area|district|location|zone", c, re.I)
                 and c != station]
    lat = override.get("lat") or _first(cols, r"\blat")
    lon = override.get("lon") or _first(cols, r"\blon|\blong")
    east = _first(cols, r"east|itm.?x|x.?itm|^x$")
    north = _first(cols, r"north|itm.?y|y.?itm|^y$")
    volt = _first(cols, r"kv|voltage|volt", r"available|headroom|capacity|demand|load|20[2-5]\d")
    if volt is None:  # voltage written inside another column, e.g. Station Type = "110kV Station"
        volt = next((c for c in text_cols if c != station and
                     df[c].astype(str).str.contains(r"\b(?:110|38)\s*kv", case=False, regex=True).mean() > 0.2), None)
    scen_col = _first(text_cols, r"scenario")
    year_col = next((c for c in cols if re.search(r"^year$|^years?\b", c.strip(), re.I) and not YEAR.search(c)), None)

    base = pd.DataFrame({"station": df[station].astype(str).str.strip(), "sheet": sheet})
    base["area"] = df[area_cols].astype(str).agg(" / ".join, axis=1) if area_cols else ""
    base["voltage"] = df[volt].astype(str) if volt else ""
    if lat and lon:
        base["lat"], base["lon"] = df[lat].map(_num), df[lon].map(_num)
    elif east and north:
        e, n = df[east].map(_num).to_numpy(), df[north].map(_num).to_numpy()
        ok = (e > 300000) & (e < 800000) & (n > 500000) & (n < 1000000)
        la, lo = itm_to_wgs84(np.where(ok, e, 600000), np.where(ok, n, 750000))
        base["lat"], base["lon"] = np.where(ok, la, np.nan), np.where(ok, lo, np.nan)
    else:
        base["lat"] = base["lon"] = np.nan
    base = base[base["station"].str.len().between(2, 80) & ~base["station"].str.lower().isin({"nan", "total"})]
    idx = base.index

    sheet_scen = _scenario(sheet)
    used = {station, volt, lat, lon, east, north, scen_col, year_col, *area_cols}
    long_rows, static = [], {}
    for c in cols:
        if c in used:
            continue
        vals = df.loc[idx, c].map(_num)
        if vals.notna().mean() < 0.3:
            continue
        lc = c.lower()
        if re.search(r"\btype\b|method|id\b|code", lc):
            continue
        metric = ("headroom" if re.search(r"headroom|available|spare|remaining|capacity for", lc) else
                  "demand" if re.search(r"demand|load|forecast|peak|maximum|utili", lc) else
                  "capacity" if re.search(r"firm|rating|installed|capacity|transformer", lc) else None)
        unit = "MVA" if "mva" in lc else "MW" if "mw" in lc else ""
        yr = YEAR.search(c)
        if yr:
            long_rows.append(pd.DataFrame({"station": base["station"], "year": int(yr.group(1)),
                                           "scenario": _scenario(c) or sheet_scen or "Unspecified",
                                           "metric": metric or "headroom", "unit": unit, "value": vals}))
        elif metric:
            static[f"{metric}_now"] = static.get(f"{metric}_now", vals)  # first matching column wins
            static[f"{metric}_unit"] = unit
    if scen_col and year_col and not long_rows:  # tidy (long) layout
        for c in cols:
            if c in used:
                continue
            vals = df.loc[idx, c].map(_num)
            lc = c.lower()
            metric = ("headroom" if re.search(r"headroom|available|spare", lc) else
                      "demand" if re.search(r"demand|load|forecast", lc) else None)
            if metric and vals.notna().mean() > 0.3:
                long_rows.append(pd.DataFrame({
                    "station": base["station"], "year": df.loc[idx, year_col].map(_num),
                    "scenario": df.loc[idx, scen_col].map(lambda v: _scenario(v) or str(v)),
                    "metric": metric, "unit": "MVA" if "mva" in lc else "MW" if "mw" in lc else "", "value": vals}))
    for k, v in static.items():
        base[k] = v if isinstance(v, str) else v.reindex(idx)
    forecast = pd.concat(long_rows, ignore_index=True).dropna(subset=["value", "year"]) if long_rows else None
    return {"sheet": sheet, "header_row": h, "station_col": station, "area_cols": area_cols, "columns": cols,
            "headroom_col": next((c for c in cols if c not in used and re.search(
                r"headroom|available|spare|remaining|capacity for", c, re.I) and not YEAR.search(c)), None),
            "has_location": bool(base["lat"].notna().mean() > 0.5), "stations": base.reset_index(drop=True),
            "forecast": forecast, "n": len(base)}


def parse_workbook(path: Path, key: str) -> tuple[list[dict], str]:
    sheets = read_workbook(path)
    text = describe(path, sheets)
    ov = ESBN_OVERRIDE.get(key, {})
    parsed = []
    for name, raw in sheets.items():
        if ov.get("sheet") and name != ov["sheet"]:
            continue
        if re.search(r"search|intro|read ?me|notes|guide|disclaimer|selector", name, re.I):
            continue  # instructions and calculator sheets, not data
        r = parse_sheet(name, raw, ov)
        if r and r["n"] >= 5:
            parsed.append(r)
    lines = [f"\n>>> detected in {Path(path).name}:"]
    for r in parsed:
        f = r["forecast"]
        lines.append(f"  sheet '{r['sheet']}' [{r.get('layout', 'table')}]: header row {r['header_row']}, "
                     f"station column '{r['station_col']}', "
                     f"areas {r['area_cols']}, location {'yes' if r['has_location'] else 'no'}, {r['n']} rows, "
                     f"static {[c for c in r['stations'].columns if c.endswith('_now')]}, forecast "
                     + (f"{len(f)} values, years {[int(y) for y in sorted(f['year'].unique())][:12]}, scenarios "
                        f"{sorted(f['scenario'].unique())[:6]}, metrics {sorted(f['metric'].unique())}"
                        if f is not None else "none"))
        if r.get("columns"):
            lines.append("      columns: " + " | ".join(str(c)[:30] for c in r["columns"][:30]))
    return parsed, text + "\n" + "\n".join(lines)


# --------------------------------------------------------------------------- region selection
def _in_polys(lat: np.ndarray, lon: np.ndarray, polys) -> np.ndarray:
    from matplotlib.path import Path as MPath
    pts = np.c_[lon, lat]
    inside = np.zeros(len(pts), bool)
    ok = ~np.isnan(pts).any(axis=1)
    for _, rings in polys:
        for r in rings:
            inside[ok] |= MPath(r).contains_points(pts[ok])
    return inside


def cork_stations(parsed: dict[str, list[dict]], polys) -> tuple[pd.DataFrame, pd.DataFrame | None, dict]:
    """Combine both workbooks into one table of the region's stations, plus ESB Networks' own forecasts for them.
    (Named for the original Cork project; works for any region in config.REGIONS.)"""
    info = {"method": None, "heatmap_sheets": 0, "headroom_sheets": 0}
    frames = []
    for key, items in parsed.items():
        for r in items:
            s = r["stations"].copy()
            s["source"] = key
            frames.append(s)
            info[f"{key}_sheets"] += 1
    if not frames:
        return pd.DataFrame(), None, info
    allst = pd.concat(frames, ignore_index=True)
    allst["key"] = allst["station"].map(norm_name)
    allst = allst[allst["key"].str.len() >= 3]

    # Names differ slightly between the two workbooks; match heatmap stations to the forecast list by name
    # (one name contained in the other, or near-identical spelling). Every match is saved for checking.
    master = set(allst.loc[allst["source"] == "headroom", "key"])
    matches = []
    if master:
        import difflib
        mlist = sorted(master)
        hv = allst["voltage"].astype(str).str.contains(r"\b(?:110|38)\b") | allst["station"].str.contains(r"\b(?:110|38)\s*kv", case=False)
        for k in sorted(set(allst.loc[(allst["source"] == "heatmap") & hv, "key"]) - master):
            cand = [m for m in mlist if len(min(k, m, key=len)) >= 5 and (k.startswith(m) or m.startswith(k))]
            if not cand:
                cand = difflib.get_close_matches(k, mlist, n=2, cutoff=0.86)
                if len(cand) == 2 and difflib.SequenceMatcher(None, k, cand[0]).ratio() - \
                        difflib.SequenceMatcher(None, k, cand[1]).ratio() < 0.03:
                    cand = []  # ambiguous: leave unmatched rather than guess
            if cand:
                best = max(cand, key=lambda m: difflib.SequenceMatcher(None, k, m).ratio())
                matches.append((k, best))
        remap = dict(matches)
        allst.loc[allst["source"] == "heatmap", "key"] = allst.loc[allst["source"] == "heatmap", "key"].replace(remap)
    info["name_matches"] = matches

    # location and area per station from whichever sheet has them
    loc = allst.dropna(subset=["lat", "lon"]).groupby("key")[["lat", "lon"]].first()
    area = allst[allst["area"].str.len() > 0].groupby("key")["area"].first()
    st = allst.groupby("key").agg(station=("station", "first"), voltage=("voltage", "first")).join(loc).join(area)
    for c in ["headroom_now", "capacity_now", "demand_now"]:
        if c in allst:  # the heatmap has one row per transformer group: a station's total is their sum
            st[c] = allst.groupby("key")[c].sum(min_count=1)
    is_cork = st["area"].fillna("").str.lower().str.contains("|".join(map(re.escape, R["region_terms"])))
    info["method"] = "county/area column" if is_cork.any() else None
    if polys is not None and st["lat"].notna().any():
        in_poly = _in_polys(st["lat"].to_numpy(), st["lon"].to_numpy(), polys)
        if not is_cork.any():
            info["method"] = f"location inside {NAME}'s electoral divisions"
        is_cork = is_cork | in_poly
    cork = st[is_cork].copy()
    cork["kv"] = cork["voltage"].fillna("").str.extract(r"(110|38)")[0].astype(float)
    cork.loc[cork["kv"].isna(), "kv"] = cork.loc[cork["kv"].isna(), "station"].str.extract(r"(110|38)")[0].astype(float)

    fc = []
    has_block = any(r.get("layout") == "block list" for items in parsed.values() for r in items)
    for items in parsed.values():
        for r in items:
            if has_block and r.get("layout") != "block list":
                continue  # ESB Networks' master list is the authoritative forecast; ignore calculator sheets
            if r["forecast"] is not None:
                f = r["forecast"].copy()
                f["key"] = f["station"].map(norm_name)
                fc.append(f)
    forecast = pd.concat(fc, ignore_index=True) if fc else None
    info["name_aliases"] = 0
    if forecast is not None and len(forecast):
        # Station names differ slightly between the two workbooks ("CORK CITY 38KV" vs "CORK CITY", "BALLINCOLLIG"
        # vs "BALLINCOLLIG T"); link a Cork station to the forecast name that is almost identical.
        import difflib
        fkeys = set(forecast["key"].unique())
        alias = {}
        for k in cork.index:
            if k in fkeys:
                continue
            pref = [f for f in fkeys if (f.startswith(k) or k.startswith(f)) and min(len(f), len(k)) >= 5]
            m = pref[:1] or difflib.get_close_matches(k, fkeys, n=1, cutoff=0.88)
            if m and m[0] not in cork.index:
                alias[m[0]] = k
        forecast["key"] = forecast["key"].replace(alias)
        info["name_aliases"] = len(alias)
        forecast = forecast[forecast["key"].isin(cork.index)]
        if not len(forecast):
            forecast = None
    if forecast is not None and not len(forecast):
        forecast = None
    # Spare capacity today: ESB Networks' own firm headroom for the first forecast year (MVA, converted to MW at
    # power factor 0.95) where available, because its units are documented; otherwise the heatmap figure.
    info["headroom_source"] = "heatmap"
    if "headroom_now" not in cork:
        cork["headroom_now"] = np.nan
    if forecast is not None:
        h = forecast[forecast["metric"] == "headroom"]
        if len(h):
            y0 = h["year"].min()
            pref = [x for x in ("Best View", "Base") if x in set(h["scenario"])]
            h0 = h[(h["year"] == y0) & (h["scenario"] == (pref[0] if pref else h["scenario"].iloc[0]))]
            fac = 0.95 if (h0["unit"] == "MVA").all() else 1.0
            wb = h0.groupby("key")["value"].sum() * fac
            got = wb.reindex(cork.index)
            info["headroom_from_workbook"] = int(got.notna().sum())
            cork["headroom_now"] = got.fillna(cork["headroom_now"])
            info["headroom_source"] = f"ESB Networks workbook ({pref[0] if pref else 'first scenario'} {int(y0)})"
    cork["headroom_now"] = cork["headroom_now"].clip(lower=0)
    # Stations on ESB Networks' demand list serve customers; others in the heatmap are mostly generation-only
    # (wind farms, hydro), transmission or dedicated customer stations, which do not take new local demand.
    if forecast is not None:
        cork["demand_station"] = cork.index.isin(set(forecast["key"]))
        info["not_demand"] = sorted(cork.loc[~cork["demand_station"] & cork["kv"].isin([38, 110]), "station"].str.title())
    else:
        cork["demand_station"] = True
    info["n_cork"] = int(len(cork))
    info["with_location"] = int(cork["lat"].notna().sum())
    info["with_headroom"] = int(cork["headroom_now"].notna().sum()) if "headroom_now" in cork else 0
    return cork, forecast, info


region_stations = cork_stations
