"""Interactive Cork capacity heatmap (docs/map.html): every Cork substation coloured by spare capacity, with a
year slider and scenario picker (ESB Networks' own forecasts), this project's 2040 verdicts, and the extra 2040
load per electoral division. One fully self-contained page: Leaflet is embedded (src/vendor, BSD-2 licence) and
the base map is drawn from Cork's own electoral-division boundaries, so it works offline and needs no map
service or API key."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from config import DOCS_DIR


def _r(x, n=2):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


TOWNS = [["Cork City", 51.8985, -8.4756, 1], ["Mallow", 52.1345, -8.6450, 0], ["Fermoy", 52.1386, -8.2756, 0],
         ["Midleton", 51.9153, -8.1750, 0], ["Youghal", 51.9536, -7.8506, 0], ["Bandon", 51.7460, -8.7425, 0],
         ["Clonakilty", 51.6231, -8.8706, 0], ["Skibbereen", 51.5500, -9.2667, 0], ["Bantry", 51.6800, -9.4520, 0],
         ["Macroom", 51.9046, -8.9568, 0], ["Kinsale", 51.7059, -8.5222, 0], ["Cobh", 51.8503, -8.2967, 0],
         ["Mitchelstown", 52.2656, -8.2683, 0], ["Kanturk", 52.1719, -8.9050, 0], ["Charleville", 52.3556, -8.6833, 0]]


def build(cork: pd.DataFrame, forecast: pd.DataFrame | None, plan: dict, scen: dict, geojson: Path | None,
          demo: bool) -> str | None:
    if cork is None or not len(cork) or cork["lat"].notna().sum() == 0:
        return None
    st_plan = plan.get("stations", {}).get(("central", False))
    ex = plan.get("exhaust_year", pd.Series(dtype=float))
    fc = {}
    years, scenarios = [], []
    if forecast is not None and len(forecast):
        h = forecast[forecast["metric"] == "headroom"]
        years = sorted(int(y) for y in h["year"].unique())
        scenarios = sorted(h["scenario"].unique())
        g = h.groupby(["key", "scenario", "year"])["value"].sum()
        for (k, s, y), v in g.items():
            fc.setdefault(k, {}).setdefault(s, {})[int(y)] = _r(v, 1)
    stations = []
    for k, r in cork.dropna(subset=["lat", "lon"]).iterrows():
        kv_ok = pd.notna(r.get("kv")) and r["kv"] in (38, 110)
        if not (kv_ok or k in fc):  # leave out small MV/LV substations from the heatmap file
            continue
        if pd.isna(r.get("kv")) and k not in fc:   # neither a known 110/38 kV station nor in ESB's forecast
            continue
        if not (51.3 <= r["lat"] <= 52.5 and -10.4 <= r["lon"] <= -7.5):  # keep the view on Cork
            continue
        p = st_plan.loc[k] if st_plan is not None and k in st_plan.index else None
        stations.append({
            "n": str(r["station"]).title(), "kv": None if pd.isna(r.get("kv")) else int(r["kv"]),
            "lat": _r(r["lat"], 5), "lon": _r(r["lon"], 5), "now": _r(r.get("headroom_now"), 1),
            "fc": fc.get(k, {}), "extra": _r(p["extra_mw"], 1) if p is not None else None,
            "short": _r(p["deficit_mw"], 1) if p is not None else None,
            "act": p["action"] if p is not None else None,
            "full": int(ex[k]) if k in ex.index and pd.notna(ex[k]) else None,
            "gen": bool(fc) and k not in fc,
        })
    eds = None
    if geojson is not None:
        gj = json.loads(Path(geojson).read_text())
        extra = scen["central"]["ed2040"]["extra_mw"]
        feats = []
        for f in gj["features"]:
            gid = f["properties"].get("ED_GUID")
            if gid in extra.index:
                f["properties"] = {"n": str(f["properties"].get("ED_ENGLISH", "")).title(), "x": _r(extra[gid], 2)}
                feats.append(f)
        eds = {"type": "FeatureCollection", "features": feats}
    payload = {"stations": stations, "years": years, "scenarios": scenarios, "eds": eds, "demo": demo,
               "towns": TOWNS}
    vendor = Path(__file__).resolve().parent / "vendor"
    html = (PAGE.replace("/*LEAFLET_CSS*/", (vendor / "leaflet.css").read_text(encoding="utf-8"))
            .replace("/*LEAFLET_JS*/", (vendor / "leaflet.js").read_text(encoding="utf-8"))
            .replace("/*DATA*/", json.dumps(payload, separators=(",", ":"))))
    DOCS_DIR.mkdir(exist_ok=True)
    out = DOCS_DIR / "map.html"
    out.write_text(html, encoding="utf-8")
    return str(out)


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cork Capacity Heatmap</title>
<style>/*LEAFLET_CSS*/</style>
<style>
:root{--bg:#f6f6f3;--panel:#fcfcfb;--card:#fff;--ink:#0b0b0b;--ink-2:#52514e;--ink-3:#8a8984;--line:#e4e3df;--accent:#2a78d6;
--land:#ecebe6;--landline:#ffffff;--sea:#dfe9f3;--green:#1baf7a;--amber:#e0a100;--red:#e34948;--orange:#eb6834;--grey:#a3a29d}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141413;--panel:#1a1a19;--card:#232322;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e87;
--line:#3a3a38;--accent:#3987e5;--land:#2a2a28;--landline:#1a1a19;--sea:#17202b}}
:root[data-theme="dark"]{--bg:#141413;--panel:#1a1a19;--card:#232322;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e87;--line:#3a3a38;--accent:#3987e5;
--land:#2a2a28;--landline:#1a1a19;--sea:#17202b}
*{box-sizing:border-box}html,body{margin:0;height:100%;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.app{display:grid;grid-template-columns:340px 1fr;height:100%}
aside{background:var(--panel);border-right:1px solid var(--line);padding:18px 18px 12px;overflow-y:auto;display:flex;flex-direction:column;gap:14px}
aside>*{flex-shrink:0}
.kicker{color:var(--accent);font-weight:700;letter-spacing:.05em;text-transform:uppercase;font-size:11px}
h1{font-size:19px;line-height:1.25;margin:2px 0 4px}.muted{color:var(--ink-2)}.small{font-size:12px}
.seg{display:grid;grid-template-columns:1fr 1fr;background:var(--bg);border:1px solid var(--line);border-radius:9px;padding:3px}
.seg button{border:0;background:transparent;color:var(--ink-2);padding:7px 6px;border-radius:7px;font:inherit;font-weight:600;cursor:pointer}
.seg button.on{background:var(--card);color:var(--ink);box-shadow:0 1px 2px rgba(0,0,0,.12)}
.field{display:flex;flex-direction:column;gap:6px}.field label{font-size:12px;font-weight:600;color:var(--ink-2)}
select{background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:7px 8px;font:inherit}
.yearrow{display:flex;align-items:center;gap:10px}.yearrow input{flex:1;accent-color:var(--accent)}
.yearrow b{font-size:18px;font-variant-numeric:tabular-nums;min-width:44px;text-align:right}
.play{width:34px;height:34px;border-radius:50%;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer;font-size:13px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.stat .big{font-size:30px;font-weight:750;line-height:1.1;font-variant-numeric:tabular-nums}
.bar{display:flex;height:8px;border-radius:5px;overflow:hidden;margin-top:9px;background:var(--line)}
.bar span{display:block;height:100%}
.legend div{display:flex;align-items:center;gap:8px;margin:3px 0}.dot{width:12px;height:12px;border-radius:50%;border:1.5px solid rgba(0,0,0,.55);flex:none}
.ramp{display:flex;height:10px;border-radius:3px;overflow:hidden;margin:6px 0 2px}.ramp span{flex:1}
.check{display:flex;align-items:center;gap:8px;font-weight:600}
#detail{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;min-height:64px}
#detail h3{margin:0 0 6px;font-size:15px}#detail table{width:100%;border-collapse:collapse;font-size:12.5px}
#detail td{padding:3px 0;border-bottom:1px solid var(--line)}#detail td:last-child{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
.pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11.5px;font-weight:700;color:#fff}
.banner{background:#fff4e5;color:#7a3d00;padding:8px 10px;border-radius:8px;font-weight:600;font-size:12px}
a{color:var(--accent)}button.reset{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:8px;padding:6px 10px;font:inherit;cursor:pointer}
#map{height:100%;background:var(--sea)}
.mapwrap{position:relative;height:100%}
.back{position:absolute;top:12px;right:12px;z-index:1000;background:var(--card);color:var(--ink);border:1px solid var(--line);
 padding:8px 12px;border-radius:999px;text-decoration:none;font-weight:700;box-shadow:0 2px 8px rgba(0,0,0,.18)}
.back:hover{border-color:var(--accent);color:var(--accent)}
.tabs{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.tabs a{text-align:center;padding:7px 8px;border-radius:999px;border:1px solid var(--line);text-decoration:none;color:var(--ink);font-weight:600;font-size:12.5px}
.tabs a.on{background:var(--accent);border-color:var(--accent);color:#fff}
.leaflet-container{font:inherit;background:var(--sea)}
.town{background:transparent;border:0;box-shadow:none;color:var(--ink-2);font-weight:600;font-size:11px;text-shadow:0 0 3px var(--land),0 0 3px var(--land)}
.town.city{font-size:13px;color:var(--ink)}
.leaflet-tooltip.town:before{display:none}
.leaflet-popup-content{font-size:12.5px;line-height:1.45}
footer{margin-top:auto;font-size:11px;color:var(--ink-3)}
@media (max-width:820px){.app{grid-template-columns:1fr;grid-template-rows:auto 62vh;height:auto}aside{border-right:0;border-bottom:1px solid var(--line)}#map,.mapwrap{height:62vh}}
</style></head><body>
<div class="app">
<aside>
 <div class="tabs"><a href="index.html">← Report</a><a class="on" href="map.html">Interactive map</a></div>
 <div id="banner"></div>
 <div><div class="kicker">Cork 2040 · grid capacity</div><h1>Cork Capacity Heatmap</h1>
 <div class="muted small">Every Cork 110 kV and 38 kV substation, coloured by spare capacity for new demand. Click a station for details.</div></div>
 <div class="seg" id="seg"><button data-v="esbn" class="on">ESB Networks forecast</button><button data-v="plan">2040 plan</button></div>
 <div class="field" id="scenF"><label for="scen">Scenario</label><select id="scen"></select></div>
 <div class="field" id="yearF"><label for="year">Year</label><div class="yearrow"><button class="play" id="play" title="Play">▶</button><input id="year" type="range"><b id="yv"></b></div></div>
 <div class="stat"><div class="big" id="big">–</div><div class="muted small" id="bigl"></div><div class="bar" id="bar"></div></div>
 <div class="legend small" id="legend"></div>
 <label class="check small"><input id="edl" type="checkbox"> Shade areas by extra 2040 load</label>
 <div id="ramp" class="small" style="display:none"><div class="ramp" id="rampbar"></div><div class="muted" style="display:flex;justify-content:space-between"><span>less</span><span>more extra MW per km²</span></div></div>
 <div id="detail"><span class="muted small">Click a station on the map.</span></div>
 <div style="display:flex;gap:8px;align-items:center"><button class="reset" id="reset">Reset view</button><a class="small" href="index.html">Full report →</a></div>
 <footer>Data: ESB Networks Demand Capacity Headroom Report 2025 &amp; customer heatmap; CSO Census 2022 boundaries.
 Extra 2040 load from this project's model. Independent analysis by Mankirat Singh, not an ESB Networks product.
 Map: Leaflet; boundaries © CSO / Tailte Éireann.</footer>
</aside>
<div class="mapwrap"><div id="map"></div><a class="back" href="index.html">← Back to full report</a></div>
</div>
<script>/*LEAFLET_JS*/</script>
<script>
const D=/*DATA*/;
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const COL={green:css('--green'),amber:css('--amber'),red:css('--red'),orange:css('--orange'),grey:css('--grey')};
const ACT={none:['Enough spare capacity',COL.green],upgrade:['Upgrade needed',COL.amber],'new station':['New station(s) needed',COL.orange]};
if(D.demo)document.getElementById('banner').innerHTML='<div class="banner">DEMO DATA: simulated, not real.</div>';
const map=L.map('map',{zoomSnap:0.25,zoomControl:true,attributionControl:true,preferCanvas:false});
map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
// base map: Cork's electoral divisions
const RAMP=['#eaf2fc','#c3dbf6','#8fbbee','#4f93e0','#2a78d6','#174f96'];
let breaks=[];let shade=false;
function edStyle(f){const x=f.properties.x;let fill=css('--land'),op=1;
  if(shade&&x!=null){let i=0;while(i<breaks.length&&x>breaks[i])i++;fill=RAMP[i];op=.85;}
  return{fillColor:fill,fillOpacity:op,color:css('--landline'),weight:.6};}
let base=null;
if(D.eds&&D.eds.features.length){
  const dens=D.eds.features.map(f=>{const b=L.geoJSON(f).getBounds();const km2=Math.max(1,(b.getEast()-b.getWest())*69*(b.getNorth()-b.getSouth())*111);f.properties.x=f.properties.x==null?null:f.properties.x/km2;return f.properties.x;}).filter(v=>v!=null).sort((a,b)=>a-b);
  const q=p=>dens[Math.min(dens.length-1,Math.floor(p*dens.length))];breaks=[q(.2),q(.4),q(.6),q(.8),q(.95)];
  base=L.geoJSON(D.eds,{style:edStyle,onEachFeature:(f,l)=>l.bindTooltip(f.properties.n,{sticky:true,direction:'top',opacity:.9})}).addTo(map);
  document.getElementById('rampbar').innerHTML=RAMP.map(c=>`<span style="background:${c}"></span>`).join('');
}
D.towns.forEach(t=>L.tooltip({permanent:true,direction:'center',className:'town'+(t[3]?' city':''),interactive:false}).setLatLng([t[1],t[2]]).setContent(t[0]).addTo(map));
// controls
const scenSel=document.getElementById('scen'),yr=document.getElementById('year'),yv=document.getElementById('yv');
let mode=D.years.length?'esbn':'plan';
D.scenarios.forEach(s=>{const o=document.createElement('option');o.value=s;o.textContent=s;scenSel.appendChild(o);});
if(D.scenarios.includes('Best View'))scenSel.value='Best View';
if(D.years.length){yr.min=0;yr.max=D.years.length-1;yr.step=1;yr.value=Math.max(0,D.years.indexOf(2030));}
else document.querySelector('#seg button[data-v=esbn]').disabled=true;
document.querySelectorAll('#seg button').forEach(b=>b.onclick=()=>{if(b.disabled)return;mode=b.dataset.v;stopPlay();draw();});
const layer=L.layerGroup().addTo(map);let selected=null;
function headroom(s){const y=D.years[+yr.value];const v=(s.fc[scenSel.value]||{})[y];return v===undefined?null:v;}
function colour(s){if(s.gen)return 'transparent';if(mode==='plan')return s.act?ACT[s.act][1]:COL.grey;const v=headroom(s);
  return v==null?COL.grey:v<=0.01?COL.red:v<5?COL.amber:COL.green;}
function fmt(v,u){return v==null?'–':`${v} ${u}`;}
function detail(s){selected=s;const v=headroom(s),y=D.years[+yr.value];
  const verdict=s.gen?`<span class="pill" style="background:${COL.grey}">Not a demand station</span><div class="muted small" style="margin-top:4px">Not on ESB Networks' demand list: usually a wind farm, hydro, transmission or dedicated customer station.</div>`
    :s.act?`<span class="pill" style="background:${ACT[s.act][1]}">${ACT[s.act][0]}</span>`:'';
  document.getElementById('detail').innerHTML=`<h3>${s.n}${s.kv?` <span class="muted small">${s.kv} kV</span>`:''}</h3>${verdict}
  <table><tr><td>Spare capacity today</td><td>${fmt(s.now,'MW')}</td></tr>
  ${D.years.length?`<tr><td>ESB Networks ${scenSel.value}, ${y}</td><td>${v==null?'–':v<=0.01?'none left':v+' MVA'}</td></tr>`:''}
  <tr><td>Extra load by 2040 (central)</td><td>${fmt(s.extra,'MW')}</td></tr>
  <tr><td>Shortfall in 2040</td><td>${fmt(s.short,'MW')}</td></tr>
  <tr><td>Full by</td><td>${s.full||'–'}</td></tr></table>`;}
function draw(){
  document.querySelectorAll('#seg button').forEach(b=>b.classList.toggle('on',b.dataset.v===mode));
  document.getElementById('scenF').style.display=mode==='esbn'?'':'none';document.getElementById('yearF').style.display=mode==='esbn'?'':'none';
  const y=D.years[+yr.value];yv.textContent=y||'';layer.clearLayers();
  const counts={};D.stations.forEach(s=>{const c=colour(s);counts[c]=(counts[c]||0)+1;
    const m=s.gen?L.circleMarker([s.lat,s.lon],{radius:4,color:COL.grey,weight:1.5,fillOpacity:0,dashArray:'2 2'})
      :L.circleMarker([s.lat,s.lon],{radius:s.kv===110?8:5.5,color:'rgba(0,0,0,.6)',weight:1.2,fillColor:c,fillOpacity:.95});
    m.bindTooltip(s.n,{direction:'top',offset:[0,-6]});m.on('click',()=>{detail(s);});m.addTo(layer);});
  const n=D.stations.filter(s=>!s.gen&&colour(s)!==COL.grey).length;
  let order,labels;
  if(mode==='plan'){order=[COL.orange,COL.amber,COL.green];labels=['New station(s) needed','Upgrade needed','Enough spare capacity'];
    document.getElementById('big').textContent=`${counts[COL.orange]||0} of ${n}`;document.getElementById('bigl').textContent='stations need a new station nearby by 2040 (central case)';}
  else{order=[COL.red,COL.amber,COL.green];labels=['No firm headroom left','Under 5 MVA left','5 MVA or more'];
    document.getElementById('big').textContent=`${counts[COL.red]||0} of ${n}`;document.getElementById('bigl').textContent=`stations full in ${y}, ${scenSel.value} scenario`;}
  document.getElementById('bar').innerHTML=order.map(c=>`<span style="background:${c};width:${100*(counts[c]||0)/Math.max(n,1)}%"></span>`).join('');
  document.getElementById('legend').innerHTML=order.map((c,i)=>`<div><span class="dot" style="background:${c}"></span>${labels[i]}</div>`).join('')+
    `<div><span class="dot" style="background:${COL.grey}"></span>No data for this view</div>`+
    `<div><span class="dot" style="background:transparent;border:1.5px dashed ${COL.grey}"></span>Not a demand station (wind farm, hydro, dedicated site)</div>`+
    `<div class="muted">Large dots = 110 kV, small = 38 kV</div>`;
  if(selected)detail(selected);}
[scenSel,yr].forEach(e=>e.addEventListener('input',()=>{draw();}));
let timer=null;const playB=document.getElementById('play');
function stopPlay(){if(timer){clearInterval(timer);timer=null;playB.textContent='▶';}}
playB.onclick=()=>{if(timer){stopPlay();return;}if(+yr.value>=+yr.max)yr.value=0;playB.textContent='❚❚';
  timer=setInterval(()=>{if(+yr.value>=+yr.max){stopPlay();return;}yr.value=+yr.value+1;draw();},700);};
document.getElementById('edl').onchange=e=>{shade=e.target.checked;if(base)base.setStyle(edStyle);document.getElementById('ramp').style.display=shade?'':'none';};
// view locked to Cork
const CORK=L.latLngBounds([[51.42,-10.25],[52.40,-7.80]]);
let bounds=base?base.getBounds():L.latLngBounds(D.stations.map(s=>[s.lat,s.lon]));
if(!bounds.isValid()||bounds.getEast()-bounds.getWest()>3.5||bounds.getNorth()-bounds.getSouth()>2.2)bounds=CORK;
function fit(){map.invalidateSize();map.fitBounds(bounds,{padding:[16,16]});}
fit();map.setMaxBounds(bounds.pad(0.35));map.setMinZoom(Math.max(6,map.getZoom()-0.75));
document.getElementById('reset').onclick=fit;window.addEventListener('resize',()=>map.invalidateSize());
setTimeout(()=>{fit();map.setMinZoom(Math.max(6,map.getZoom()-0.75));},250);
draw();
</script></body></html>
"""
