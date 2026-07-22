# Test environment for ohc_derive — deps only, no code copied in (mount the source at runtime).
FROM python:3.12-slim

# numpy/xarray/netCDF4 are the runtime deps; pandas comes with xarray; pytest to run the suite.
RUN pip install --no-cache-dir numpy "xarray>=2024.10" netCDF4 pytest

WORKDIR /app
CMD ["pytest", "-q"]

# Build:
#   docker build -f Dockerfile.test -t ohc_derive_test ohc_pipeline/ohc_derive
#
# Run (mount the ohc_derive source at /app; iterate on the host, no rebuild):
#   docker run --rm -v "$PWD/ohc_pipeline/ohc_derive":/app ohc_derive_test
#
# Or from inside ohc_derive/:
#   docker run --rm -v "$PWD":/app ohc_derive_test
#
# Pass pytest args, e.g. one file or verbose:
#   docker run --rm -v "$PWD":/app ohc_derive_test pytest -v tests/test_transforms.py
