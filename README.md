# Irish Rail Commute for Home Assistant

A Home Assistant custom integration that tracks live Irish Rail train services between two stations. Shows the next N upcoming departures with delay information, cancellation status, and travel recommendations — all powered by the free Irish Rail Real-time API (no API key required).

---

## What it does

- Polls the [Irish Rail Real-time API](https://api.irishrail.ie/realtime/) for live departure data at your origin station
- Filters services to your chosen destination
- Tracks the next N upcoming trains within a configurable time window
- Classifies delays as minor, major, or severe based on configurable thresholds
- Provides a countdown sensor, per-train sensors, a summary sensor, and a disruption binary sensor
- Includes a custom Lovelace card with a timeline UI, delay indicators, and travel recommendations
- Supports multiple routes — add the integration more than once for different commutes

Data is live (not delayed) and reflects current train status from Irish Rail.

---

## Features

- Real-time train departure data from the Irish Rail API
- Configurable time window (how far ahead to look) and number of services to track
- Delay classification with configurable thresholds:
  - Minor delays (default: 3+ min)
  - Major delays (default: 15+ min)
  - Severe disruption (default: 30+ min)
- Smart update intervals:
  - Every 2 minutes during peak hours (06:00–10:00 and 16:00–19:00)
  - Every 5 minutes off-peak
  - Every 15 minutes overnight (00:00–05:00) when night updates are enabled
  - Night update mode: disable overnight polling entirely to avoid unnecessary API calls
- Custom Lovelace card with timeline UI, delay indicators, and travel recommendations
- Multiple routes supported — add the integration multiple times for each commute

---

## Installation

### Via HACS (recommended)

1. Open HACS in your Home Assistant instance.
2. Go to **Integrations** → click the three-dot menu → **Custom repositories**.
3. Add `https://github.com/jmurphylaois1/irish-rail-commute-ha` as an **Integration**.
4. Search for **Irish Rail Commute** and install it.
5. Restart Home Assistant.

### Manual installation

1. Download or clone this repository.
2. Copy the `custom_components/irish_rail_commute/` directory into your Home Assistant `config/custom_components/` directory.
3. Restart Home Assistant.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Irish Rail Commute**.
3. **Step 1 — Choose route:** Select your origin and destination station from the dropdown lists (populated live from the Irish Rail API).
4. **Step 2 — Commute settings:**
   - **Commute name** — a label for this route (defaults to "Origin → Destination")
   - **Time window (minutes)** — how many minutes ahead to look for services (15–180, default 60)
   - **Number of services** — how many upcoming trains to track (1–10, default 3)
   - **Enable night updates** — if disabled, polling pauses between midnight and 05:00

Repeat for each commute route you want to track.

You can update these settings at any time via **Settings → Devices & Services → Irish Rail Commute → Configure**.

---

## Entities created

For each configured route, the integration creates:

| Entity | Description |
|--------|-------------|
| `sensor.<name>_summary` | Summary text and full train list as attributes |
| `sensor.<name>_status` | Overall status (Normal, Minor Delays, Major Delays, etc.) |
| `sensor.<name>_next_train` | Next departure time (with delay suffix if applicable) |
| `sensor.<name>_countdown` | Human-readable countdown (e.g. "12 min", "Due", "Departed") |
| `sensor.<name>_train_1` … `_train_N` | Individual sensors for each tracked service |
| `binary_sensor.<name>_has_disruption` | `on` when the route has delays or cancellations |

---

## Custom Lovelace card

The integration includes a custom card (`irish-rail-commute-card`) that provides a polished timeline view of your commute.

### Step 1 — Copy the card file

Copy `www/irish-rail-commute-card.js` from this repository to your Home Assistant `config/www/` directory.

### Step 2 — Add the card resource

Go to **Settings → Dashboards → Resources → Add resource** and enter:

- **URL:** `/local/irish-rail-commute-card.js`
- **Resource type:** JavaScript module

### Step 3 — Add the card to your dashboard

In the Lovelace dashboard editor, add a **Manual card** with this YAML:

```yaml
type: custom:irish-rail-commute-card
entity: sensor.irish_rail_commute_summary
show_last_updated: true
show_day_view: true
show_recommendation: true
show_compact_times: true
```

Replace `sensor.irish_rail_commute_summary` with the actual entity ID of your summary sensor (found in **Settings → Devices & Services → Irish Rail Commute**).

### Card options

| Option | Default | Description |
|--------|---------|-------------|
| `entity` | *(required)* | Entity ID of the summary sensor |
| `show_last_updated` | `true` | Show when data was last refreshed |
| `show_day_view` | `true` | Show a day-level view of services |
| `show_recommendation` | `true` | Show a travel recommendation based on current delays |
| `show_compact_times` | `true` | Use compact time display format |

---

## API

This integration uses the free [Irish Rail Real-time API](https://api.irishrail.ie/realtime/). No registration or API key is required. Data reflects live train status and is not subject to any intentional delay.

---

## Troubleshooting

- **No stations load during setup:** The integration fetches stations from the Irish Rail API at configuration time. If the API is unreachable, you will see an empty dropdown. Check your internet connection and try again.
- **No trains showing:** Verify the time window is wide enough to catch upcoming services, and that trains run on the selected route at the current time.
- **Card not loading:** Ensure the JS file has been copied to `config/www/` and the resource URL is correct. Check browser console for errors.

---

## License

MIT
