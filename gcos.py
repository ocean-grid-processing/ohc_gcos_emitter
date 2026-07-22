"""GCOS/WMO-report export: yearly baseline anomaly + the three quantities.

Mirrors WMO2024_create_tseries_to_Karina_for_WMOreport.m. Per combined layer, from the combined
`total(t)` (TJ), `area` (m^2), `volume` (m^3): take the annual mean of the density (total/area),
subtract the baseline-window mean, and express that anomaly three ways.

    OHCA_J_m2_oc(y)      = d_yr(y) - mean(d_yr over baseline)          [J/m^2]
    OHCA_ZJ(y)           = j_to_zj * area * OHCA_J_m2_oc(y)            [see note on j_to_zj]
    vol_ave_temp_anom(y) = area * OHCA_J_m2_oc(y) / (cp0*rho0*volume) [degC]

The anomaly is a large-mean cancellation (absolute OHC minus its baseline mean), so it is done in
float64. Our internal OHC is TJ/m^2 while the original is J/m^2, so densities are scaled by 1e12
at this boundary to land on the original's numbers.

NOTE on j_to_zj: the original uses 1e-15, which is J->PJ (petajoules), not J->ZJ (that would be
1e-21) — so its `_ZJ` column is actually in petajoules (1e6x the true ZJ). We default to 1e-21 so
`OHCA_ZJ` is genuine, correctly-labelled zettajoules (a deliberate correction, per project
decision). Pass 1e-15 to byte-match the collaborator's original file on that column.
"""
import numpy as np
import xarray as xr


def _yearly(series):
    """Monthly (time,) series -> calendar-year mean (year,), float64."""
    return series.astype("float64").groupby("time.year").mean("time")


def build_dataset(combined, cp0, rho0, baseline, j_to_zj, gcos_tag, collaborators):
    """Assemble the GCOS Dataset from a list of combine_level() results.

    `baseline` is (year0, year1) inclusive. Returns an xr.Dataset with dim `years` and, per
    level, `GCOS_<lo>_<hi>_{OHCA_J_m2_oc, OHCA_ZJ, vol_ave_temp_anom}` plus GCOS_area/GCOS_volume
    attributes and a global `description`.
    """
    b0, b1 = baseline
    years = None
    data_vars = {}
    for cl in combined:
        d_yr = _yearly(cl["total"] / cl["area"])                 # TJ/m^2, yearly, float64
        yrs = d_yr["year"].values.astype("int64")
        if years is None:
            years = yrs
        elif not np.array_equal(yrs, years):
            raise SystemExit("year axes differ across levels (%s vs %s)" % (yrs, years))

        base = d_yr.sel(year=slice(b0, b1)).mean("year")
        anom_jm2 = (d_yr - base).values * 1e12                   # TJ/m^2 -> J/m^2, float64
        area, vol = cl["area"], cl["volume"]
        tag = "%04d_%04d" % (cl["low"], cl["high"])

        data_vars["GCOS_%s_OHCA_J_m2_oc" % tag] = xr.DataArray(
            anom_jm2, dims=("years",), attrs={"GCOS_area": area})
        data_vars["GCOS_%s_OHCA_ZJ" % tag] = xr.DataArray(
            j_to_zj * area * anom_jm2, dims=("years",), attrs={"GCOS_area": area})
        data_vars["GCOS_%s_vol_ave_temp_anom" % tag] = xr.DataArray(
            area * anom_jm2 / (cp0 * rho0 * vol), dims=("years",), attrs={"GCOS_volume": vol})

    out = xr.Dataset(data_vars, coords={"years": ("years", years.astype("float64"))})
    out.attrs["description"] = "%s, %s" % (gcos_tag, collaborators)
    return out


def filename(gcos_tag, baseline):
    """Original convention: <gcos_tag lowercased, spaces removed>_LocalGP_Giglio_etal_using<b0>_<b1>baseline.nc"""
    b0, b1 = baseline
    return "%s_LocalGP_Giglio_etal_using%d_%dbaseline.nc" % (
        gcos_tag.lower().replace(" ", ""), b0, b1)
