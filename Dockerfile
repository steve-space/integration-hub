FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY legacy_warehouse ./legacy_warehouse
COPY legacy_pricing ./legacy_pricing

# Same image is used for all three services (hub, warehouse, pricing) —
# docker-compose.yml picks which app to actually run via `command:`.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
