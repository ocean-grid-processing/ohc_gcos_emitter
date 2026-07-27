FROM python:3.12-slim

RUN pip install --no-cache-dir numpy "xarray>=2024.10" netCDF4 pytest

WORKDIR /app

