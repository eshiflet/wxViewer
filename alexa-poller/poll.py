#!/usr/bin/env python3
"""
Alexa Smart Home thermostat poller.
Queries all available thermostat state every N minutes and saves to SQLite.
"""

import json
import sqlite3
import time
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path

import requests

# ── Config ─────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
DB_FILE    = BASE_DIR / "hvac_data.db"

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
# Alexa Smart Properties REST API (us-east-1)
ASP_BASE = "https://api.amazonalexa.com"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Database ────────────────────────────────────────────────────────────────
def init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS thermostat_readings (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            ts                      TEXT NOT NULL,          -- ISO-8601 UTC
            endpoint_id             TEXT,
            endpoint_name           TEXT,

            -- ThermostatController
            thermostat_mode         TEXT,                   -- HEAT/COOL/AUTO/ECO/OFF
            adaptive_recovery       TEXT,                   -- PREHEATING/PRECOOLING/INACTIVE
            target_setpoint_f       REAL,
            lower_setpoint_f        REAL,
            upper_setpoint_f        REAL,

            -- TemperatureSensor
            current_temp_f          REAL,

            -- HVAC.Components (actual running state)
            primary_heater_op       TEXT,                   -- OFF/STAGE_1/STAGE_2/STAGE_3
            auxiliary_heater_op     TEXT,                   -- OFF/ON
            cooler_op               TEXT,                   -- OFF/STAGE_1/STAGE_2/STAGE_3
            fan_op                  TEXT,                   -- OFF/STAGE_1/STAGE_2/STAGE_3

            -- Raw JSON for anything we didn't parse
            raw_json                TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON thermostat_readings(ts)")
    conn.commit()


# ── Auth ────────────────────────────────────────────────────────────────────
class TokenManager:
    def __init__(self, cfg: dict):
        self.client_id     = cfg["client_id"]
        self.client_secret = cfg["client_secret"]
        self.refresh_token = cfg["refresh_token"]
        self._access_token = None
        self._expires_at   = 0

    def access_token(self) -> str:
        if time.time() < self._expires_at - 60:
            return self._access_token
        log.info("Refreshing LWA access token…")
        r = requests.post(LWA_TOKEN_URL, data={
            "grant_type":    "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id":     self.client_id,
            "client_secret": self.client_secret,
        }, timeout=15)
        r.raise_for_status()
        data = r.json()
        self._access_token = data["access_token"]
        self._expires_at   = time.time() + data.get("expires_in", 3600)
        log.info("Token refreshed, valid for %ds", data.get("expires_in", 3600))
        return self._access_token

    def headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token()}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        }


# ── API calls ───────────────────────────────────────────────────────────────
def get_endpoints(tm: TokenManager) -> list[dict]:
    """Return all Alexa endpoints (devices)."""
    r = requests.get(f"{ASP_BASE}/v2/endpoints", headers=tm.headers(), timeout=15)
    r.raise_for_status()
    return r.json().get("endpoints", [])


def get_thermostat_features(tm: TokenManager, endpoint_id: str) -> dict:
    """GET all available features for a thermostat endpoint."""
    results = {}
    feature_paths = [
        "thermostat",           # ThermostatController (mode, setpoints, adaptiveRecovery)
        "temperature",          # TemperatureSensor
        "thermostatHvacComponents",  # HVAC.Components (running state)
    ]
    for feature in feature_paths:
        url = f"{ASP_BASE}/v2/endpoints/{endpoint_id}/features/{feature}"
        try:
            r = requests.get(url, headers=tm.headers(), timeout=15)
            if r.status_code == 200:
                results[feature] = r.json()
            elif r.status_code == 404:
                log.debug("Feature %s not available for %s", feature, endpoint_id)
            else:
                log.warning("Feature %s returned %d: %s", feature, r.status_code, r.text[:200])
        except requests.RequestException as e:
            log.warning("Error fetching feature %s: %s", feature, e)
    return results


def celsius_to_f(c) -> float | None:
    if c is None:
        return None
    try:
        return round(c * 9 / 5 + 32, 2)
    except (TypeError, ValueError):
        return None


def extract_temp_f(temp_obj: dict | None) -> float | None:
    if not temp_obj:
        return None
    value = temp_obj.get("value")
    scale = temp_obj.get("scale", "FAHRENHEIT").upper()
    if value is None:
        return None
    if scale == "CELSIUS":
        return celsius_to_f(value)
    return round(float(value), 2)


def parse_features(features: dict) -> dict:
    """Flatten nested feature responses into a flat row dict."""
    row = {}

    # ── ThermostatController ──────────────────────────────────────────────
    therm = features.get("thermostat", {})
    props = {p.get("name"): p.get("value") for p in therm.get("properties", [])}

    row["thermostat_mode"]   = props.get("thermostatMode")
    row["adaptive_recovery"] = props.get("adaptiveRecoveryStatus")
    row["target_setpoint_f"] = extract_temp_f(props.get("targetSetpoint"))
    row["lower_setpoint_f"]  = extract_temp_f(props.get("lowerSetpoint"))
    row["upper_setpoint_f"]  = extract_temp_f(props.get("upperSetpoint"))

    # ── TemperatureSensor ─────────────────────────────────────────────────
    temp = features.get("temperature", {})
    tprops = {p.get("name"): p.get("value") for p in temp.get("properties", [])}
    row["current_temp_f"] = extract_temp_f(tprops.get("temperature"))

    # ── HVAC.Components ───────────────────────────────────────────────────
    hvac = features.get("thermostatHvacComponents", {})
    hprops = {p.get("name"): p.get("value") for p in hvac.get("properties", [])}
    row["primary_heater_op"]   = hprops.get("primaryHeaterOperation")
    row["auxiliary_heater_op"] = hprops.get("auxiliaryHeaterOperation")
    row["cooler_op"]           = hprops.get("coolerOperation")
    row["fan_op"]              = hprops.get("fanOperation")

    return row


# ── Main poll loop ───────────────────────────────────────────────────────────
def poll_once(tm: TokenManager, conn: sqlite3.Connection):
    ts = datetime.now(timezone.utc).isoformat()
    log.info("Polling at %s", ts)

    try:
        endpoints = get_endpoints(tm)
    except requests.RequestException as e:
        log.error("Failed to fetch endpoints: %s", e)
        return

    # Filter to thermostat endpoints
    thermostats = [
        ep for ep in endpoints
        if any(
            cap.get("interface", "").startswith("Alexa.ThermostatController")
            for cap in ep.get("capabilities", [])
        )
    ]

    if not thermostats:
        log.warning("No thermostat endpoints found. Available: %s",
                    [ep.get("friendlyName") for ep in endpoints])
        return

    for ep in thermostats:
        eid  = ep["endpointId"]
        name = ep.get("friendlyName", eid)
        log.info("  Reading thermostat: %s (%s)", name, eid)

        features = get_thermostat_features(tm, eid)
        row = parse_features(features)

        conn.execute("""
            INSERT INTO thermostat_readings (
                ts, endpoint_id, endpoint_name,
                thermostat_mode, adaptive_recovery,
                target_setpoint_f, lower_setpoint_f, upper_setpoint_f,
                current_temp_f,
                primary_heater_op, auxiliary_heater_op, cooler_op, fan_op,
                raw_json
            ) VALUES (
                :ts, :endpoint_id, :endpoint_name,
                :thermostat_mode, :adaptive_recovery,
                :target_setpoint_f, :lower_setpoint_f, :upper_setpoint_f,
                :current_temp_f,
                :primary_heater_op, :auxiliary_heater_op, :cooler_op, :fan_op,
                :raw_json
            )
        """, {
            "ts":               ts,
            "endpoint_id":      eid,
            "endpoint_name":    name,
            **row,
            "raw_json":         json.dumps(features),
        })
        conn.commit()

        log.info("    mode=%-6s  temp=%-5s°F  setpoint=%-5s°F  "
                 "heat=%s  cool=%s  fan=%s",
                 row.get("thermostat_mode", "?"),
                 row.get("current_temp_f", "?"),
                 row.get("target_setpoint_f") or row.get("lower_setpoint_f", "?"),
                 row.get("primary_heater_op", "?"),
                 row.get("cooler_op", "?"),
                 row.get("fan_op", "?"))


def main():
    parser = argparse.ArgumentParser(description="Poll Alexa thermostat state")
    parser.add_argument("--interval", type=int, default=5,
                        help="Poll interval in minutes (default: 5)")
    parser.add_argument("--once", action="store_true",
                        help="Poll once and exit (useful for cron)")
    args = parser.parse_args()

    if not CONFIG_FILE.exists():
        print(f"ERROR: Config file not found: {CONFIG_FILE}")
        print("Run  python auth.py  first to set up credentials.")
        raise SystemExit(1)

    cfg = json.loads(CONFIG_FILE.read_text())
    tm  = TokenManager(cfg)

    conn = sqlite3.connect(DB_FILE)
    init_db(conn)

    if args.once:
        poll_once(tm, conn)
        conn.close()
        return

    log.info("Starting poller — interval=%d min — db=%s", args.interval, DB_FILE)
    interval_sec = args.interval * 60
    while True:
        try:
            poll_once(tm, conn)
        except Exception as e:
            log.error("Unexpected error: %s", e, exc_info=True)
        log.info("Sleeping %d minutes…", args.interval)
        time.sleep(interval_sec)


if __name__ == "__main__":
    main()
