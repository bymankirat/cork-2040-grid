# Cork 2040: How Much Power, How Many Substations, What Budget?

A network-planning model for **Co. Cork to 2040**, the year of ESB's Net Zero strategy. It estimates how much
electricity Cork will need, maps where the new demand lands, tests it against every ESB Networks 110 kV and 38 kV
substation in Cork, and sizes the stations and budget needed, with and without flexibility.

**[Read the report →](https://bymankirat.github.io/cork-2040-grid/)** ·
**[Interactive Cork capacity heatmap →](https://bymankirat.github.io/cork-2040-grid/map.html)**

![Map of new demand and substations](reports/figures/04_map.png)

> Independent analysis of public data. Not an ESB or ESB Networks publication.

## Questions answered

1. **How much power will Cork need?** A bottom-up model built from CSO metered consumption and Census 2022 data for
   every Cork electoral division (heating fuel, cars, households). It adds housing growth, business growth,
   heat pumps, electric cars and new large loads, minus efficiency, year by year in three scenarios.
2. **Where?** Each electoral division's extra load is mapped and assigned to its nearest substation.
3. **Which substations run out, and when?** The new load is compared with each station's spare capacity, read
   automatically from ESB Networks' own workbooks. The result is cross-checked against ESB Networks' four official
   scenarios.
4. **How many stations, and what budget?** Stations needing an upgrade or new stations, costed with a 5,000-run
   Monte Carlo over demand, station sizes and unit costs, so results are ranges, not single numbers.
5. **How to accommodate it?** It shows how much smart EV charging, heat-pump flexibility and demand response save,
   and which drivers matter most (sensitivity).

## Run it

```bash
pip install -r requirements.txt
python run_pipeline.py            # downloads CSO and ESB Networks data (first run a few minutes)
python run_pipeline.py --demo     # simulated data, for testing only
python run_pipeline.py --refresh  # re-download when new data is published
```

Every assumption, with its source, is in `src/config.py`. Change one, re-run, and the report updates.

## Structure

```
run_pipeline.py     data -> checks -> 2040 scenarios -> Monte Carlo -> substations & budget -> charts -> report
src/config.py       data sources and every planning assumption with its source
src/data.py         CSO consumption and Census tables, ED boundaries, ESB Networks workbooks
src/esbn.py         reads ESB Networks workbooks of unknown layout; Irish Transverse Mercator -> lat/lon
src/scenarios.py    bottom-up demand model by electoral division, S-curve uptake, Monte Carlo, sensitivity
src/planning.py     nearest-station assignment, upgrade/new-station decisions, costs, ESB Networks cross-check
src/quality.py      data checks
src/charts.py       figures (incl. Cork map)
src/report.py       report page (docs/index.html)
src/webmap.py       interactive heatmap (docs/map.html): year slider, ESB Networks scenarios, 2040 verdicts
```

Data: CSO (CC BY 4.0) · ESB Networks
[Distribution Network Development Plan](https://www.esbnetworks.ie/services/tools-maps/distribution-network-development-plan).
Mankirat Singh · [Portfolio](https://bymankirat.github.io/myportfolio/) ·
[LinkedIn](https://linkedin.com/in/mankirat-singh-694440177)
