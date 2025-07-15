import time
import re
import requests
import os
from prometheus_client import start_http_server, Gauge
from collections import defaultdict

ACEXY_API = os.environ.get("ACEXY_API", "http://localhost:8080/ace/status")
CHANNELS_URL = os.environ.get("CHANNELS_URL", "http://localhost:8000/api/tv-channels/")
ACESTREAMS_URL_TEMPLATE = os.environ.get("ACESTREAMS_URL_TEMPLATE", "http://localhost:8000/api/tv-channels/{}/acestreams")
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
    refresh_interval = 60 * 5
    last_refresh = 0

    while True:
        now = time.time()
        if now - last_refresh > refresh_interval or not acestream_to_channel:
            build_acestream_mapping()
            last_refresh = now

        try:
            print("[Fetch] Requesting usage data from new API...")
            resp = requests.get(ACEXY_API, timeout=5)
            data = resp.json()

            active_streams_by_channel.clear()
            streams_by_user.clear()

            users_by_stream = data.get("users_by_stream", {})
            user_channel_counts = defaultdict(int)

            for raw_stream_id, users in users_by_stream.items():
                match = re.search(r'[a-f0-9]{40}', raw_stream_id)
                if not match:
                    continue
                stream_id = match.group(0)
                channel_name = get_channel_name_from_stream_id(stream_id)

                active_streams_by_channel.labels(channel_name).inc(1)

                for user in users:
                    key = (user, channel_name)
                    user_channel_counts[key] = max(user_channel_counts[key], 1)

            for (user, channel_name), count in user_channel_counts.items():
                streams_by_user.labels(user=user, channel_name=channel_name).set(count)
                print(f"[UserMetric] User: {user}, Channel: {channel_name}, Clients: {count}")


        except Exception as e:
            print(f"[!] Error while collecting usage data: {e}")

        time.sleep(10)

if __name__ == "__main__":
    print(f"[Start] Exporter running on port {EXPORTER_PORT}")
    start_http_server(EXPORTER_PORT)
    collect_and_export()
