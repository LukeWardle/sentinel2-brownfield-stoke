# Dockerfile — SiteSignal pipeline runtime (P0-5).
# rasterio and pyproj manylinux wheels bundle GDAL/PROJ, so the slim base
# image needs no system geo libraries.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY scripts/ scripts/
COPY migrations/ migrations/

# DATABASE_URL, COPERNICUS_USERNAME, COPERNICUS_PASSWORD are supplied at
# run time (docker compose env_file / -e flags) — never baked into the image.
CMD ["python", "-m", "src.main", "--help"]
