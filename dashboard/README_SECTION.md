## Dashboard

**[Open the Tableau dashboard →](PASTE_YOUR_TABLEAU_PUBLIC_LINK_HERE)**

A Tableau Public dashboard built on two tidy tables made by `make_dashboard_data.py`:

- `dashboard/cork_substations_2040.csv`: the 65 demand substations with location, spare capacity today, extra load by 2040, shortfall and verdict (central case)
- `dashboard/cork_peak_scenarios.csv`: Cork's winter peak 2025–2040 in three scenarios, split by driver

```bash
python run_pipeline.py          # builds reports/
python make_dashboard_data.py   # builds dashboard/
```
