# Alexa Thermostat Poller — Does Not Work

**Status: abandoned. The code in this directory is non-functional and kept only as a record.**

This was an attempt to poll an Amazon Smart Thermostat every 5 minutes and log real
HVAC on/off state to SQLite, so that wxViewer's Thermal Analysis panel could train on
labeled ground truth instead of inferring HVAC activity from the passive thermal model.

It cannot work. Not because of a bug — because Amazon does not expose the data.

---

## Why it can't work

### 1. The HVAC data flows the wrong direction

The fields this poller was built to capture — `primaryHeaterOperation`,
`coolerOperation`, `auxiliaryHeaterOperation`, `fanOperation` — belong to the
[`Alexa.ThermostatController.HVAC.Components`][hvac] interface.

That interface is implemented *by a device maker's cloud, reporting **to** Alexa*, so
Alexa can populate its energy dashboard. The manufacturer answers `ReportState`
directives and sends proactive `ChangeReport` events. Nothing reads those properties
back out. There is no query direction.

This is the fatal one. No amount of fixing the other three problems gets around it.

### 2. `poll.py` targets an enterprise API

`ASP_BASE = "https://api.amazonalexa.com"` with `GET /v2/endpoints` is the
[Alexa Smart Properties][asp] Endpoint API — Amazon's commercial product for
hospitality, senior living, and healthcare properties.

Using it requires an Amazon Business account, onboarding through Amazon's Business
Development team, and an issued organization identifier (`amzn1.alexa.unit.did.{id}`).
A personal Amazon account — the one your thermostat is actually registered to — cannot
reach it.

### 3. `auth.py` and `poll.py` disagree about which API they're for

`auth.py` requests these scopes:

```
alexa::smarthome:devices:read
alexa::smarthome:guest:skill:invokeAlexa
```

Alexa Smart Properties requires an entirely different set:

```
alexa::enterprise:management
credential_locker::wifi_management
profile:user_id
```

So even with an entitled business account, the token `auth.py` produces is not one
`poll.py`'s endpoint accepts. The OAuth flow would appear to succeed and every poll
would then fail authorization.

### 4. Two of the three polled feature names don't exist

`poll.py` requests `thermostat`, `temperature`, and `thermostatHvacComponents`.

The [documented feature names][features] are `bluetooth`, `brightness`, `color`,
`colorTemperature`, `connectivity`, `power`, `speaker`, `temperatureSensor`, and
`thermostat`. Only the first of the three is real; `temperature` should have been
`temperatureSensor`, and `thermostatHvacComponents` was invented.

Worse, `get_thermostat_features()` swallows a 404 into `log.debug`, so these would have
produced permanently empty columns and a log line invisible at the default level. The
failure mode would have read as "my thermostat doesn't report this" rather than "I asked
for a field that never existed."

---

## Is there any other way to read an Amazon Smart Thermostat?

Not officially. Amazon publishes no consumer API for thermostat state. The Home
Assistant community [reached the same conclusion independently][ha] — there is no HA
integration for it, for this reason.

The one known workaround is [`homebridge-alexa-smarthome`][homebridge], which proxies an
Amazon login to capture a session cookie (valid ~14 days, auto-refreshed) and exposes
Alexa-linked devices to HomeKit. It is unofficial, breaks when Amazon changes anything,
and it is unclear whether it surfaces true compressor/blower running state as opposed to
just mode and current temperature.

---

## What to do instead

Measure the HVAC directly rather than asking Amazon about it.

A current transformer (CT) clamp on the air handler and condenser circuits reports actual
electrical draw, which gives unambiguous on/off state — and, from the magnitude of the
draw, which stage is running. That is strictly better ground truth than anything the
thermostat would have reported, and it involves no cloud API, no OAuth, and no vendor
that can revoke access.

See the **HVAC monitoring** section of the main [README](../README.md).

---

## The code in this directory

`auth.py` and `poll.py` are retained so this write-up can point at specific lines. They
have never been run successfully and should not be. There is no `config.json` and no
`hvac_data.db`, and none will be produced.

[hvac]: https://developer.amazon.com/en-US/docs/alexa/device-apis/alexa-thermostatcontroller-hvac-components.html
[asp]: https://developer.amazon.com/en-US/docs/alexa/alexa-smart-properties/get-started.html
[features]: https://developer.amazon.com/en-US/docs/alexa/alexa-smart-properties/endpoint-features-api.html
[ha]: https://community.home-assistant.io/t/pass-amazon-smart-thermostat-info-to-ha/720795
[homebridge]: https://github.com/joeyhage/homebridge-alexa-smarthome
