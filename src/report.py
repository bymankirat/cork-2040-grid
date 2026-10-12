"""Self-contained web report, written for an electricity network planning audience."""

from __future__ import annotations

import base64
import html
from pathlib import Path

import pandas as pd

from config import ASSUMPTIONS as A
from config import ESBN_PAGE, NETWORK, SCENARIO_NAMES, SCENARIOS, TARGET_YEAR

AUTHOR = "Mankirat Singh"
REPO = "https://github.com/bymankirat/cork-2040-grid"
LINKS = {"Portfolio": "https://bymankirat.github.io/myportfolio/", "GitHub": "https://github.com/bymankirat",
         "LinkedIn": "https://linkedin.com/in/mankirat-singh-694440177"}


def _img(p, alt):
    if not p:
        return ""
    return f'<img src="data:image/png;base64,{base64.b64encode(Path(p).read_bytes()).decode()}" alt="{html.escape(alt)}">'


def _rng(d, fmt="{:,.0f}"):
    return f"{fmt.format(d[10])}–{fmt.format(d[90])}"


def headline(base, scen, plan, view) -> dict:
    c = scen["central"]["yearly"].loc[TARGET_YEAR]
    s = plan["summary"]
    st = plan.get("stations", {}).get(("central", False))
    return {
        "base_year": base["year"], "base_gwh": base["total_gwh"], "base_peak": base["peak_mw"],
        "peak_2040": {k: float(scen[k]["yearly"].loc[TARGET_YEAR, "peak_mw"]) for k in SCENARIOS},
        "peak_2040_flex": float(scen["central"]["yearly_flex"].loc[TARGET_YEAR, "peak_mw"]),
        "growth_pct": 100 * (c["peak_mw"] / base["peak_mw"] - 1), "extra_central": float(c["extra_peak_mw"]),
        "heat_pumps": float(c["heat_pumps"]), "evs": float(c["evs"]),
        "top_driver": max(["homes_mw", "business_mw", "heat_pumps_mw", "evs_mw", "large_loads_mw"], key=lambda k: c[k]),
        "stations_short": int((st["deficit_mw"] > 0).sum()) if st is not None else None,
        "stations_total": int(len(st)) if st is not None else None,
        "new_p50": s["stations_new"][50], "new_range": (s["stations_new"][10], s["stations_new"][90]),
        "new_flex_p50": s["stations_new_flex"][50], "uprates_p50": s["uprates"][50],
        "cost": s["cost_m"], "cost_flex": s["cost_m_flex"], "saving": s["saving_m"], "method": plan["method"],
        "esbn_2040": (view["table"][view["table"]["year"] == 2040][["scenario", "negative", "deficit"]]
                      .to_dict("records") if view else None),
    }


def build(cons, base, eds, scen, plan, sens, view, qc, figs, esbn_info, demo) -> str:
    hl = headline(base, scen, plan, view)
    s = plan["summary"]
    cause = {"homes_mw": "new homes and population", "business_mw": "business growth", "heat_pumps_mw": "heat pumps",
             "evs_mw": "electric cars", "large_loads_mw": "new large loads"}
    findings = [
        f"Co. Cork used <b>{hl['base_gwh']:,.0f} GWh</b> of electricity in {hl['base_year']}, equivalent to a winter "
        f"peak of about <b>{hl['base_peak']:,.0f} MW</b>.",
        f"By {TARGET_YEAR} the peak could reach <b>{hl['peak_2040']['central']:,.0f} MW</b> in the central case "
        f"(+{hl['growth_pct']:.0f}%), and {hl['peak_2040']['low']:,.0f}–{hl['peak_2040']['high']:,.0f} MW across "
        f"scenarios. The biggest single driver is <b>{cause[hl['top_driver']]}</b>, with about "
        f"{hl['heat_pumps']:,.0f} extra heat pumps and {hl['evs']:,.0f} extra electric cars.",
    ]
    if hl["stations_short"] is not None:
        findings.append(f"<b>{hl['stations_short']} of {hl['stations_total']}</b> Cork 110 kV / 38 kV substations "
                        f"would run short of capacity by {TARGET_YEAR} (central case).")
    findings.append(
        f"Meeting it needs about <b>{hl['new_p50']:.0f} new substations</b> (10–90% range "
        f"{hl['new_range'][0]:.0f}–{hl['new_range'][1]:.0f})" + (f" plus about {hl['uprates_p50']:.0f} upgrades"
                                                                 if hl["uprates_p50"] else "")
        + f", costing <b>€{_rng(hl['cost'])}m</b> in station investment alone (2026 prices).")
    findings.append(
        f"<b>Flexibility pays:</b> smart EV charging, heat-pump flexibility and demand response cut the 2040 peak to "
        f"{hl['peak_2040_flex']:,.0f} MW and the median station bill by about <b>€{max(hl['saving'], 0):,.0f}m</b> "
        f"({hl['new_flex_p50']:.0f} new stations instead of {hl['new_p50']:.0f}).")
    compare = ""
    if hl["esbn_2040"]:
        r = hl["esbn_2040"]
        findings.append("ESB Networks' own station forecasts point the same way: in 2040 "
                        + ", ".join(f"{x['scenario']} {int(x['negative'])}" for x in r)
                        + " Cork stations have no firm spare capacity left.")
        if hl["stations_short"] is not None:
            near = min(r, key=lambda x: abs(x["negative"] - hl["stations_short"]))
            more = hl["stations_short"] > max(x["negative"] for x in r)
            compare = (f"<p><b>How this compares:</b> the central case here finds {hl['stations_short']} stations short, "
                       f"closest to ESB Networks' <b>{near['scenario']}</b> scenario ({int(near['negative'])})."
                       + (" It is more demanding than all four, mainly because it assumes faster heat-pump and EV "
                          "uptake to meet the 2040 net-zero path, and uses today's spare capacity from the heatmap "
                          "rather than ESB Networks' planned reinforcements." if more else
                          " Differences come from uptake assumptions and from ESB Networks' planned reinforcements, "
                          "which this model does not include.") + "</p>")

    yrows = []
    for sname in SCENARIOS:
        y = scen[sname]["yearly"].loc[TARGET_YEAR]
        yrows.append(f"<tr><td>{SCENARIO_NAMES[sname]}</td><td class='num'>{y['peak_mw']:,.0f}</td>"
                     f"<td class='num'>{y['energy_gwh']:,.0f}</td><td class='num'>{y['heat_pumps']:,.0f}</td>"
                     f"<td class='num'>{y['evs']:,.0f}</td><td class='num'>{y['households']:,.0f}</td></tr>")
    st = plan.get("stations", {}).get(("central", False))
    st_rows = ""
    if st is not None:
        ex = plan.get("exhaust_year", pd.Series(dtype=float))
        top = st.sort_values("deficit_mw", ascending=False)
        top = top[top["deficit_mw"] > 0].head(15)
        st_rows = "".join(
            f"<tr><td>{html.escape(str(r['station']))}</td><td class='num'>{int(r['kv']) if pd.notna(r['kv']) else '–'}</td>"
            f"<td class='num'>{r['headroom_mw']:.1f}</td><td class='num'>{r['extra_mw']:.1f}</td>"
            f"<td class='num'>{r['deficit_mw']:.1f}</td><td>{r['action']}"
            f"{'' if not r['n_new'] else f' ×{int(r.n_new)}'}</td>"
            f"<td class='num'>{int(ex.get(k)) if pd.notna(ex.get(k)) else '–'}</td></tr>" for k, r in top.iterrows())
    budget_rows = "".join(
        f"<tr><td>{lab}</td><td class='num'>{s[k][10]:,.0f}</td><td class='num'>{s[k][50]:,.0f}</td>"
        f"<td class='num'>{s[k][90]:,.0f}</td></tr>" for k, lab in (
            ("extra_mw", "Extra peak (MW)"), ("extra_mw_flex", "Extra peak with flexibility (MW)"),
            ("n110", "New 110 kV stations"), ("n38", "New 38 kV stations"), ("uprates", "Station upgrades"),
            ("cost_m", "Station investment (€m)"), ("cost_m_flex", "Station investment with flexibility (€m)")))
    esbn_rows = ""
    if view:
        t = view["table"]
        t = t[t["year"].isin([2030, 2035, 2040, 2050])]
        esbn_rows = "".join(f"<tr><td>{r['scenario']}</td><td class='num'>{int(r['year'])}</td>"
                            f"<td class='num'>{int(r['negative'])} of {int(r['stations'])}</td>"
                            f"<td class='num'>{r['headroom']:,.0f}</td></tr>"
                            for _, r in t.sort_values(["year", "scenario"]).iterrows())
    asum = [
        ("Population growth 2022–2040, Cork City", A["pop_growth_2040"]["Cork City"], "{:.0%}",
         "Revised National Planning Framework 2025: +950,000 nationally, half in the five cities"),
        ("Population growth 2022–2040, Cork County", A["pop_growth_2040"]["Cork County"], "{:.0%}", "As above"),
        ("Homes with a heat pump in 2040", A["heat_pump_share_2040"], "{:.0%}",
         "Climate Action Plan: ~680,000 heat pumps by 2030"),
        ("Cars that are electric in 2040", A["ev_share_2040"], "{:.0%}", "Climate Action Plan / PR6: up to 1m EVs by 2030"),
        ("Extra peak per heat-pump home (kW)", A["hp_peak_kw"], "{:.2f}",
         "UCC field trial: 2.33 kW typical winter, 3.84 kW extreme cold (part replaces existing load)"),
        ("Peak per electric car (kW)", A["ev_peak_kw"], "{:.2f}",
         f"Assumption: ~1 kW unmanaged, {A['ev_peak_kw_smart']} kW smart; ESB Networks base: 85% smart by 2040"),
        ("Business growth per year", A["nonres_growth_pa"], "{:.1%}", "Assumption; CSO trend 2015–2025"),
        ("New large loads (MW)", A["large_loads_mw"], "{:.0f}", "Assumption (industrial electrification, ports)"),
        ("Efficiency gain per home by 2040", A["res_efficiency_2040"], "{:.0%}", "Assumption"),
    ]
    a_rows = "".join(f"<tr><td>{n}</td>" + "".join(f"<td class='num'>{f.format(v[k])}</td>" for k in SCENARIOS)
                     + f"<td class='muted'>{html.escape(src)}</td></tr>" for n, v, f, src in asum)
    net_rows = "".join(f"<tr><td>{k.replace('_', ' ').replace('kv', ' kV')}</td>"
                       f"<td class='num'>{v['mva'][0]}–{v['mva'][2]} (most likely {v['mva'][1]})</td>"
                       f"<td class='num'>{v['cost_m'][0]}–{v['cost_m'][2]} (most likely {v['cost_m'][1]})</td></tr>"
                       for k, v in NETWORK.items())
    qc_rows = "".join(f"<tr><td class='qc-{x.lower()}'>{x}</td><td>{html.escape(c)}</td><td>{html.escape(d)}</td></tr>"
                      for x, c, d in qc["results"])

    method_txt = (
        "<p>Each electoral division's extra 2040 load is assigned to its nearest 110 kV or 38 kV station and compared "
        "with that station's spare capacity today (ESB Networks data). Only stations on ESB Networks' demand list "
        "take new load; generation-only stations such as wind farms and hydro are excluded. A small shortfall is met by upgrading the "
        "station (for example larger transformers); a larger one is met by upgrading it and adding new station(s) "
        "nearby for the rest.</p>"
        if plan["method"] == "spatial" else
        f"<p>Station locations or spare capacity were not available, so new capacity is sized for Cork as a whole: the "
        f"extra peak minus today's total spare capacity ({plan.get('headroom_total', 0):,.0f} MW), split between "
        f"110 kV and 38 kV stations. This is cruder than a station-by-station plan.</p>")

    banner = ('<div class="banner">DEMO DATA: simulated numbers for testing. Run without --demo to use the real '
              'CSO and ESB Networks data before publishing.</div>') if demo else ""
    links = " · ".join(f'<a href="{u}">{k}</a>' for k, u in LINKS.items())

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cork 2040 Grid</title>
<style>
:root{{--bg:#fcfcfb;--card:#fff;--ink:#0b0b0b;--ink-2:#52514e;--line:#e4e3df;--accent:#2a78d6;--hl:#eef4fc;--warn-bg:#fff4e5;--warn-ink:#7a3d00}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#1a1a19;--card:#232322;--ink:#f0efec;--ink-2:#c3c2b7;--line:#3a3a38;--accent:#3987e5;--hl:#1f2a3a;--warn-bg:#3a2a12;--warn-ink:#ffd08a}}:root:not([data-theme="light"]) img{{background:#fcfcfb}}}}
:root[data-theme="dark"]{{--bg:#1a1a19;--card:#232322;--ink:#f0efec;--ink-2:#c3c2b7;--line:#3a3a38;--accent:#3987e5;--hl:#1f2a3a;--warn-bg:#3a2a12;--warn-ink:#ffd08a}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:940px;margin:0 auto;padding:40px 16px 64px}}
.kicker{{color:var(--accent);font-weight:700;letter-spacing:.04em;text-transform:uppercase;font-size:.82rem}}
h1{{font-size:clamp(1.6rem,4vw,2.3rem);line-height:1.2;margin:6px 0 8px}}h2{{font-size:1.3rem;margin:44px 0 8px}}h3{{font-size:1.05rem;margin:24px 0 6px}}
.byline,.muted{{color:var(--ink-2)}}a{{color:var(--accent)}}
.banner{{background:var(--warn-bg);color:var(--warn-ink);padding:12px 16px;border-radius:8px;font-weight:600;margin:16px 0}}
.note{{border-left:3px solid var(--accent);padding:6px 12px;color:var(--ink-2);font-size:.92rem;margin:14px 0}}
.findings{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 20px 16px 36px;margin:20px 0}}
.findings li{{margin:7px 0}}
img{{width:100%;height:auto;border:1px solid var(--line);border-radius:8px;margin:12px 0}}
.table-wrap{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;margin:12px 0;font-size:.92rem}}
th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line)}}th{{color:var(--ink-2);font-weight:600}}
.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
td.qc-pass{{color:#008300;font-weight:700}}td.qc-warn{{color:#b06f00;font-weight:700}}td.qc-fail{{color:#e34948;font-weight:700}}
.topnav{{position:sticky;top:0;z-index:10;background:var(--bg);border-bottom:1px solid var(--line)}}
.topnav .in{{max-width:940px;margin:0 auto;padding:10px 16px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.topnav .brand{{font-weight:700;margin-right:auto}}
.tab{{padding:6px 12px;border-radius:999px;border:1px solid var(--line);text-decoration:none;color:var(--ink);font-weight:600;font-size:.9rem}}
.tab.on{{background:var(--accent);border-color:var(--accent);color:#fff}}
.mapcta{{display:flex;gap:14px;align-items:center;background:var(--hl);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:14px 0}}
.mapcta a.btn{{background:var(--accent);color:#fff;text-decoration:none;padding:8px 14px;border-radius:8px;font-weight:700;white-space:nowrap}}
footer{{margin-top:52px;padding-top:16px;border-top:1px solid var(--line);color:var(--ink-2);font-size:.9rem}}
</style></head><body>
<nav class="topnav"><div class="in"><span class="brand">Cork 2040 Grid</span>
<a class="tab on" href="index.html">Report</a><a class="tab" href="map.html">Interactive map →</a></div></nav>
<main>
{banner}
<div class="kicker">Network planning to 2040 · open data</div>
<h1>Cork 2040: How Much Power, How Many Substations, What Budget?</h1>
<p class="byline">{AUTHOR} · {links}</p>
<p class="note">Co. Cork (Cork City and Cork County). Data: CSO metered electricity consumption and Census 2022 (heating,
cars, population by electoral division); ESB Networks Demand Capacity Headroom Report and customer heatmap. 2040 is the
year of ESB's Net Zero strategy. Independent analysis, not an ESB or ESB Networks publication.</p>

<h2>Key findings</h2>
<ul class="findings">{''.join(f'<li>{f}</li>' for f in findings)}</ul>

<h2>1. Where Cork starts</h2>
{_img(figs.get('history'), 'Cork electricity consumption')}
<p>Yearly consumption is turned into a winter peak with a load factor of {A['load_factor']:.2f} (average ÷ peak), the
quantity that sizes substations.</p>

<h2>2. How much power Cork will need</h2>
<p>The model adds, year by year: new homes and people, business growth, heat pumps (new homes plus conversions of
oil-, gas- and solid-fuel-heated homes, mapped from Census 2022), electric cars (from Census car ownership), and new
large loads, minus efficiency gains. Heat pumps and EVs follow an S-shaped uptake curve.</p>
{_img(figs.get('paths'), 'Cork peak demand to 2040')}
{_img(figs.get('drivers'), 'Drivers of growth')}
<div class="table-wrap"><table><thead><tr><th>{TARGET_YEAR}</th><th class="num">Peak (MW)</th><th class="num">Energy (GWh)</th>
<th class="num">Extra heat pumps</th><th class="num">Extra EVs</th><th class="num">Households</th></tr></thead>
<tbody>{''.join(yrows)}</tbody></table></div>

<h2>3. Where the new demand lands</h2>
{_img(figs.get('map'), 'Map of extra demand and substations')}
{'<div class="mapcta"><div>Explore every Cork substation on the <b>interactive map</b>: play 2025–2050 under ESB Networks\' four scenarios, switch to this project\'s 2040 verdicts, and click any station for its numbers.</div><a class="btn" href="map.html">Open map →</a></div>' if figs.get('webmap') else ''}

<h2>4. Which substations run out</h2>
{method_txt}
{_img(figs.get('stations'), 'Stations under pressure')}
{f'''<div class="table-wrap"><table><thead><tr><th>Station</th><th class="num">kV</th><th class="num">Spare today (MW)</th>
<th class="num">Extra by 2040 (MW)</th><th class="num">Shortfall (MW)</th><th>Action</th><th class="num">Full by</th></tr></thead>
<tbody>{st_rows}</tbody></table></div>''' if st_rows else ''}

<h2>5. What it costs</h2>
{_img(figs.get('budget'), 'Budget distribution')}
<div class="table-wrap"><table><thead><tr><th>By {TARGET_YEAR}</th><th class="num">10%</th><th class="num">Median</th>
<th class="num">90%</th></tr></thead><tbody>{budget_rows}</tbody></table></div>
<p class="muted">Station costs only, in 2026 euro. Circuits (cables and lines), land, connections and upstream
transmission are excluded, so the full programme cost is higher. For scale, the regulator approved €8.9bn of ESB
Networks capital investment nationally for 2026–2030 (PR6), including 69 new or upgraded substations.</p>

<h2>6. What matters most</h2>
{_img(figs.get('tornado'), 'Sensitivity')}

{f'''<h2>7. ESB Networks' own view</h2>
<p>The Demand Capacity Headroom Report gives ESB Networks' forecast headroom for each station under its four
scenarios. Counting Cork's stations is an independent cross-check on the bottom-up model above.</p>
{_img(figs.get('esbn'), 'ESB Networks headroom forecasts')}
<div class="table-wrap"><table><thead><tr><th>Scenario</th><th class="num">Year</th><th class="num">Stations with no firm headroom</th>
<th class="num">Spare capacity left ({view['unit'] or 'as published'})</th></tr></thead>
<tbody>{esbn_rows}</tbody></table></div>
{compare}''' if view else ''}

<h2>8. How Cork can accommodate it</h2>
<ul>
<li><b>Flexibility first.</b> Smart EV charging and heat-pump flexibility are the cheapest "capacity": they defer or
avoid stations (section 5). Time-of-use tariffs and managed charging should be in place before EV numbers peak.</li>
<li><b>Build where it runs out first.</b> Stations that fill earliest (section 4) set the order of work; planning and
consenting a 110 kV station takes years, so decisions are needed well before the year a station is full.</li>
<li><b>Upgrade before building.</b> Where the shortfall is small, a larger transformer at an existing site is faster
and cheaper than a new station.</li>
<li><b>Plan with the city.</b> Growth is concentrated in Cork City and its expansion areas; reserving sites and cable
routes in development plans now avoids costly retrofits later.</li>
<li><b>Keep the plan live.</b> Re-run yearly as ESB Networks updates its workbooks and CSO publishes new data.</li>
</ul>

<h2>9. Assumptions</h2>
<p>Every number below is in <code>src/config.py</code> and can be changed; the report updates on the next run.</p>
<div class="table-wrap"><table><thead><tr><th>Assumption</th><th class="num">Low</th><th class="num">Central</th>
<th class="num">High</th><th>Source</th></tr></thead><tbody>{a_rows}</tbody></table></div>
<div class="table-wrap"><table><thead><tr><th>Network item</th><th class="num">Capacity (MVA)</th><th class="num">Cost (€m)</th></tr>
</thead><tbody>{net_rows}</tbody></table></div>
<p class="muted">Published cost examples: about €6m for a new 38 kV station (Ballymahon, 2018) and about €70m each
for the new Bracklone and planned West Portlaoise 110 kV stations. Upgrade costs and station sizes are assumptions.</p>

<h2>10. Data checks</h2>
<p>Result: <b>{qc['summary']}</b>.</p>
<div class="table-wrap"><table><thead><tr><th>Status</th><th>Check</th><th>Detail</th></tr></thead><tbody>{qc_rows}</tbody></table></div>

<h2>Limitations and methods</h2>
<ul>
<li>Consumption is metered energy by county; the winter peak is estimated with a load factor, not measured.
Business and industry growth, new large loads, and EV charging behaviour are the least certain inputs.</li>
<li>Station assignment uses straight-line distance to the nearest station, a simplification of real network
topology; ESB Networks' spare-capacity figures are indicative and can be limited by upstream circuits.</li>
<li>Costs cover stations only and use public examples and stated assumptions, not ESB Networks unit costs.</li>
<li>Methods: Python (pandas, NumPy, matplotlib). Bottom-up scenario model by electoral division with S-curve
technology uptake; nearest-station spatial assignment; {len(plan['mc']):,}-run Monte Carlo over demand drivers,
station sizes and unit costs (triangular distributions); one-at-a-time sensitivity; automatic reading of ESB Networks
workbooks with structure detection and Irish Transverse Mercator conversion. Code: <a href="{REPO}">GitHub</a>.</li>
</ul>
<footer>Data: CSO (CC BY 4.0); ESB Networks (<a href="{ESBN_PAGE}">DNDP</a>). Analysis and any errors are the
author's own.</footer>
</main></body></html>
"""
