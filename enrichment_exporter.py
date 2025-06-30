import time
import re
import requests
from prometheus_client import start_http_server, Gauge
from collections import defaultdict

MTAIL_METRICS_URL = "http://localhost:3903/metrics"
CHANNEL_LOOKUP_URL = "http://192.168.20.3:8000/api/tv-channels/find-matches"
EXPORTER_PORT = 9101

active_streams_by_channel = Gauge("active_streams_by_channel", "Número de streams activos por canal", ["channel_name"])
stream_cache = {}
stream_id_regex = re.compile(r'gauge_clients_per_stream\{stream_ID="([a-f0-9]+)"\} ([0-9]+)')

def get_channel_name(stream_id):
    if stream_id in stream_cache:
        return stream_cache[stream_id]
    try:
        resp = requests.get(CHANNEL_LOOKUP_URL, params={"id": stream_id}, timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            matches = data.get("matches", [])
            if matches and "channel" in matches[0]:
                name = matches[0]["channel"].get("name", f"unknown_{stream_id[:6]}")
            else:
                name = f"unknown_{stream_id[:6]}"
            stream_cache[stream_id] = name
            return name
    except Exception as e:
        print(f"[!] Error obteniendo canal para ID {stream_id}: {e}")
    return f"unknown_{stream_id[:6]}"

def collect_and_export():
    while True:
        try:
            resp = requests.get(MTAIL_METRICS_URL)
            active_streams_by_channel.clear()
            if resp.status_code == 200:
                matches = stream_id_regex.findall(resp.text)
                counts = defaultdict(int)
                for stream_id, clients in matches:
                    channel_name = get_channel_name(stream_id)
                    counts[channel_name] += int(clients)
                for channel, count in counts.items():
                    active_streams_by_channel.labels(channel).set(count)
        except Exception as e:
            print(f"[!] Error leyendo métricas: {e}")
        time.sleep(10)

if __name__ == "__main__":
    print(f"Exportador iniciando en puerto {EXPORTER_PORT}...")
    start_http_server(EXPORTER_PORT)
    collect_and_export()
