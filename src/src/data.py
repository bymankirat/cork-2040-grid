"""Download public data and build the region's starting point: consumption history and one row per electoral division."""

from __future__ import annotations

import json
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from config import BOUNDARY_URL, CSO_API, CSO_TABLES, ESBN, ESBN_PAGE, RAW_DIR, REGION_KEY, R

STANDARD = {"STATISTIC", "Statistic Label", "TLIST(A1)", "Census Year", "Sex", "UNIT", "VALUE"}


# --------------------------------------------------------------------------- download
def _fetch(url: str, timeout: int = 300) -> bytes:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:  # noqa: BLE001  some Python installs lack SSL certificates; curl usually works
        return subprocess.run(["curl", "-sSL", "-A", "Mozilla/5.0", "--max-time", str(timeout), url],
                              capture_output=True, check=True).stdout


def download_cso(folder: Path = RAW_DIR, force: bool = False) -> dict[str, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    out = {}
    for key, table in CSO_TABLES.items():
        p = folder / f"{table}.csv"
        if force or not p.exists() or p.stat().st_size < 1000:
            print(f"     CSO {table} ({key}) ...")
            data = _fetch(CSO_API.format(table=table))
            if b"STATISTIC" not in data[:500]:
                raise ValueError(f"unexpected reply from CSO for {table}")
            p.write_bytes(data)
        out[key] = p
    return out


def download_esbn(folder: Path = RAW_DIR, force: bool = False) -> dict[str, Path | None]:
    """The two ESB Networks workbooks. If the download is blocked, the run continues without station data and
    prints where to save the files by hand."""
    folder.mkdir(parents=True, exist_ok=True)
    out = {}
    for key, (name, url) in ESBN.items():
        p = folder / name
        if p.exists() and p.stat().st_size > 10_000 and not force:
            out[key] = p
            continue
        try:
            print(f"     ESB Networks {key} workbook (large file) ...")
            data = _fetch(url, timeout=600)
            if data[:2] != b"PK":
                raise ValueError("the server did not return an Excel file")
            p.write_bytes(data)
            out[key] = p
        except Exception as e:  # noqa: BLE001
            print(f"     [!] Could not download {name} ({e}).\n         Download it in Chrome from {ESBN_PAGE}\n"
                  f"         and save it as {p}")
            out[key] = p if p.exists() else None
    return out


def download_boundaries(folder: Path = RAW_DIR, force: bool = False) -> Path | None:
    """The region's electoral division polygons (WGS84) for the maps."""
    p = folder / f"{REGION_KEY}_ed_boundaries.geojson"
    if p.exists() and not force:
        return p
    try:
        q = urllib.parse.urlencode({"where": R["boundary_where"], "outFields": "ED_GUID,ED_ENGLISH,COUNTY_ENGLISH", "outSR": 4326,
                                    "f": "geojson", "resultRecordCount": 2000, "geometryPrecision": 5,
                                    "maxAllowableOffset": 0.0008})
        gj = json.loads(_fetch(f"{BOUNDARY_URL}?{q}"))
        if not gj.get("features"):
            raise ValueError("no features returned")
        p.write_text(json.dumps(gj))
        return p
    except Exception as e:  # noqa: BLE001
        print(f"     [!] Could not download boundaries ({e}); maps will be skipped.")
        return None


# --------------------------------------------------------------------------- CSO readers
def read_consumption(path: Path) -> pd.DataFrame:
    """The region's metered electricity by year and sector (GWh). Columns: residential, non_residential, total.
    Several MEC03 rows can make one region (Dublin = "Co. Dublin" plus postal districts Dublin 1-24)."""
    raw = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    county = next(c for c in raw.columns if "count" in c.lower() and not c.startswith("C0"))
    sector = next(c for c in raw.columns if "sector" in c.lower() and not c.startswith("C0"))
    year = next(c for c in raw.columns if c.lower() in ("year", "tlist(a1)"))
    lab = raw[county].str.strip().str.lower()
    keep = lab.isin(R["cso_labels"])
    for pre in R["cso_prefixes"]:
        keep |= lab.str.startswith(pre)
    d = raw[keep].copy()
    d["value"] = pd.to_numeric(d["VALUE"], errors="coerce")
    d["sector"] = d[sector].str.lower().map(
        lambda s: "residential" if "non" not in s and "resid" in s else "non_residential" if "non" in s else "total")
    # sum the parts of the region; a year counts only if every part reported it
    parts = d[county].nunique()
    w = d.pivot_table(index=pd.to_numeric(d[year]), columns="sector", values="value", aggfunc="sum")
    n = d.dropna(subset=["value"]).groupby([pd.to_numeric(d[year]), "sector"])[county].nunique().unstack()
    w = w.where(n.reindex_like(w) >= parts)
    w.index.name = "year"
    if "total" not in w:
        w["total"] = w.sum(axis=1)
    return w.dropna(how="all").sort_index()


def _read_ed(path: Path) -> tuple[pd.DataFrame, pd.Series]:
    raw = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    raw.columns = [c.strip() for c in raw.columns]
    geo_label = next(c for c in raw.columns if "Electoral Division" in c)
    geo_code = raw.columns[raw.columns.get_loc(geo_label) - 1]
    cat_col = next(c for c in raw.columns if c not in STANDARD | {geo_label, geo_code} and not c.startswith("C0"))
    df = raw
    if "Sex" in df.columns:
        df = df[df["Sex"].str.strip().str.lower() == "both sexes"]
    df = df[~df[geo_label].str.strip().str.lower().isin({"ireland", "state"})]
    df = df.assign(value=pd.to_numeric(df["VALUE"], errors="coerce"), cat=df[cat_col].str.strip().str.lower())
    if df["Statistic Label"].nunique() > 1:  # keep households, not persons, where a table has both
        hh = df["Statistic Label"].str.lower().str.contains("household")
        if hh.any():
            df = df[hh]
    wide = df.pivot_table(index=geo_code, columns="cat", values="value", aggfunc="first")
    names = df.drop_duplicates(geo_code).set_index(geo_code)[geo_label].str.strip()
    return wide, names


def _cols(w: pd.DataFrame, *keys, exclude=()) -> list[str]:
    return [c for c in w.columns if any(k in c for k in keys) and not any(x in c for x in exclude)]


def build_eds(paths: dict[str, Path]) -> tuple[pd.DataFrame, dict]:
    """One row per electoral division in the region: population, households, heating fuel, cars."""
    heat, names = _read_ed(paths["heating"])
    cars, _ = _read_ed(paths["cars"])
    pop, _ = _read_ed(paths["population"])

    total_h = heat[_cols(heat, "total")].sum(axis=1)
    elec = heat[_cols(heat, "electric")].sum(axis=1)
    not_stated = heat[_cols(heat, "not stated")].sum(axis=1)
    car_count = pd.Series(0.0, index=cars.index)
    car_cols = {}
    words = {"no": 0, "none": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    for c in cars.columns:
        if "total" in c or "not stated" in c:
            continue
        m = re.match(r"\s*(\d+|no|none|one|two|three|four|five)\b", c)
        if m:  # "1 motor car", "Two motor cars", "4 or more motor cars", "No motor car"
            k = int(m.group(1)) if m.group(1).isdigit() else words[m.group(1)]
            car_count += k * cars[c].fillna(0)
            car_cols[c] = k
    eds = pd.DataFrame({
        "ed": names, "population": pop[_cols(pop, "total")].sum(axis=1),
        "households": total_h, "hh_electric_heat": elec, "hh_heat_not_stated": not_stated,
        "cars": car_count,
    })
    suffix = eds["ed"].str.rsplit(",", n=1).str[-1].str.strip()
    low = suffix.str.lower()
    in_region = low.str.contains("|".join(map(re.escape, R["region_terms"])))
    area = pd.Series(None, index=eds.index, dtype=object)
    for name, terms in R["areas"]:  # first rule that matches wins
        hit = area.isna() & in_region & low.apply(lambda x, t=terms: any(k in x for k in t))
        area[hit] = name
    eds["area"] = area
    area_labels = suffix[in_region].value_counts().to_dict()
    eds = eds[in_region & area.notna()].copy()
    eds["hh_convertible"] = (eds["households"] - eds["hh_electric_heat"] - eds["hh_heat_not_stated"]).clip(lower=0)
    eds.index.name = "ed_guid"
    meta = {"heating_categories": list(heat.columns), "car_categories": car_cols, "area_labels": area_labels,
            "car_columns_all": list(cars.columns), "population_columns": [c for c in pop.columns if "total" in c],
            "eds": len(eds), "areas": eds["area"].value_counts().to_dict()}
    return eds, meta
