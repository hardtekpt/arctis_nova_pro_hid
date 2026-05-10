"""
Probe the SteelSeries GG Sonar local REST API.

Reads coreProps.json to find the Sonar HTTPS address, then queries:
  /subApps     → discover Sonar's actual web server address
  /configs     → list audio configurations (looking for EQ preset names)

Usage:
  python src/scripts/probe_sonar_api.py
  python src/scripts/probe_sonar_api.py --endpoint /configs/selected
  python src/scripts/probe_sonar_api.py --endpoint /volumeSettings/classic
"""

import argparse
import json
import ssl
import urllib.request
from pathlib import Path

CORE_PROPS = Path(r"C:\ProgramData\SteelSeries\SteelSeries Engine 3\coreProps.json")

# Ignore self-signed cert (GG regenerates it every launch)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _get(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, context=_SSL_CTX, timeout=5) as resp:
        return json.loads(resp.read())


def find_sonar_address() -> str:
    if not CORE_PROPS.exists():
        raise FileNotFoundError(
            f"coreProps.json not found at {CORE_PROPS}\n"
            "Is SteelSeries GG / Engine 3 installed and running?"
        )

    props = json.loads(CORE_PROPS.read_text())
    base = props.get("ggEncryptedAddress") or props.get("address")
    if not base:
        raise KeyError(f"No address key found in coreProps.json. Keys: {list(props)}")

    # coreProps may omit the scheme — normalise to https://
    if not base.startswith(("http://", "https://")):
        base = "https://" + base

    print(f"[coreProps] base address: {base}")

    # /subApps reveals per-app ports including Sonar
    sub = _get(f"{base}/subApps")
    sonar_meta = (
        sub.get("subApps", sub)
           .get("sonar", {})
           .get("metadata", {})
    )
    sonar_addr = sonar_meta.get("webServerAddress")
    if sonar_addr:
        print(f"[subApps]   Sonar address: {sonar_addr}")
        return sonar_addr

    # Fallback: some versions put it at top-level
    print("[subApps] full response:")
    print(json.dumps(sub, indent=2))
    raise KeyError("Could not find sonar.metadata.webServerAddress in /subApps response")


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe SteelSeries Sonar REST API")
    parser.add_argument(
        "--endpoint",
        default=None,
        help="Extra endpoint to fetch after /configs (e.g. /configs/selected)",
    )
    args = parser.parse_args()

    sonar = find_sonar_address()

    endpoints = ["/configs", "/configs/selected", "/features"]
    if args.endpoint and args.endpoint not in endpoints:
        endpoints.append(args.endpoint)

    for ep in endpoints:
        url = f"{sonar}{ep}"
        print(f"\n{'='*60}")
        print(f"GET {url}")
        print("=" * 60)
        try:
            data = _get(url)
            print(json.dumps(data, indent=2))
        except urllib.error.HTTPError as e:
            print(f"HTTP {e.code}: {e.reason}")
        except Exception as e:
            print(f"ERROR: {e}")


if __name__ == "__main__":
    main()
