# Cork 2040 Substation Dashboard in Tableau Public (about 1–2 hours)

## 0. Install (10 min)
1. Go to **public.tableau.com**, click **Sign up**, and create a free profile.
2. Download **Tableau Public** (the free desktop app; it works on Mac) and sign in.

## 1. Connect the data (5 min)
1. Open Tableau Public → **Connect → To a File → Text file** → pick `dashboard/cork_substations_2040.csv`.
2. At the bottom left, click **Sheet 1**.
3. For the second file, go to **Data → New Data Source → Text file** → pick `dashboard/cork_peak_scenarios.csv`.

## 2. Sheet 1: "Substation map" (20 min)
1. Data source: `cork_substations_2040`.
2. Drag **Longitude** to Columns and **Latitude** to Rows. If Tableau doesn't make a map by itself, right-click each one → **Geographic Role** → Longitude / Latitude.
3. Drag **Station** to **Detail** on the Marks card.
4. Drag **Verdict** to **Colour**. Set the colours to green = Enough spare capacity, amber = Upgrade needed, red = New station(s) needed.
5. Drag **Shortfall by 2040 (MW)** to **Size**.
6. Drag **Spare capacity today (MW)**, **Extra load by 2040 (MW)** and **Voltage** to **Tooltip**.
7. Rename the sheet (double-click the tab): `Substation map`.

## 3. Sheet 2: "Biggest shortfalls" (10 min)
1. New sheet. Drag **Station** to Rows and **Shortfall by 2040 (MW)** to Columns.
2. Sort descending (the sort icon on the toolbar). Drag **Station** to **Filters** → **Top** tab → **By field**: Top 15 by Shortfall.
3. Drag **Verdict** to **Colour**, using the same colours as the map.

## 4. Sheet 3: "Peak to 2040" (15 min)
1. Switch the data source to `cork_peak_scenarios`.
2. Drag **Year** to Columns (right-click → **Dimension**, then **Continuous**).
3. Drag **Total peak (MW)** to Rows → right-click → **Measure → Average**. Each year repeats for every driver, so Average gives the true value.
4. Drag **Scenario** to **Colour**.
5. Drag **Scenario** to **Filters** too → right-click it → **Show Filter**.

## 5. Sheet 4: "What drives the growth" (10 min)
1. Drag **Driver** to Rows and **Extra peak (MW)** to Columns.
2. Drag **Year** to Filters → keep only **2040**. Drag **Scenario** to Filters → keep **Central**.
3. Drag **Driver** to Colour and sort descending.

## 6. KPI cards (15 min)
Make 4 small sheets, each with one big number: **Text** on the Marks card, font size 28 or more, written as text with **Worksheet → Show Title** off.
- `+91%` winter peak by 2040 (581 → about 1,110 MW)
- `45 of 65` substations short
- `€194–346m` station investment
- `~€68m` saved by smart EV charging and demand response

(The easiest way: create a sheet, drag nothing in, double-click the **Text** mark and type the number and label.)

## 7. Put it together (15 min)
1. Click **New Dashboard** (bottom bar). Size: **Automatic**.
2. Title: `Cork 2040: power, substations and budget`.
3. KPI cards along the top, the **Substation map** big on the left, **Peak to 2040** and **Biggest shortfalls** on the right, and **What drives the growth** underneath.
4. Click the map → the funnel icon (**Use as Filter**). Clicking a station then highlights it in the other charts.
5. Add a small text box at the bottom:
   `Independent analysis by Mankirat Singh using public CSO, Census 2022 and ESB Networks data. Not an ESB Networks publication. Full report: bymankirat.github.io/cork-2040-grid`

## 8. Publish (5 min)
**File → Save to Tableau Public**. Name: `Cork 2040 Substation Dashboard`. Copy the link it gives you.

## 9. Add the link everywhere
- Send me the link. I'll add it to your CV, portfolio and the Cork report.
- LinkedIn Featured → **Add a link**.
- GitHub README of `cork-2040-grid`, under "Live report".

## Files in this pack
- `cork_substations_2040.csv`: 65 demand substations with location, spare capacity, extra load by 2040, shortfall and verdict (central case)
- `cork_peak_scenarios.csv`: winter peak 2025–2040 for 3 scenarios, split by driver (homes, business, heat pumps, EVs, large loads)
