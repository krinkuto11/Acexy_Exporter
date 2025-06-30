import time
import re
import requests
from prometheus_client import start_http_server, Gauge
from collections import defaultdict
import os

MTAIL_METRICS_URL = os.environ.get("MTAIL_METRICS_URL","http://localhost:3903/metrics")
CHANNEL_LOOKUP_URL = os.environ.get("CHANNEL_LOOKUP_URL",   "http://192.168.20.3:8000/api/tv-channels/find-matches")
EXPORTER_PORT = 9101

active_streams_by_channel = Gauge("active_streams_by_channel", "Número de streams activos por canal", ["channel_name"])
stream_cache = {}
stream_id_regex = re.compile(r'gauge_clients_per_stream\{stream_ID="([a-f0-9]+)"\} ([0-9]+)')

def get_channel_name(stream_id):
    if stream_id in stream_cache:
        print(f"[Cache] Found cached channel name for stream ID {stream_id}")
        return stream_cache[stream_id]

    try:
        print(f"[API] Looking up channel for stream ID {stream_id}")
        resp = requests.get(CHANNEL_LOOKUP_URL, params={"id": stream_id}, timeout=2)
        print(f"[API] Response status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"[API] Response JSON: {data}")
            matches = data.get("matches", [])
            if matches and "channel" in matches[0]:
                name = matches[0]["channel"].get("name", f"unknown_{stream_id[:6]}")
            else:
                name = f"unknown_{stream_id[:6]}"
            stream_cache[stream_id] = name
            return name
        else:
            print(f"[API] Non-200 response for stream ID {stream_id}")
    except Exception as e:
        print(f"[!] Error getting channel for ID {stream_id}: {e}")

    return f"unknown_{stream_id[:6]}"

def collect_and_export():
    while True:
        try:
            print(f"[Fetch] Requesting metrics from MTail: {MTAIL_METRICS_URL}")
            resp = requests.get(MTAIL_METRICS_URL)
            active_streams_by_channel.clear()
            if resp.status_code != 200:
                print(f"[!] Failed to fetch metrics (HTTP {resp.status_code})")
                time.sleep(10)
                continue

            print("[Fetch] Metrics response OK")
            body = resp.text
            print("[Fetch] Response body snippet:")
            print("\n".join(body.splitlines()[:10]))  # Print first 10 lines for preview

            matches = stream_id_regex.findall(body)
            print(f"[Parse] Found {len(matches)} stream matches")

            if not matches:
                print("[Parse] No gauge_clients_per_stream matches found.")
            else:
                counts = defaultdict(int)
                for stream_id, clients in matches:
                    print(f"[Parse] Found stream ID {stream_id} with {clients} clients")
                    channel_name = get_channel_name(stream_id)
                    print(f"[Metric] Mapping stream ID {stream_id} to channel '{channel_name}'")
                    counts[channel_name] += int(clients)

                print("[Prometheus] Exporting metrics per channel:")
                for channel, count in counts.items():
                    print(f"    - {channel}: {count} active clients")
                    active_streams_by_channel.labels(channel).set(count)

        except Exception as e:
            print(f"[!] Error reading or exporting metrics: {e}")

        time.sleep(10)

if __name__ == "__main__":
    print(f"[Start] Exporter starting on port {EXPORTER_PORT}...")
    start_http_server(EXPORTER_PORT)
    collect_and_export()
