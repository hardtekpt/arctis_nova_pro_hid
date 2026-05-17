"""
Map the SteelSeries GG Sonar local REST API.

Two modes:
  probe    Enumerate candidate endpoints, log to logs/sonar_api_TIMESTAMP.json
  analyze  Parse log file(s) and print a structured endpoint/schema report
  watch    Connect to WebSocket paths and log incoming events

Usage:
  python src/scripts/map_gg_sonar_api.py probe
  python src/scripts/map_gg_sonar_api.py probe --write-probes   # also try PUT/POST/DELETE safely
  python src/scripts/map_gg_sonar_api.py probe --prefixes       # also try /api/ /v1/ variants
  python src/scripts/map_gg_sonar_api.py analyze
  python src/scripts/map_gg_sonar_api.py analyze --file logs/sonar_api_2026-05-14_100000.json
  python src/scripts/map_gg_sonar_api.py watch
  python src/scripts/map_gg_sonar_api.py watch --duration 30

Requirements:
  stdlib only for probe/analyze.
  websocket-client (pip install websocket-client) for watch mode.
"""

from __future__ import annotations

import argparse
import datetime
import http.client
import json
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# ── Config / constants ──────────────────────────────────────────────────────

CORE_PROPS = Path(r"C:\ProgramData\SteelSeries\SteelSeries Engine 3\coreProps.json")
LOG_DIR = Path(__file__).parent.parent.parent / "logs"

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# Real channel identifiers used by the Sonar API (confirmed from /volumeSettings/classic response).
# Classic: "game", "chatRender", "chatCapture", "media", "aux"
# The API does NOT use "master", "chat", "micro" as channel path segments.
CLASSIC_CHANNELS = ["game", "chatRender", "chatCapture", "media", "aux"]
STREAMER_CHANNELS = ["game", "chatRender", "chatCapture", "media", "aux"]

# Endpoints to probe with GET (path, feature_area)
_GET_PROBES: list[tuple[str, str]] = [
    # ── Root / state ────────────────────────────────────────────────────────
    ("/",                                   "state"),
    ("/status",                             "state"),
    ("/version",                            "state"),
    ("/info",                               "state"),
    ("/health",                             "state"),
    ("/app/status",                         "state"),
    ("/app/version",                        "state"),
    ("/sonar/status",                       "state"),

    # ── Mode (classic / streamer) ────────────────────────────────────────────
    ("/mode",                               "mode"),
    ("/activeMode",                         "mode"),
    ("/config/mode",                        "mode"),
    ("/sonar/mode",                         "mode"),
    ("/config",                             "mode"),
    ("/settings",                           "mode"),

    # ── Features / capabilities ──────────────────────────────────────────────
    ("/features",                           "features"),
    ("/capabilities",                       "features"),
    ("/subApps",                            "features"),

    # ── Volume settings — top-level ──────────────────────────────────────────
    ("/volumeSettings",                     "volume"),
    ("/volumeSettings/classic",             "volume"),
    ("/volumeSettings/streamer",            "volume"),

    # ── Volume settings — per real channel (classic) ─────────────────────────
    *[(f"/volumeSettings/classic/{ch}",         "volume") for ch in CLASSIC_CHANNELS],
    # master is a top-level key; try it anyway
    ("/volumeSettings/classic/master",          "volume"),

    # ── Volume settings — per-channel sub-resources ──────────────────────────
    *[(f"/volumeSettings/classic/{ch}/volume",  "volume") for ch in CLASSIC_CHANNELS],
    *[(f"/volumeSettings/classic/{ch}/mute",    "volume") for ch in CLASSIC_CHANNELS],
    *[(f"/volumeSettings/classic/{ch}/enabled", "channels") for ch in CLASSIC_CHANNELS],
    *[(f"/volumeSettings/classic/{ch}/state",   "channels") for ch in CLASSIC_CHANNELS],

    # ── Volume settings — streamer per channel ───────────────────────────────
    *[(f"/volumeSettings/streamer/{ch}",        "volume") for ch in STREAMER_CHANNELS],

    # ── Channels ─────────────────────────────────────────────────────────────
    ("/channels",                           "channels"),
    ("/channels/classic",                   "channels"),
    ("/channels/streamer",                  "channels"),
    ("/audio/channels",                     "channels"),

    # ── Configs / EQ presets — list + selected ───────────────────────────────
    ("/configs",                            "presets"),
    ("/configs/selected",                   "presets"),
    # per-channel selected (real channel names)
    *[(f"/configs/selected/{ch}",           "presets") for ch in CLASSIC_CHANNELS],
    ("/configs/selected/master",            "presets"),

    # ── Configs — favorites ──────────────────────────────────────────────────
    ("/configs/favorites",                  "presets"),
    ("/configs/favorite",                   "presets"),
    # Query-string variant (real HTTP GET with ?isFavorite=true)
    ("/configs?isFavorite=true",            "presets"),

    # ── Configs — misc ───────────────────────────────────────────────────────
    ("/configs/classic",                    "presets"),
    ("/configs/streamer",                   "presets"),
    ("/presets",                            "presets"),
    ("/presets/selected",                   "presets"),
    ("/eq/configs",                         "presets"),
    ("/eq/configs/selected",                "presets"),
    ("/eq/presets",                         "presets"),

    # ── Spatial audio ────────────────────────────────────────────────────────
    ("/spatial",                            "spatial"),
    ("/spatialAudio",                       "spatial"),
    ("/spatial/configs",                    "spatial"),
    ("/spatial/configs/selected",           "spatial"),
    ("/spatial/presets",                    "spatial"),
    ("/spatial/active",                     "spatial"),
    *[(f"/spatial/{ch}",                    "spatial") for ch in CLASSIC_CHANNELS],
    *[(f"/spatialAudio/{ch}",               "spatial") for ch in CLASSIC_CHANNELS],

    # ── Volume boost ─────────────────────────────────────────────────────────
    ("/volumeBoost",                        "volumeBoost"),
    ("/volumeBoost/configs",                "volumeBoost"),
    ("/volumeBoost/configs/selected",       "volumeBoost"),
    *[(f"/volumeBoost/{ch}",                "volumeBoost") for ch in CLASSIC_CHANNELS],

    # ── Smart volume ─────────────────────────────────────────────────────────
    ("/smartVolume",                        "smartVolume"),
    ("/smartVolume/configs",                "smartVolume"),
    ("/smartVolume/configs/selected",       "smartVolume"),
    *[(f"/smartVolume/{ch}",                "smartVolume") for ch in CLASSIC_CHANNELS],

    # ── App routing ──────────────────────────────────────────────────────────
    ("/routing",                            "routing"),
    ("/routing/classic",                    "routing"),
    ("/routing/streamer",                   "routing"),
    ("/classicRouting",                     "routing"),
    ("/streamerRouting",                    "routing"),
    ("/apps",                               "routing"),
    ("/apps/routing",                       "routing"),
    ("/audio/routing",                      "routing"),
    # routing with real channel names
    *[(f"/routing/classic/{ch}",            "routing") for ch in CLASSIC_CHANNELS],
    *[(f"/routing/streamer/{ch}",           "routing") for ch in STREAMER_CHANNELS],
    *[(f"/classicRouting/{ch}",             "routing") for ch in CLASSIC_CHANNELS],
    # sub-resource routing within volumeSettings
    *[(f"/volumeSettings/classic/{ch}/routing",        "routing") for ch in CLASSIC_CHANNELS],
    *[(f"/volumeSettings/classic/{ch}/applications",   "routing") for ch in CLASSIC_CHANNELS],
    # process / app-level routing
    ("/processes",                          "routing"),
    ("/processRouting",                     "routing"),
    ("/processGroups",                      "routing"),
    ("/appRouting",                         "routing"),
    ("/applications",                       "routing"),

    # ── Devices ──────────────────────────────────────────────────────────────
    ("/devices",                            "devices"),
    ("/devices/output",                     "devices"),
    ("/devices/input",                      "devices"),
    ("/audioDevices",                       "devices"),
    ("/outputDevices",                      "devices"),
    ("/inputDevices",                       "devices"),
    ("/audio/devices",                      "devices"),
    # per-channel output device using real channel names as roles
    *[(f"/audioDevices/{ch}",               "devices") for ch in CLASSIC_CHANNELS],
    *[(f"/devices/output/{ch}",             "devices") for ch in CLASSIC_CHANNELS],
    *[(f"/volumeSettings/classic/{ch}/outputDevice",   "devices") for ch in CLASSIC_CHANNELS],
    *[(f"/volumeSettings/classic/{ch}/output",         "devices") for ch in CLASSIC_CHANNELS],

    # ── ChatMix ──────────────────────────────────────────────────────────────
    ("/chatMix",                            "chatMix"),
    ("/chatmix",                            "chatMix"),
    ("/chatMix/classic",                    "chatMix"),
    ("/chatMix/streamer",                   "chatMix"),

    # ── Mic / audio processing ───────────────────────────────────────────────
    ("/mic",                                "mic"),
    ("/microphone",                         "mic"),
    ("/mic/settings",                       "mic"),
    ("/audioProcessing",                    "mic"),
    # chatCapture is the mic VAD role; try as path segment too
    ("/volumeSettings/classic/chatCapture", "mic"),
    ("/configs/selected/chatCapture",       "mic"),
]

# Mutation probe: (path_template, method, body_template, safe_key_to_read_back)
# Only executed with --write-probes. Reads current value and writes it back.
_WRITE_PROBES: list[tuple[str, str, dict | None]] = [
    ("/mode",                               "PUT",    None),  # body derived from GET
    ("/volumeSettings/classic/master",      "PUT",    None),
    ("/volumeSettings/classic/game",        "PUT",    None),
    ("/volumeSettings/classic/chat",        "PUT",    None),
    ("/volumeSettings/classic/media",       "PUT",    None),
    ("/volumeSettings/classic/aux",         "PUT",    None),
    ("/volumeSettings/classic/micro",       "PUT",    None),
    ("/configs/selected",                   "PUT",    None),
    ("/routing/classic",                    "PUT",    None),
]

# WebSocket paths to try in watch mode
_WS_PATHS = [
    "/ws",
    "/websocket",
    "/events",
    "/sonar/ws",
    "/sonar/events",
    "/notifications",
    "/realtime",
    "/stream",
]

# How to group paths in the analyze report
_AREA_PREFIXES: dict[str, list[str]] = {
    "State & Mode":     ["state", "mode", "features"],
    "Volume & Mute":    ["volume", "channels"],
    "Presets (EQ/Spatial/Boost/Smart)": ["presets", "spatial", "volumeBoost", "smartVolume"],
    "App Routing":      ["routing"],
    "Devices":          ["devices"],
    "ChatMix":          ["chatMix"],
    "Mic / Processing": ["mic"],
}


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def _http_request(
    url: str,
    method: str = "GET",
    body: bytes | None = None,
    timeout: float = 5.0,
) -> tuple[int, dict[str, str], bytes | None]:
    """Return (status_code, headers, body_bytes). Raises urllib.error.URLError on network error."""
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=timeout) as resp:
            hdrs = dict(resp.getheaders())
            raw = resp.read()
            return resp.status, hdrs, raw
    except urllib.error.HTTPError as e:
        hdrs = dict(e.headers) if e.headers else {}
        try:
            raw = e.read()
        except Exception:
            raw = None
        return e.code, hdrs, raw


def _http_options(url: str, timeout: float = 3.0) -> list[str]:
    """Return the Allow methods from an OPTIONS request (may be empty)."""
    try:
        status, hdrs, _ = _http_request(url, method="OPTIONS", timeout=timeout)
        allow = hdrs.get("Allow", hdrs.get("allow", ""))
        return [m.strip() for m in allow.split(",") if m.strip()]
    except Exception:
        return []


def _try_parse_json(raw: bytes | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return raw.decode("utf-8", errors="replace")[:500]


# ── Schema inference ─────────────────────────────────────────────────────────

def _infer_schema(value: Any, depth: int = 0, max_depth: int = 4) -> Any:
    """Build a type-annotated skeleton of a JSON value (no real data, just shapes)."""
    if depth >= max_depth:
        return "..."
    if isinstance(value, dict):
        return {k: _infer_schema(v, depth + 1, max_depth) for k, v in list(value.items())[:30]}
    if isinstance(value, list):
        if not value:
            return "[]"
        schema = _infer_schema(value[0], depth + 1, max_depth)
        return [schema, f"...{len(value)} items"] if len(value) > 1 else [schema]
    if isinstance(value, bool):
        return f"bool({value})"
    if isinstance(value, int):
        return f"int({value})"
    if isinstance(value, float):
        return f"float({value:.4g})"
    if isinstance(value, str):
        return f"str({value!r})" if len(value) < 50 else f"str(len={len(value)})"
    if value is None:
        return "null"
    return type(value).__name__


# ── Address discovery ────────────────────────────────────────────────────────

def find_sonar_address() -> str:
    """Return the Sonar web server base URL (e.g. 'https://127.0.0.1:54321')."""
    if not CORE_PROPS.exists():
        raise FileNotFoundError(
            f"coreProps.json not found at {CORE_PROPS}\n"
            "Is SteelSeries GG installed and running?"
        )
    props = json.loads(CORE_PROPS.read_text())
    base = props.get("ggEncryptedAddress") or props.get("address")
    if not base:
        raise KeyError(f"No address key in coreProps.json. Keys: {list(props)}")
    if not base.startswith(("http://", "https://")):
        base = "https://" + base

    print(f"  GG base address : {base}")
    status, _, raw = _http_request(f"{base}/subApps")
    sub = _try_parse_json(raw)
    if isinstance(sub, dict):
        sonar_meta = (
            sub.get("subApps", sub)
               .get("sonar", {})
               .get("metadata", {})
        )
        addr = sonar_meta.get("webServerAddress")
        if addr:
            if not addr.startswith(("http://", "https://")):
                addr = "https://" + addr
            print(f"  Sonar address   : {addr}")
            return addr

    print("  /subApps response (raw):")
    print(f"  {json.dumps(sub, indent=2)[:800]}")
    raise KeyError("Could not find sonar.metadata.webServerAddress in /subApps")


# ── Probe mode ───────────────────────────────────────────────────────────────

def _probe_one(sonar: str, path: str, area: str) -> dict:
    url = sonar.rstrip("/") + path
    result: dict = {
        "path": path,
        "url": url,
        "area": area,
        "timestamp": datetime.datetime.now().isoformat(),
    }

    # GET
    try:
        status, hdrs, raw = _http_request(url)
        body = _try_parse_json(raw)
        result["get_status"] = status
        result["get_body"] = body
        result["get_schema"] = _infer_schema(body)
        result["content_type"] = hdrs.get("Content-Type", hdrs.get("content-type", ""))
    except urllib.error.URLError as e:
        result["get_error"] = str(e.reason)
    except Exception as e:
        result["get_error"] = str(e)

    return result


def _probe_write_one(sonar: str, path: str, method: str, explicit_body: dict | None) -> dict:
    url = sonar.rstrip("/") + path
    result: dict = {
        "path": path,
        "url": url,
        "area": "write_probe",
        "method": method,
        "timestamp": datetime.datetime.now().isoformat(),
    }

    # First read the current value
    current_body = None
    try:
        _, _, raw = _http_request(url)
        current_body = _try_parse_json(raw)
        result["read_before"] = current_body
    except Exception as e:
        result["read_error"] = str(e)
        return result

    # Use explicit body or echo the current value back
    write_body = explicit_body if explicit_body is not None else current_body
    if write_body is None:
        result["write_skipped"] = "no body to send"
        return result

    payload = json.dumps(write_body).encode()
    try:
        status, hdrs, raw = _http_request(url, method=method, body=payload)
        result["write_status"] = status
        result["write_response"] = _try_parse_json(raw)
    except urllib.error.URLError as e:
        result["write_error"] = str(e.reason)
    except Exception as e:
        result["write_error"] = str(e)

    return result


def _add_prefix_variants(probes: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Duplicate each probe with /api and /v1 prefixes."""
    extra: list[tuple[str, str]] = []
    for path, area in probes:
        for prefix in ("/api", "/v1", "/sonar"):
            extra.append((prefix + path, area))
    return probes + extra


def _extract_dynamic_probes(results: list[dict]) -> list[tuple[str, str]]:
    """
    Second-pass probe paths derived from data returned by the first pass.

    Extracts:
    - config UUIDs from GET /configs → /configs/{id}  (get / edit / delete a single preset)
    - virtualAudioDevice names from GET /configs → /configs/selected/{device}
    - audioDevice IDs from GET /audioDevices → /audioDevices/{id}
    """
    extra: list[tuple[str, str]] = []
    seen_ids: set[str] = set()

    for r in results:
        body = r.get("get_body")
        if not isinstance(body, list):
            continue

        path = r.get("path", "")

        if path == "/configs":
            for item in body[:5]:  # probe first 5 to stay quick
                if not isinstance(item, dict):
                    continue
                uid = item.get("id", "")
                vad = item.get("virtualAudioDevice", "")
                if uid and uid not in seen_ids:
                    seen_ids.add(uid)
                    extra.append((f"/configs/{uid}", "presets"))
                if vad and f"/configs/selected/{vad}" not in {p for p, _ in extra}:
                    extra.append((f"/configs/selected/{vad}", "presets"))

        if path == "/audioDevices":
            for item in body:
                if not isinstance(item, dict):
                    continue
                dev_id = item.get("id", "")
                role = item.get("role", "")
                # probe /audioDevices/{windows-device-id} (URL-encoded if needed)
                if dev_id and dev_id not in seen_ids:
                    seen_ids.add(dev_id)
                    # Windows device IDs contain braces/dots — encode minimal set
                    safe_id = dev_id.replace("{", "%7B").replace("}", "%7D")
                    extra.append((f"/audioDevices/{safe_id}", "devices"))
                # Also try the role as a path segment (shorter, more likely)
                if role and role not in ("none", "") and f"/audioDevices/{role}" not in {p for p, _ in extra}:
                    extra.append((f"/audioDevices/{role}", "devices"))

    return extra


def run_probe(
    sonar: str,
    write_probes: bool = False,
    add_prefixes: bool = False,
) -> list[dict]:
    probes = _add_prefix_variants(_GET_PROBES) if add_prefixes else _GET_PROBES
    total = len(probes) + (len(_WRITE_PROBES) if write_probes else 0)
    print(f"\nPass 1: probing {total} static endpoints on {sonar} …\n")

    results: list[dict] = []
    hits = 0

    for i, (path, area) in enumerate(probes, 1):
        r = _probe_one(sonar, path, area)
        results.append(r)
        status = r.get("get_status")
        err = r.get("get_error", "")
        if status and status < 400:
            hits += 1
            schema_str = json.dumps(r.get("get_schema"), separators=(",", ":"))[:120]
            print(f"  [{status}] GET {path:<55} {schema_str}")
        elif status:
            print(f"  [{status}] GET {path}")
        elif "Connection refused" not in err and "timed out" not in err:
            print(f"  [ERR] GET {path}  — {err[:80]}")

        if i % 50 == 0:
            print(f"  … {i}/{len(probes)} paths probed, {hits} hits so far …")

    # ── Second pass: dynamic paths derived from first-pass responses ──────────
    dynamic = _extract_dynamic_probes(results)
    if dynamic:
        print(f"\nPass 2: probing {len(dynamic)} dynamic endpoints (IDs from responses) …\n")
        for path, area in dynamic:
            r = _probe_one(sonar, path, area)
            results.append(r)
            status = r.get("get_status")
            if status and status < 400:
                hits += 1
                schema_str = json.dumps(r.get("get_schema"), separators=(",", ":"))[:120]
                print(f"  [{status}] GET {path:<55} {schema_str}")
            elif status:
                print(f"  [{status}] GET {path}")

    if write_probes:
        print(f"\nWrite probes (safe echo-back, {len(_WRITE_PROBES)} endpoints) …\n")
        for path, method, body_tpl in _WRITE_PROBES:
            r = _probe_write_one(sonar, path, method, body_tpl)
            results.append(r)
            ws = r.get("write_status")
            we = r.get("write_error", "")
            if ws:
                print(f"  [{ws}] {method} {path}")
            elif "read_error" in r:
                print(f"  [READ-ERR] {method} {path} — {r['read_error'][:60]}")
            else:
                print(f"  [WRITE-ERR] {method} {path} — {we[:60]}")

    # OPTIONS pass to discover additional methods
    print(f"\nOPTIONS probes on {hits} successful endpoints …")
    for r in results:
        if r.get("get_status", 999) < 400:
            methods = _http_options(r["url"])
            if methods:
                r["allowed_methods"] = methods
                print(f"  {r['path']}  →  {', '.join(methods)}")

    return results


# ── WebSocket watch mode ─────────────────────────────────────────────────────

def run_watch(sonar: str, duration: int = 20) -> None:
    try:
        import websocket  # type: ignore[import]
    except ImportError:
        print("ERROR: websocket-client is not installed. Run: pip install websocket-client")
        sys.exit(1)

    # Derive ws:// or wss:// base
    ws_base = sonar.replace("https://", "wss://").replace("http://", "ws://")
    print(f"\nTrying WebSocket connections on {ws_base} for {duration}s each …\n")

    found: list[str] = []
    for path in _WS_PATHS:
        ws_url = ws_base.rstrip("/") + path
        print(f"  Trying {ws_url} …", end=" ", flush=True)
        messages: list[Any] = []
        connected = False

        def _on_message(ws, msg):  # type: ignore[no-untyped-def]
            try:
                messages.append(json.loads(msg))
            except Exception:
                messages.append(msg)

        def _on_open(ws):  # type: ignore[no-untyped-def]
            nonlocal connected
            connected = True

        ws_app = websocket.WebSocketApp(
            ws_url,
            on_message=_on_message,
            on_open=_on_open,
        )
        import threading
        t = threading.Thread(
            target=lambda: ws_app.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}),
            daemon=True,
        )
        t.start()
        time.sleep(duration)
        ws_app.close()

        if connected:
            found.append(ws_url)
            print(f"CONNECTED  ({len(messages)} messages in {duration}s)")
            for msg in messages[:10]:
                print(f"    → {json.dumps(msg)[:200]}")
            if len(messages) > 10:
                print(f"    … {len(messages) - 10} more messages")
        else:
            print("no connection")

    if found:
        print(f"\nActive WebSocket endpoints: {found}")
    else:
        print("\nNo WebSocket endpoints found on tested paths.")


# ── Log I/O ──────────────────────────────────────────────────────────────────

def save_log(sonar: str, results: list[dict]) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = LOG_DIR / f"sonar_api_{ts}.json"
    log = {
        "session": ts,
        "sonar_address": sonar,
        "total_probed": len(results),
        "hits": sum(1 for r in results if r.get("get_status", 999) < 400),
        "results": results,
    }
    path.write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(f"\nLog saved: {path}")
    return path


def load_logs(file_arg: str | None) -> list[dict]:
    if file_arg:
        paths = [Path(file_arg)]
    else:
        paths = sorted(LOG_DIR.glob("sonar_api_*.json"))
    if not paths:
        print("No sonar_api_*.json log files found in logs/.")
        return []
    logs = []
    for p in paths:
        try:
            logs.append(json.loads(p.read_text(encoding="utf-8")))
            print(f"  Loaded: {p}")
        except Exception as e:
            print(f"  ERROR loading {p}: {e}")
    return logs


# ── Analyze mode ─────────────────────────────────────────────────────────────

def _collect_results(logs: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for log in logs:
        for r in log.get("results", []):
            path = r.get("path", "")
            status = r.get("get_status")
            if not status or status >= 400:
                continue
            # Keep the latest entry per path
            if path not in seen or r["timestamp"] > seen[path]["timestamp"]:
                seen[path] = r
    return sorted(seen.values(), key=lambda r: r["path"])


def _format_schema(schema: Any, indent: int = 6) -> str:
    pad = " " * indent
    s = json.dumps(schema, indent=2)
    lines = s.splitlines()
    return "\n".join(pad + ln for ln in lines)


def run_analyze(file_arg: str | None) -> None:
    print("\nLoading logs …")
    logs = load_logs(file_arg)
    if not logs:
        return

    results = _collect_results(logs)
    if not results:
        print("No successful (2xx) endpoints found in logs.")
        return

    print(f"\n{'=' * 72}")
    print(f"SONAR API MAP  ({len(results)} successful endpoints across {len(logs)} log file(s))")
    print(f"{'=' * 72}\n")

    # Group by feature area
    area_results: dict[str, list[dict]] = {}
    for r in results:
        area = r.get("area", "other")
        area_results.setdefault(area, []).append(r)

    # Print display order: use _AREA_PREFIXES mapping then remainder
    printed_areas: set[str] = set()
    display_order = [
        ("State & Mode",                          ["state", "mode", "features"]),
        ("Volume & Mute (channels)",               ["volume", "channels"]),
        ("Presets / EQ / Spatial / Boost / Smart", ["presets", "spatial", "volumeBoost", "smartVolume"]),
        ("App Routing",                            ["routing"]),
        ("Devices",                               ["devices"]),
        ("ChatMix",                               ["chatMix"]),
        ("Mic / Audio Processing",                ["mic"]),
        ("Write probes",                          ["write_probe"]),
        ("Other",                                 []),
    ]

    for display_name, area_keys in display_order:
        matching: list[dict] = []
        for ak in area_keys:
            for r in area_results.get(ak, []):
                if r["path"] not in {x["path"] for x in matching}:
                    matching.append(r)
                    printed_areas.add(r.get("area", ""))

        # Catch-all "Other"
        if display_name == "Other":
            for area, rs in area_results.items():
                if area not in printed_areas:
                    matching.extend(rs)

        if not matching:
            continue

        print(f"{'─' * 72}")
        print(f"  {display_name.upper()}")
        print(f"{'─' * 72}")

        for r in sorted(matching, key=lambda x: x["path"]):
            status = r.get("get_status", "?")
            path = r["path"]
            methods = r.get("allowed_methods", ["GET"])
            methods_str = ", ".join(methods) if methods else "GET"

            print(f"\n  [{status}] {path}   ({methods_str})")

            if r.get("get_schema"):
                print(_format_schema(r["get_schema"]))

            if r.get("write_status"):
                print(f"      └─ {r.get('method','PUT')} → [{r['write_status']}]  "
                      f"{json.dumps(r.get('write_response', {}))[:80]}")

    # Summary table
    print(f"\n{'=' * 72}")
    print("SUMMARY TABLE")
    print(f"{'=' * 72}")
    print(f"  {'PATH':<55} {'STATUS':>6}  METHODS")
    print(f"  {'─'*55} {'─'*6}  {'─'*20}")
    for r in results:
        methods_str = ", ".join(r.get("allowed_methods", ["GET"]))
        print(f"  {r['path']:<55} [{r.get('get_status','?'):>3}]  {methods_str}")

    print(f"\nTotal: {len(results)} endpoint(s) confirmed reachable.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Map the SteelSeries GG Sonar local REST API"
    )
    sub = parser.add_subparsers(dest="cmd")

    p_probe = sub.add_parser("probe", help="Enumerate endpoints and log results")
    p_probe.add_argument(
        "--write-probes",
        action="store_true",
        help="Also try safe PUT/POST probes (echo current value back)",
    )
    p_probe.add_argument(
        "--prefixes",
        action="store_true",
        help="Also try /api, /v1, /sonar path prefixes (3× more requests)",
    )
    p_probe.add_argument(
        "--sonar",
        metavar="URL",
        help="Override Sonar base URL (skip coreProps.json discovery)",
    )

    p_analyze = sub.add_parser("analyze", help="Parse logs and print endpoint report")
    p_analyze.add_argument(
        "--file",
        metavar="PATH",
        help="Specific log file (default: all logs/sonar_api_*.json)",
    )

    p_watch = sub.add_parser("watch", help="Connect to WebSocket paths and log events")
    p_watch.add_argument(
        "--duration",
        type=int,
        default=20,
        metavar="SECS",
        help="Seconds to listen on each WebSocket path (default: 20)",
    )
    p_watch.add_argument(
        "--sonar",
        metavar="URL",
        help="Override Sonar base URL",
    )

    args = parser.parse_args()

    if args.cmd is None:
        parser.print_help()
        sys.exit(0)

    if args.cmd in ("probe", "watch"):
        print("Discovering Sonar address …")
        sonar = args.sonar if args.sonar else find_sonar_address()

    if args.cmd == "probe":
        results = run_probe(
            sonar,
            write_probes=args.write_probes,
            add_prefixes=args.prefixes,
        )
        log_path = save_log(sonar, results)
        print(f"\nRun 'python {Path(__file__).name} analyze --file {log_path}' to view the report.")

    elif args.cmd == "analyze":
        run_analyze(args.file)

    elif args.cmd == "watch":
        run_watch(sonar, duration=args.duration)


if __name__ == "__main__":
    main()
