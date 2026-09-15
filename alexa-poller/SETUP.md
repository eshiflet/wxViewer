# Alexa Thermostat Poller — Setup Guide

## What this does

Polls your Amazon Smart Thermostat every 5 minutes via the Alexa Smart Home API
and saves the data to `hvac_data.db` (SQLite). Captures:

- Current temperature (°F)
- Thermostat mode (HEAT / COOL / AUTO / OFF)
- Target setpoint(s)
- **Whether heating/cooling is actually running** (`primaryHeaterOperation`, `coolerOperation`, etc.)
- Adaptive recovery status (pre-heating / pre-cooling)

---

## Step 0 — Install dependencies

```bash
cd /Users/eric/Desktop/Weather/alexa-poller
pip install requests
```

---

## Step 1 — Create an Amazon Security Profile (one time, ~5 min)

1. Go to https://developer.amazon.com and sign in with **the same Amazon account
   your thermostat is registered to**.

2. Click **Developer Console → Login with Amazon**.

3. Click **Create a New Security Profile**.
   - Profile Name: `Thermostat Poller` (anything works)
   - Description: anything
   - Privacy URL: `https://example.com` (placeholder is fine)
   - Click **Save**

4. On your new profile, click **Show Client ID and Client Secret**.
   Copy both values — you'll paste them in the next step.

5. Click the **Web Settings** tab.
   - Under **Allowed Return URLs**, add: `http://localhost:9876/callback`
   - Click **Save**

---

## Step 2 — Authorize (one time, ~2 min)

```bash
python auth.py
```

This will:
- Ask for your Client ID and Client Secret (from Step 1)
- Open your browser to Amazon's login page
- You log in and click "Allow"
- Amazon redirects back, the script captures the token and saves `config.json`

`config.json` holds your refresh token — keep it private, don't commit it anywhere.

---

## Step 3 — Run the poller

```bash
# Run continuously, poll every 5 minutes (default)
python poll.py

# Poll every 1 minute
python poll.py --interval 1

# Single poll (for cron)
python poll.py --once
```

---

## Step 4 (optional) — Run as a background service with launchd

Create `/Library/LaunchAgents/com.weather.alexa-poller.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.weather.alexa-poller</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/eric/Desktop/Weather/alexa-poller/poll.py</string>
        <string>--once</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>  <!-- 300 seconds = 5 minutes -->
    <key>StandardOutPath</key>
    <string>/Users/eric/Desktop/Weather/alexa-poller/poller.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/eric/Desktop/Weather/alexa-poller/poller.log</string>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
```

Then load it:
```bash
launchctl load ~/Library/LaunchAgents/com.weather.alexa-poller.plist
```

---

## Querying the data

The SQLite database has one table: `thermostat_readings`.

```bash
sqlite3 hvac_data.db

# Latest reading
SELECT ts, thermostat_mode, current_temp_f, target_setpoint_f,
       primary_heater_op, cooler_op, fan_op
FROM thermostat_readings ORDER BY ts DESC LIMIT 1;

# All times heat was running today
SELECT ts, primary_heater_op, current_temp_f
FROM thermostat_readings
WHERE date(ts) = date('now')
  AND primary_heater_op != 'OFF'
  AND primary_heater_op IS NOT NULL;

# Export to CSV
.mode csv
.output hvac_export.csv
SELECT * FROM thermostat_readings;
```

---

## Notes on HVAC running state

The `primaryHeaterOperation` and `coolerOperation` columns will show:
- `OFF` — not running
- `STAGE_1` — running at low capacity
- `STAGE_2` / `STAGE_3` — higher stages (if your system supports multi-stage)

`auxiliaryHeaterOperation` will be `ON` or `OFF` (for heat pump aux/emergency heat).

**If these columns stay NULL**, the Amazon Smart Thermostat may not expose the
HVAC.Components interface to the consumer API — it's primarily designed for
manufacturers to push data TO Alexa. If that's the case, you can still infer
HVAC activity from `thermostatMode` + the gap between `current_temp_f` and
`target_setpoint_f` narrowing over time.
