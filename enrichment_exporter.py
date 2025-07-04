import time
import re
import requests
import os
from prometheus_client import start_http_server, Gauge
from collections import defaultdict

MTAIL_METRICS_URL = os.environ.get("MTAIL_METRICS_URL", "http://localhost:3903/metrics")
CHANNELS_URL = os.environ.get("CHANNELS_URL", "http://192.168.20.3:8000/api/tv-channels/")
ACESTREAMS_URL_TEMPLATE = os.environ.get("ACESTREAMS_URL_TEMPLATE", "http://192.168.20.3:8000/api/tv-channels/{}/acestreams")
EXPORTER_PORT = 9101

active_streams_by_channel = Gauge("active_streams_by_channel", "Número de streams activos por canal", ["channel_name"])
acestream_to_channel = {}  # acestream_id → channel_name
streams_by_user = Gauge("streams_by_user", "Número de streams por usuario y canal", ["user", "channel_name"])
stream_id_regex = re.compile(r'clients_per_stream\{[^}]*stream_ID="([a-f0-9]{40})"[^}]*} ([0-9]+)')
stream_user_regex = re.compile(r'stream_by_user\{[^}]*stream_ID="(?P<stream_id>[a-f0-9]{40})"[^}]*user="(?P<user>[^"]+)"[^}]*\} (?P<count>[0-9]+)')

def build_acestream_mapping():
    global acestream_to_channel
    print("[Cache] Refreshing acestream-to-channel map...")

    page = 1
    mapping = {}

    try:
        while True:
            paged_url = f"{CHANNELS_URL}?page={page}"
            print(f"[Fetch] Getting channels from: {paged_url}")
            resp = requests.get(paged_url, timeout=5)
            if resp.status_code != 200:
                print(f"[!] Failed to fetch channels page {page}")
                break

            data = resp.json()
            channels = data.get("channels", [])
            if not channels:
                break

            for channel in channels:
                chan_id = channel.get("id")
                chan_name = channel.get("name", f"unknown_{chan_id}")
                if not chan_id:
                    continue

                acestreams_url = ACESTREAMS_URL_TEMPLATE.format(chan_id)
                try:
                    ace_resp = requests.get(acestreams_url, timeout=3)
                    if ace_resp.status_code == 200:
                        ace_data = ace_resp.json()
                        ace_list = ace_data.get("acestreams", [])
                        for stream in ace_list:
                            ace_id = stream.get("id")
                            if ace_id:
                                mapping[ace_id.lower()] = chan_name
                except Exception as e:
                    print(f"[!] Error fetching acestreams for channel {chan_id}: {e}")

            if page >= data.get("total_pages", page):  # done!
                break

            page += 1

        acestream_to_channel = mapping
        print(f"[Cache] Mapping complete with {len(acestream_to_channel)} entries.")

    except Exception as e:
        print(f"[!] Error building acestream cache: {e}")


def get_channel_name_from_stream_id(stream_id):
    print(f"Probando a matchear {stream_id}")
    return acestream_to_channel.get(stream_id, f"unknown_{stream_id[:6]}")

def collect_and_export():
    refresh_interval = 60 * 5  # refresh channel map every 5 minutes
    last_refresh = 0

    while True:
        now = time.time()
        if now - last_refresh > refresh_interval or not acestream_to_channel:
            build_acestream_mapping()
            last_refresh = now

        try:
            print("[Fetch] Requesting MTail metrics...")
            resp = requests.get(MTAIL_METRICS_URL, timeout=5)
            active_streams_by_channel.clear()

            if resp.status_code != 200:
                print(f"[!] Failed to fetch metrics (HTTP {resp.status_code})")
                time.sleep(10)
                continue

            body = resp.text
            matches = stream_id_regex.findall(body)
            print(f"[Parse] Found {len(matches)} stream entries.")

            counts = defaultdict(int)
            for stream_id, clients in matches:
                channel_name = get_channel_name_from_stream_id(stream_id)
                counts[channel_name] += int(clients)

            for channel, count in counts.items():
                print(f"[Metric] Channel: {channel}, Clients: {count}")
                active_streams_by_channel.labels(channel).set(count)

            user_matches = stream_user_regex.findall(body)
            print(f"[Parse] Found {len(user_matches)} user stream entries.")

            streams_by_user.clear()
            for match in user_matches:
                user = match.group("user")
                stream_id = match.group("stream_id")
                count = match.group("count")
                channel_name = get_channel_name_from_stream_id(stream_id)
                print(f"[UserMetric] User: {user}, Channel: {channel_name}, Clients: {count}")
                streams_by_user.labels(user=user, channel_name=channel_name).set(int(count))



        except Exception as e:
            print(f"[!] Error during metric fetch/export: {e}")

        time.sleep(10)

if __name__ == "__main__":
    print(f"[Start] Exporter running on port {EXPORTER_PORT}")
    start_http_server(EXPORTER_PORT)
    collect_and_export()
