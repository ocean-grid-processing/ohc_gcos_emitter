import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def months(n, start="2004-01"):
    """A monthly datetime64 axis of length n."""
    return pd.date_range(start, periods=n, freq="MS").values


def make_layer(tag, top, bottom, area, integral_values, cp0=3989.244, rho0=1030.0):
    """A read_layer()-shaped dict for combine tests (no file IO)."""
    t = months(len(integral_values))
    integ = xr.DataArray(np.asarray(integral_values, dtype="float64"),
                         dims=("time",), coords={"time": t})
    return {"tag": tag, "integral": integ, "area": float(area),
            "top": top, "bottom": bottom, "cp0": cp0, "rho0": rho0,
            "product": "TEST", "period": "2004_2004"}


def monthly_total(area, yearly_density):
    """Monthly `total` (TJ) for a level: density (TJ/m^2) held constant within each year, x area."""
    times, vals = [], []
    for y, d in yearly_density.items():
        t = pd.date_range("%d-01" % y, periods=12, freq="MS").values
        times.extend(list(t))
        vals.extend([d * area] * 12)
    return xr.DataArray(np.asarray(vals, dtype="float64"),
                        dims=("time",), coords={"time": np.asarray(times)})
