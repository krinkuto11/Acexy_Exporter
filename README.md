# Acexy Exporter and Enricher for Prometheus Metrics
<img width="621" height="221" alt="diagram_exporter" src="https://github.com/user-attachments/assets/40dd6e0e-9adb-428a-a913-0a585441913e" />

> [!WARNING]  
> The main Acexy fork doesn't expose stream IDs and Users. Until this is added to the main branch you must use my own fork.
> You can get it here https://github.com/krinkuto11/acexy

This Middleware receives the stats from the API in the following format
```
{"streams":1,"users":["user1","user2"],"users_by_stream":{"{id: <id>}":["user1","user2"]}}```
```

...then queries the Acestream Scraper API and gets the TV Channel that the Stream is part of.
The resulting metrics are:
```
active_streams_by_channel{channel_name="<Channel Name>"} <Gauge>
```
```
streams_by_user{channel_name="<Channel Name",user="<User>"} <Gauge>
```
## Deployment
Use the following docker-compose project:
```
version: '3.8'

services:
  enrichment_exporter:
    image: ghcr.io/krinkuto11/enrichment_exporter:latest
    container_name: enrichment_exporter
    ports:
      - "9101:9101"
    environment:
      - CHANNEL_LOOKUP_URL=${ACESTREAM_SCRAPER_URL}/api/tv-channels/find-matches
      - PGID=1000
      - PUID=1000
      - ACEXY_API=${ACEXY_URL}/ace/status
```




