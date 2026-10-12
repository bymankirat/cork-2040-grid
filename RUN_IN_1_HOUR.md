# Finish this project in 1 hour

## 1. Run it (10 min, mostly downloading)

```
cd /Users/mankiratsingh/MSc_Thesis/THESIS_PAPER_DATA_PDF/03_Gut_Microbiota_Dysbiosis
unzip -o ~/Downloads/cork-2040-grid.zip
cd cork-2040-grid
python run_pipeline.py
open docs/index.html
```

It downloads 4 CSO tables, the Cork boundaries and two large ESB Networks Excel files.

**Paste these to Claude:**
1. The whole RESULTS block.
2. The first ~60 lines of the workbook layout:
   ```
   head -60 reports/esbn_workbook_structure.txt
   tail -15 reports/esbn_workbook_structure.txt
   ```

The ESB Networks workbooks' exact layout couldn't be seen in advance, so the reader detects it automatically. The
structure file lets Claude confirm it read them correctly or adjust it in one step.

**If the ESB Networks download fails:** open
https://www.esbnetworks.ie/services/tools-maps/distribution-network-development-plan in Chrome. Download
"Demand Capacity Headroom Report 2025". From the heatmap page, download "Customer heatmap download".
Put both files in `data/raw/` with their original names, then run again.

## 2. GitHub (15 min)

1. On github.com, click **+ → New repository**. Name it `cork-2040-grid`, make it **Public**, no README.
2. Click **uploading an existing file**. In **Chrome**, drag in `docs`, `reports`, `src`, `README.md`,
   `requirements.txt`, `run_pipeline.py` and `RUN_IN_1_HOUR.md`. Do **not** upload `data`.
3. Click **Commit**. Then go to **Settings → Pages**, choose **main** and **/docs**, and click **Save**.

## 3. Interview talking points (ESB, ESB Networks, EirGrid, energy consultancies)

- **Why peak, not energy?** Substations are sized for the worst winter evening, not the yearly total.
  I converted metered GWh to a peak with a load factor and added each new load at its *after-diversity* peak.
- **Why bottom-up by electoral division?** Growth isn't uniform. Census data shows where oil- and gas-heated
  homes are (future heat pumps) and where the cars are (future EVs), so I can see *which* station feels it.
- **Where do the numbers come from?**
  - Climate Action Plan targets for heat pumps and EVs.
  - The National Planning Framework for population.
  - UCC field-trial heat-pump peaks: 2.33 kW typical, 3.84 kW extreme cold.
  - ESB Networks' scenario assumptions: 85% smart charging by 2040, 11.2% peak reduction from demand response.
- **Why Monte Carlo?** No one knows 2040. Giving €X–Ym with a median is more honest, and more useful for a
  budget, than one number. The tornado chart shows which assumption to research first.
- **Upgrade before new build:** a shortfall is first met by upgrading the existing station (bigger
  transformers), and new stations are added only for what's left. It's cheaper and faster.
- **Flexibility = avoided capex:** smart charging and demand response cut the peak, so fewer stations are needed.
  This links directly to ESB Networks' flexibility strategy and the regulator's PR6 incentives.
- **Cross-check:** my central case is compared against ESB Networks' own four scenarios from their
  workbook. Explaining *why* they differ (uptake speed, planned reinforcements) is the analyst's job.
- **Limitations I'd fix with internal data:**
  - real network topology instead of nearest station;
  - real unit costs;
  - feeder and transformer loading;
  - 38 kV stations fed from 110 kV (the hierarchy).
- **Net Zero by 2040:** ESB's own target year. The model shows what that path means for one county's grid.
