# Enriching Middleware for Acexy Metrics
![enriched-light](https://github.com/user-attachments/assets/22658f9e-773e-48fc-83f6-cc719868dfed)

> [!WARNING]  
> For this to work my fork of Acexy has to be used as the main one doesn't expose logs in a file
> You can get it here https://github.com/krinkuto11/acexy

This Middleware takes these two metrics from an MTail export with Prometheus format...
```
clients_per_stream{prog="stream_stats.mtail",stream_ID="<Stream ID>"} <Gauge>
```
```
stream_by_user{prog="stream_stats.mtail",stream_ID="<Stream ID",user="<User>"} <Gauge>
```
...then queries the Acestream Scraper API and gets the TV Channel that the Stream is part of.
The resulting metrics are:
```
active_streams_by_channel{channel_name="<Channel Name>"} <Gauge>
```
```
streams_by_user{channel_name="<Channel Name",user="<User>"} <Gauge>
```
## MTail Config

The MTail Config used to get this metrics from the Acexy logs parses the following events:

**Stream Start:**
```
YYYY/MM/DD HH:MM:SS INFO Client connected stream="{id: <Stream ID>}" clients=<Client Number> user=<User>
```
**Stream Stop***
```
YYYY/MM/DD HH:MM:SS INFO Client stopped stream="{id: <Stream ID>}" clients=<Client Number> user=<User>
```
**Stream Error (Stream stops)**
```
YYYY/MM/DD HH:MM:SS ERROR Failed to start stream stream="{id: <Stream ID>}" error="<Error message>" user=<User>
```
Config file `stream_stats.mtail`:
```MTail
# Exported metrics
gauge clients_per_stream by stream_ID
gauge stream_by_user by user, stream_ID

# Hidden metric to store the most recent client count per stream
hidden gauge last_clients_count by stream_ID

# Timestamp parser decorator (YYYY/MM/DD HH:MM:SS)
def logtime {
  /^(?P<ts>\d{4}\/\d{2}\/\d{2} \d{2}:\d{2}:\d{2})/ {
    strptime($ts, "2006/01/02 15:04:05")
    next
  }
}

@logtime {
  # Cliente se conecta a un stream
  /Client connected stream="\{id: (?P<stream_ID>[a-f0-9]+)\}" clients=(?P<clients>\d+) user=(?P<user>\w+)/ {
    clients_per_stream[$stream_ID] = int($clients)
    last_clients_count[$stream_ID] = int($clients)
    stream_by_user[$user][$stream_ID] = 1
  }

  # Cliente se desconecta de un stream
  /Client stopped stream="\{id: (?P<stream_ID>[a-f0-9]+)\}" clients=(?P<clients>\d+) user=(?P<user>\w+)/ {
    clients_per_stream[$stream_ID] = int($clients)
    last_clients_count[$stream_ID] = int($clients)
    stream_by_user[$user][$stream_ID] = 0
  }
  # Hay un error en el stream
  /Failed to start stream stream="\{id: (?P<stream_ID>[a-f0-9]+)\}".*user=(?P<user>\S+)/ {
    clients_per_stream[$stream_ID] = 0
    last_clients_count[$stream_ID] = 0
    stream_by_user[$user][$stream_ID] = 0
  }  
}
```



