# GG Sonar REST API — Findings

> Discovery date: 2026-05-14  
> Server: `http://127.0.0.1:53537` (port assigned at runtime; discovered via `coreProps.json` → `/subApps`)  
> Protocol: HTTP (plain, not HTTPS on this install). Self-signed HTTPS on some installs — ignore cert errors.  
> Sources: live probing (`map_gg_sonar_api.py`), source analysis (`arctis_centre` app `service.ts`)

---

## Address discovery

```
C:\ProgramData\SteelSeries\SteelSeries Engine 3\coreProps.json
  → ggEncryptedAddress  (base GG address)

GET https://{ggEncryptedAddress}/subApps
  → .subApps.sonar.metadata.webServerAddress  (Sonar base URL)
```

The Sonar base URL changes on every GG restart. Always resolve it at runtime.

---

## Channel names

The Sonar API uses these identifiers as URL path segments and JSON keys:

| API name | UI label | Notes |
|---|---|---|
| `game` | Game | |
| `chatRender` | Chat (output) | Not `chat` |
| `chatCapture` | Mic (input) | Not `mic` or `microphone` |
| `media` | Media | |
| `aux` | Aux | |
| `master` | Master | Top-level only; not a `devices` key |

---

## Confirmed endpoints

### GET — Read

| Path | Response shape | Notes |
|---|---|---|
| `GET /mode` | `"classic"` or `"stream"` (plain string) | Not `"streamer"` — value is `"stream"` |
| `GET /features` | `[]` | Always empty on this install |
| `GET /volumeSettings/classic` | See schema below | All channels in one response |
| `GET /volumeSettings/streamer` | See schema below | Adds `stream.streaming` / `stream.monitoring` sub-keys |
| `GET /configs` | Array of preset objects | 369 items; includes EQ, boost, spatial, smart volume, `isFavorite`, `favoritePosition` |
| `GET /configs/selected` | Array of preset objects | One entry per `virtualAudioDevice`; same shape as `/configs` |
| `GET /audioDevices` | Array of device objects | All Windows audio devices + Sonar VADs; `role` field maps to channel name |
| `GET /chatMix` | `{"balance": 0.0, "state": "finiteWheel"}` | Also accessible as `/chatmix` (lowercase) |

#### `/volumeSettings/classic` response shape

```json
{
  "masters": {
    "stream": {},
    "classic": { "volume": 1.0, "muted": false }
  },
  "devices": {
    "game":        { "stream": {}, "classic": { "volume": 1.0,  "muted": false } },
    "chatRender":  { "stream": {}, "classic": { "volume": 0.72, "muted": false } },
    "chatCapture": { "stream": {}, "classic": { "volume": 1.0,  "muted": false } },
    "media":       { "stream": {}, "classic": { "volume": 1.0,  "muted": false } },
    "aux":         { "stream": {}, "classic": { "volume": 0.02, "muted": false } }
  }
}
```

#### `/volumeSettings/streamer` response shape

Same as above but `stream` is populated:

```json
"stream": {
  "streaming":  { "volume": 1.0, "muted": false },
  "monitoring": { "volume": 1.0, "muted": false }
}
```

#### `/configs` item shape (preset object)

```json
{
  "id":                 "e6979db3-3e00-4399-b58c-6f026c9ef6ba",
  "name":               "Custom",
  "createdAt":          "2025-12-14T13:29:35",
  "updatedAt":          "2026-02-22T14:39:56.4346307",
  "virtualAudioDevice": "game",
  "schemaVersion":      5,
  "isPreset":           false,
  "isFavorite":         true,
  "favoritePosition":   4,
  "releaseVersion":     null,
  "image":              "8.svg",
  "data": {
    "globalEnableState":   true,
    "generalGain":         0,
    "bassBoostState":      { "enabled": true,  "value": 0 },
    "trebleBoostState":    { "enabled": true,  "value": 0 },
    "voiceClarityState":   { "enabled": true,  "value": 0 },
    "smartVolume":         { "enabled": false, "volumeLevel": 0, "loudness": "balanced" },
    "virtualSurroundState": false,
    "virtualSurroundChannels": {
      "frontLeft":  { "position": 30,   "gain": 0 },
      "frontRight": { "position": -30,  "gain": 0 },
      "center":     { "position": 0,    "gain": 0 },
      "subWoofer":  { "position": 0,    "gain": 0 },
      "rearLeft":   { "position": 150,  "gain": 0 },
      "rearRight":  { "position": -150, "gain": 0 },
      "sideLeft":   { "position": 90,   "gain": 0 },
      "sideRight":  { "position": -90,  "gain": 0 }
    },
    "reverbGainDB": -6,
    "formFactor":   "headphones",
    "parametricEQ": {
      "enabled": true,
      "filter1": { "enabled": true, "qFactor": 0.7071, "frequency": 35,    "gain": 0, "type": "peakingEQ" },
      "filter2": { "enabled": true, "qFactor": 0.7071, "frequency": 120,   "gain": 0, "type": "peakingEQ" },
      "filter3": { "enabled": true, "qFactor": 0.7071, "frequency": 1000,  "gain": 0, "type": "peakingEQ" },
      "filter4": { "enabled": true, "qFactor": 0.7071, "frequency": 6000,  "gain": 0, "type": "peakingEQ" },
      "filter5": { "enabled": true, "qFactor": 0.7071, "frequency": 18000, "gain": 0, "type": "peakingEQ" },
      "filter6": { "enabled": false, "qFactor": 0.7071, "frequency": 1000, "gain": 0, "type": "peakingEQ" }
    }
  },
  "defaultData": { "...same shape as data, factory defaults..." }
}
```

Mic channel (`chatCapture`) configs have different `data` fields: `noiseReductionState`, `noiseGateState`, `automaticNoiseGateState`, `volumeStabilizerState`, `noiseCancelingState`, `acousticEchoCancelingState`, `impactNoiseReductionState`.

#### `/audioDevices` item shape

```json
{
  "friendlyName":  "SteelSeries Sonar - Gaming (SteelSeries Sonar Virtual Audio Device)",
  "id":            "{0.0.0.00000000}.{49177f02-d92b-4d29-9e77-52edf7471a2a}",
  "dataFlow":      "render",
  "role":          "game",
  "channels":      8,
  "defaultRole":   "multimedia",
  "fwUpdateRequired": false,
  "state":         "active",
  "isVad":         true
}
```

`role` values on Sonar VADs: `game`, `chatRender`, `chatCapture`, `media`, `aux`. Physical devices have `role: "none"`. `dataFlow`: `"render"` = output, `"capture"` = input.

---

### PUT — Write

> **Path segment casing matters.** The working paths use mixed case exactly as shown. Wrong case → 404.

#### Volume (classic mode)

```
PUT /volumeSettings/classic/{channel}/Volume/{value}
PUT /volumeSettings/classic/{channel}/Mute/{true|false}
```

- `{channel}`: `game`, `chatRender`, `chatCapture`, `media`, `aux`, `master`
- `{value}` for volume: float `0.0`–`1.0` (e.g. `0.75`)
- `{value}` for mute: `true` or `false`
- No request body needed — value is in the URL
- Response: full `/volumeSettings/classic` payload (updated state)

Examples:
```
PUT /volumeSettings/classic/game/Volume/0.8
PUT /volumeSettings/classic/chatRender/Mute/true
PUT /volumeSettings/classic/master/Volume/1.0
```

#### Volume (streamer mode)

```
PUT /volumeSettings/streamer/streaming/{channel}/Volume/{value}
PUT /volumeSettings/streamer/monitoring/{channel}/Volume/{value}
PUT /volumeSettings/streamer/streaming/{channel}/isMuted/{true|false}
PUT /volumeSettings/streamer/monitoring/{channel}/isMuted/{true|false}
```

- Note `isMuted` (not `Mute`) for streamer mode
- Returns 500 when GG is in classic mode — switch mode first

#### Preset selection

```
PUT /configs/{uuid}/select
```

- No request body — UUID is in the URL
- `{uuid}`: ID from `GET /configs` (e.g. `e6979db3-3e00-4399-b58c-6f026c9ef6ba`)
- Response: full preset object that was selected
- The selected preset applies to the channel identified by the preset's own `virtualAudioDevice` field — no channel parameter needed

#### Preset management

```
POST /configs       → create a new preset (body: preset data object)
PUT  /configs       → update an existing preset (body: preset data object with id)
DELETE /configs/{uuid}  → delete preset by ID
DELETE /configs/selected   → (presumably resets selection; use with caution)
DELETE /configs/favorites  → (presumably clears all favorites)
DELETE /configs/classic    → (presumably deletes all classic-mode configs)
DELETE /configs/streamer   → (presumably deletes all streamer-mode configs)
```

> POST/PUT body format for create/edit not yet tested. Use the shape from `GET /configs` as the template.

#### ChatMix

```
PUT /chatMix
```

- Body format not yet confirmed. GET returns `{"balance": 0.0, "state": "finiteWheel"}`.

---

### Methods summary (from OPTIONS probes)

| Path | Allowed methods |
|---|---|
| `/mode` | GET |
| `/volumeSettings/classic` | GET |
| `/volumeSettings/streamer` | GET |
| `/configs` | GET, POST, PUT |
| `/configs/selected` | GET, DELETE |
| `/configs/{uuid}` | DELETE |
| `/configs/favorites` | DELETE |
| `/configs/classic` | DELETE |
| `/configs/streamer` | DELETE |
| `/audioDevices` | GET |
| `/chatMix` | GET, PUT |

---

## Favorites

There is no dedicated GET endpoint for favorites and no confirmed add-favorite endpoint. Favorites are embedded in every preset object:

```json
{ "isFavorite": true, "favoritePosition": 4 }
```

To get favorites: `GET /configs` and filter client-side where `isFavorite == true`, sorted by `favoritePosition`.

To toggle favorites: likely requires `PUT /configs` with the preset body modified to set `isFavorite: true/false`. Not yet confirmed.

---

## Not found / not exposed

| Feature | Status | Notes |
|---|---|---|
| GG Sonar enabled/disabled state | ❌ | No endpoint responds. Not in `/features` (empty). Probably not exposed. |
| Write mode (classic ↔ streamer) | ❌ | `PUT /mode` → 405, Allow: GET. Read-only. |
| Channel routed apps | ❌ | 9 candidate paths tried (`/AudioDeviceRouting`, `/applications`, `/sessions`, etc.) — all 404. Routing is OS-level: apps select a Sonar VAD via Windows audio APIs; there is no REST routing table. |
| Channel state (enabled/disabled) | ❌ | Not in any response payload. May not exist — use volume=0 + muted as equivalent. |
| Channel output device assignment | ❌ | `GET /audioDevices` maps roles to channel names but no write endpoint found. |
| GET preset by ID | ❌ | `GET /configs/{uuid}` → 405, Allow: DELETE. Read the full list and filter. |
| Add to favorites | ❓ | No confirmed endpoint. Likely `PUT /configs` with modified body. |
| Per-channel selected preset | ❓ | `GET /configs/selected/{channel}` → 404. Use `GET /configs/selected` and filter by `virtualAudioDevice`. |

---

## Discovery tooling

```bash
# Probe all endpoints and save log
python src/scripts/map_gg_sonar_api.py probe

# Parse log and print report
python src/scripts/map_gg_sonar_api.py analyze

# Listen for WebSocket events (requires: pip install websocket-client)
python src/scripts/map_gg_sonar_api.py watch

# Quick ad-hoc query (original probe script)
python src/scripts/probe_sonar_api.py --endpoint /configs/selected
```

Logs saved to: `logs/sonar_api_YYYY-MM-DD_HHMMSS.json`
