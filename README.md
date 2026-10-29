# Home Assistant support for Mobile-Alerts

## Overview

This integration supports various Mobile-Alerts sensors. The integration acts as proxy server between Mobile-Alerts gateway and cloud. 

Readings can be exposed either as **native Home Assistant entities** or through an **MQTT gateway** mode that republishes them in the sarnau/MMMMobileAlerts JSON format, so an existing `mqtt:` sensor configuration (or a standalone maserver setup) keeps working unchanged.

_Based on MMMMobileAlerts by [@sarnau](https://github.com/sarnau/MMMMobileAlerts)

## Installation

Place the `custom_components` folder in your configuration directory (or add its contents to an existing `custom_components` folder). Alternatively install via [HACS](https://hacs.xyz/).

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=m-l&repository=ha_mobilealerts&category=integration)

## Configuration

The gateway is discovered automatically (UDP broadcast and DHCP). Add the integration from **Settings → Devices & Services → Add Integration → Mobile-Alerts**. Home Assistant and the gateway must be on the same subnet for discovery to succeed.

Once added, open the integration's **Configure** dialog to choose how readings are exposed and whether data is still forwarded to the Mobile-Alerts cloud. Changes are applied immediately (the config entry reloads automatically).

### Modes

**Native Home Assistant entities** (default) — each measurement becomes a Home Assistant `sensor` / `binary_sensor` entity. Temperature, humidity, CO2, air pressure, wind speed and gust sensors have state class `measurement`, and rain totals `total_increasing`, so Home Assistant keeps long-term statistics for them.

> **Coming from another fork?** Before version 0.3.11 these sensors had no state class. If you previously ran a fork that did set one (for example Iminet72/ha_mobilealerts), Home Assistant may show the repair notice "we have generated statistics in the past, but it no longer has a state class". Update to 0.3.11 or later and restart. Do **not** press the button that deletes the long-term statistics: with the state class back, the entity keeps recording under the same entity id and its existing history is kept.

**MQTT gateway (sarnau-compatible)** — each sensor's readings are published as a single JSON document to:

```
<mqtt_topic_prefix><sensor_id>/json
```

The topic prefix defaults to `/MobileAlerts/` and `<sensor_id>` is lower-case, matching the topic layout of [MMMMobileAlerts](https://github.com/sarnau/MMMMobileAlerts) / maserver. This lets the integration replace a standalone maserver while your existing `mqtt:` sensors continue to work.

The broker connection is **not** configured here — messages are published through Home Assistant's own MQTT integration, so the broker host, port and credentials live there. The MQTT integration must be set up for this mode to work.

#### Payload

Environmental measurements are published as **arrays** (templates read index `0`); wind values and all metadata are **scalars**. Each message also carries per-sensor metadata:

```json
{
  "temperature": [21.3],
  "humidity": [55],
  "temperatureExt": [12.1],
  "windSpeed": 0.2,
  "gustSpeed": 1.0,
  "directionDegree": 90,
  "direction": "E",
  "battery": "ok",
  "offline": false,
  "id": "094596df5368",
  "t": "2022-09-15T06:27:50.000Z",
  "lastTransmit": 360,
  "by_event": false,
  "counter": 54242,
  "model": "MA10238",
  "name": "Air pressure monitor (...)"
}
```

| Key | Type | Notes |
| --- | --- | --- |
| `temperature`, `temperatureExt`, `humidity`, `airPressure`, `co2`, `rain` | array | Index `0` is the current value. `temperatureExt` is a second/external probe (pool, water). |
| `windSpeed`, `gustSpeed` | scalar | m/s |
| `directionDegree` | scalar | Wind direction in degrees |
| `direction` | scalar | 16-point compass string (`N`, `NNE`, ...) |
| `wetness`, `contact` | scalar | Leakage / door-window sensors |
| `eventCounter` | scalar | Rain sensors: cumulative bucket-tip counter |
| `eventTimes` | array | Rain sensors: seconds since each of the last 9 events (`[0]` is the most recent; `0` = an event in this transmission) |
| `battery` | scalar | `"ok"` or `"low"` |
| `t` | scalar | Reading time, ISO 8601 UTC |
| `lastTransmit` | scalar | Sensor transmit interval, seconds |
| `id` | scalar | Sensor id (also in the topic) |
| `by_event` | scalar | `true` if triggered by an event rather than a scheduled report |
| `counter` | scalar | Packet counter |
| `offline` | scalar | Always `false` — see note below |
| `model`, `name` | scalar | Sensor model / name |

> **`offline`:** the integration publishes only when a sensor transmits, so `offline` is always `false` (there is no watchdog that flips it to `true` after silence — use the age of `t` for staleness instead). Rain sensors additionally publish `eventCounter` and `eventTimes`, parsed directly from the packet, so rain-gauge templates that count bucket tips work as they did with maserver.

> **Missing keys:** not every model reports every key — for example `lastTransmit` is absent on the MA10230 Humidity Guard. In templates that must tolerate this, read keys with `value_json.get('key')` instead of `value_json.key`; an absent key makes `tojson` fail with "Object of type Undefined is not JSON serializable" (this matters in `json_attributes_template`).

Example `mqtt:` sensor reusing the published data:

```yaml
mqtt:
  sensor:
    - state_topic: "/MobileAlerts/094596df5368/json"
      name: "Garage Temperature"
      value_template: "{{ value_json.temperature[0] | float }}"
      unit_of_measurement: "°C"
    - state_topic: "/MobileAlerts/094596df5368/json"
      name: "Garage Humidity"
      value_template: "{{ value_json.humidity[0] | float }}"
      unit_of_measurement: "%"
```

Battery status as a binary sensor:

```yaml
mqtt:
  binary_sensor:
    - state_topic: "/MobileAlerts/094596df5368/json"
      name: "Garage sensor battery"
      device_class: battery
      value_template: "{{ 'ON' if value_json.battery == 'low' else 'OFF' }}"
```

#### Rain sensor example

Rain sensors publish `eventCounter` (bucket tips counted by the sensor), `eventTimes` (age of the last 9 tips) and the cumulative `rain` value in mm, alongside the usual `temperature`. A rain sensor transmits when its bucket tips and otherwise only rarely — `lastTransmit` reports 7200 s (2 h) on an MA10650 — so don't give its entities a short `expire_after`, or they will go unavailable during every dry spell.

```yaml
mqtt:
  sensor:
    # Cumulative rainfall in mm, as computed by the integration (0.25 mm per tip)
    - name: "Rain total"
      state_topic: "/MobileAlerts/083b2e19ccc9/json"
      unit_of_measurement: "mm"
      device_class: precipitation
      state_class: total_increasing
      value_template: "{{ value_json.rain[0] | float }}"

    # The same from the tip counter, with your own calibration (mm per tip)
    - name: "Rain total calibrated"
      state_topic: "/MobileAlerts/083b2e19ccc9/json"
      unit_of_measurement: "mm"
      device_class: precipitation
      state_class: total_increasing
      value_template: "{{ (value_json.eventCounter | int * 0.2495) | round(2) }}"

    # When it last rained: reading time minus the age of the most recent tip
    - name: "Rain last tip"
      state_topic: "/MobileAlerts/083b2e19ccc9/json"
      device_class: timestamp
      value_template: >-
        {{ (as_datetime(value_json.t) - timedelta(seconds=value_json.eventTimes[0] | int)).isoformat() }}

  binary_sensor:
    # ON when the latest transmission contains a fresh tip (eventTimes[0] == 0),
    # back to OFF after 10 minutes without another one
    - name: "Rain tip"
      state_topic: "/MobileAlerts/083b2e19ccc9/json"
      value_template: "{{ 'ON' if value_json.eventTimes[0] | int == 0 else 'OFF' }}"
      off_delay: 600
```

Daily and hourly totals come from Home Assistant's built-in [utility meter](https://www.home-assistant.io/integrations/utility_meter/):

```yaml
utility_meter:
  rain_today:
    source: sensor.rain_total_calibrated
    cycle: daily
  rain_this_hour:
    source: sensor.rain_total_calibrated
    cycle: hourly
```

Things worth knowing:

- `rain` assumes a fixed 0.25 mm per tip. Multiply `eventCounter` by your own value (the example uses 0.2495) if you have calibrated your gauge.
- `eventTimes` stores older events in coarser units (days, hours, minutes), so "Rain last tip" is exact for a fresh tip and approximate for an old one.
- The integration drops a packet whose transmit `counter` it has already published, as maserver did, so a packet delivered twice by the gateway is not counted twice.

### Send data to cloud

When enabled (default), the integration forwards received data to the Mobile-Alerts cloud so the official app keeps working. Disable it to keep everything local.

## Credits

- Protocol and JSON format: [MMMMobileAlerts](https://github.com/sarnau/MMMMobileAlerts) by [@sarnau](https://github.com/sarnau)
- Original Home Assistant integration: [@PlusPlus-ua](https://github.com/PlusPlus-ua/ha_mobilealerts)
- Home Assistant 2024.x compatibility: [@greiter](https://github.com/greiter), [@Silver-Volt4](https://github.com/Silver-Volt4), [@msvb04](https://github.com/msvb04)
- This fork (MQTT gateway mode with the sarnau-compatible payload, rain event decoding, and the fixes listed in the changelog): [@m-l](https://github.com/m-l)

