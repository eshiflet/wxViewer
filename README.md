# wxViewer

A browser-based analytics app for personal weather station data. No server required — all data stays on your device.

**Live app:** [ericshiflet.com/wxViewer](https://www.ericshiflet.com/wxViewer/)

---

## What it does

wxViewer loads CSV files exported from an Ambient Weather station (or any compatible format) and gives you interactive charts and analysis across your full data history.

### Main chart

- Plot any combination of your station's data series over time — temperature, humidity, pressure, wind, rain, UV index, solar radiation, and more
- Selectable date range via date pickers, quick-range buttons (7d / 30d / 90d / All), or by drag-selecting directly on the chart
- Overlay weather model **forecasts** for your location: ECMWF IFS, ECMWF AIFS, HRRR, and NOAA AIGFS — fetched live from the [Open-Meteo API](https://open-meteo.com/)
- **Anomaly detection** — highlights statistically unusual readings using Tukey IQR fences
- Min / avg / max stats bar for the selected time window
- Export the current filtered view to CSV

### Analysis panel

Click **Analyze** to open a panel with four tabs, each computed from the currently selected date range:

**🌬 Wind Rose**
Polar histogram of wind direction and speed across 16 compass points and 4 speed bands.

**⏱ Daily Pattern**
Average values by hour of day, grouped by calendar month — shows diurnal cycles for temperature, humidity, and other series.

**🏆 Records**
All-time high and low for every data series, with the date and time each record occurred.

**🏠 Thermal Analysis**
Models your home as a thermal circuit and quantifies how indoor temperatures respond to outdoor conditions:

- **Lag correlation** — cross-correlation at 0–24h lags reveals your home's thermal time constant (how many hours it takes indoor temp to follow outdoor changes)
- **Thermal phase scatter** — plots lagged outdoor temp vs indoor temp, colored by HVAC state; the slope of the regression line is your thermal coupling coefficient
- **HVAC residual time series** — deviations from the passive thermal model identify when heating or cooling was running
- **Monthly HVAC activity** — bar chart of estimated heating and cooling hours per month

The thermal model is trained on **passive periods** (when neither heat nor AC is running) to learn the house's true natural thermal response. You can configure your heating and cooling seasons in the **⚙ Season Configuration** section so the algorithm uses labeled ground-truth data instead of the built-in RANSAC estimator.

---

## Loading your data

### 📂 Open Folder *(recommended)*
Click **Open Folder** and select the directory containing your CSV files. The app reads all `.csv` files in that folder and remembers the selection — on future visits it reloads automatically (or with one click if permission needs re-granting). Requires Chrome or Edge; Safari 15.2+.

### Load CSV files
Standard file picker — select one or more CSV files manually. Works in all browsers.

---

## Running locally

If you want to use the **Open Folder** auto-load on a local copy, serve the directory with the included Python server:

```bash
cd /path/to/wxViewer
python3 server.py
```

Then open [http://localhost:5201](http://localhost:5201).

---

## Data format

CSV files must have a header row. The first column should be a date/time field. wxViewer auto-detects the column names and units from the headers — it works out of the box with Ambient Weather Network CSV exports.

---

## HVAC monitoring

The Thermal Analysis panel currently *infers* when heating and cooling ran, from
deviations against the passive thermal model. Real HVAC on/off state would be better
ground truth — it would let the model train on labeled data rather than a RANSAC
estimate.

### Amazon Smart Thermostat — not possible

The `alexa-poller/` directory holds an abandoned attempt to read HVAC state from an
Amazon Smart Thermostat via the Alexa API. **It does not work and cannot be made to
work.**

The HVAC running-state properties (`primaryHeaterOperation`, `coolerOperation`) belong to
an interface that device manufacturers implement to report *to* Alexa for its energy
dashboard. There is no direction in which a consumer reads them back out, and Amazon
publishes no consumer API for thermostat state at all. The Home Assistant community hit
the same wall — there is no HA integration for this thermostat, for this reason.

The code is kept only as a record. See [`alexa-poller/SETUP.md`](alexa-poller/SETUP.md)
for the full findings.

### CT clamps — the working alternative

Measuring the HVAC circuits directly sidesteps the vendor entirely: a current transformer
clamp around the condenser and air handler conductors reports actual draw, which gives
unambiguous on/off state and, from the magnitude, which stage is running.

Nothing is wired up yet. Note that connecting such a feed will need a change to the CSV
loader: it currently concatenates rows from every file and takes its column set from the
first file only, so a second CSV of HVAC readings would need to be joined on timestamp
rather than appended.

---

## Tech

- [Plotly.js](https://plotly.com/javascript/) — charting
- [Open-Meteo](https://open-meteo.com/) — free weather forecast API
- [File System Access API](https://developer.mozilla.org/en-US/docs/Web/API/File_System_Access_API) — local folder access
- No frameworks, no build step, no data leaves your browser
