FROM python:3.11-slim

WORKDIR /app
COPY enrichment_exporter.py .

RUN pip install --no-cache-dir prometheus_client requests

CMD ["python", "enrichment_exporter.py"]
