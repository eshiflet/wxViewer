# wxViewer

A browser-based analytics app for personal weather station data. No server required — all data stays on your device.

**Live app:** [ericshiflet.com/wxViewer](https://www.ericshiflet.com/wxViewer/)

---

## What it does

wxViewer loads CSV files exported from an Ambient Weather station (or any compatible format) and gives you interactive charts and analysis across your full data history.

### Main chart

- Plot any combination of your station's data series over time — temperature, humidity, pressure, wind, rain, UV index, solar radiation, and more
- Selectable date range via date pickers, quick-range buttons (1d / 7d / 30d / 90d / All), or by drag-selecting directly on the chart
- **Anomaly detection** — highlights statistically unusual readings using Tukey IQR fences
- Min / avg / max stats bar for the selected time window
- Click any series' colour dot to recolour it; the choice is remembered in your browser
- **Ignore periods** — hide a stretch of readings you know are wrong, per series (a newly
  installed sensor still reaching equilibrium, or one that misbehaved for a while).
  Nothing is deleted: clear the bound and the readings come back
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

The thermal model is trained on **passive periods** (when neither heat nor AC is running) to
learn the house's true natural thermal response. The **⚙ Configuration** section at the top of
the tab controls two things:

- **Heating / cooling seasons** — whole-day ranges saying which mode the HVAC was in. These
  are labels about mode, not runtime; working out when it actually ran inside those days is
  the model's job. Given them, the regression trains on labelled ground truth instead of the
  built-in RANSAC estimator
- **Sensor roles** — which channels are indoor spaces and which one is the outdoor reference.
  Each indoor sensor is modelled separately. Unset, the app guesses from the column names

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

Files need not all share the same columns. Add a sensor to your station partway through and
only the exports after that date will carry it; wxViewer merges the column sets across every
file it loads, so the new channel appears as a series that simply starts when it starts.

---

## HVAC monitoring

The Thermal Analysis panel *infers* when heating and cooling ran, from deviations against
the passive thermal model. That works without any extra hardware, and labelling your
heating and cooling seasons sharpens it considerably.

For definitive events rather than inferred ones, put a temperature probe in the HVAC supply
trunk and let it come through as an ordinary channel in the CSV, then name it under
**HVAC Temperature Sensor** in the Configuration section.

Duct air sits at whatever surrounds the duct while the blower is off, is pulled down to the
cooling coil when the compressor runs, and is pushed well above room temperature by a
furnace. A cooling coil's return-to-supply split is normally 16–24°F and a gas furnace's
rise 40–70°F, and even damped by a probe sitting downstream in the trunk that is far outside
the couple of degrees the reading wanders while idle — so the trace says when the equipment
*ran* rather than when it probably ran.

wxViewer reads the idle level from the probe's own history rather than from a room sensor,
because what the duct equilibrates to might be a basement, a crawlspace or an attic.
Excursions either side of that level become cooling and heating periods, with brief lulls
inside a cycling period treated as one period: a compressor holding a setpoint switches on
and off every few minutes, and the house is in cooling throughout.

When a probe is assigned, those measured periods replace the heating and cooling ranges
above as the model's notion of which hours were passive — the regression then trains on
hours the equipment demonstrably wasn't running. Without one, the season ranges are used,
and without those, RANSAC guesses. The **HVAC interpretation** card reports run hours, cycle
counts, duty cycle and how far supply air departed from idle.

The probe is a temperature series like any other on the main chart, but it is not modelled
as a room: it gets no lag or coupling figures, because its temperature is set by the
equipment rather than by heat moving through the building envelope.

---

## Tech

- [Plotly.js](https://plotly.com/javascript/) — charting
- [File System Access API](https://developer.mozilla.org/en-US/docs/Web/API/File_System_Access_API) — local folder access
- No frameworks, no build step, no data leaves your browser
