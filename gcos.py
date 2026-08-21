#!/usr/bin/env python3
"""GCOS/WMO-report packaging: ohc_derive blobs -> one combined GCOS deliverable.

The factory has done the analysis — the n_fac cross-layer combine, the annual mean, and the OHCA
baseline window. Each per-level blob carries `ohca` (annual anomaly, basin-integrated TJ, referenced
to its baseline window) plus `area_m2`, `volume_m3`, `cp0`, `rho0`, and the `time_window` it was built
with. This step packages one file spanning every level, expressing each level's anomaly three ways:

    GCOS_<lo>_<hi>_OHCA_J_m2_oc(y)      = ohca / area * 1e12                       [J/m^2]
    GCOS_<lo>_<hi>_OHCA_ZJ(y)           = j_to_zj * area * OHCA_J_m2_oc            [ZJ, see note]
    GCOS_<lo>_<hi>_vol_ave_temp_anom(y) = area * OHCA_J_m2_oc / (cp0*rho0*volume)  [degC]

Each gets a `*_sd` companion when the blob carried the ensemble — the factory's `ohca_sd` pushed
through the same deterministic factors. Note that `ohca_sd` is the spread of the *anomaly* members
(each demeaned by its own window), the factory's convention; the retired emitter used the spread of
the absolute yearly value instead.

NOTE on j_to_zj: the original uses 1e-15, which is J->PJ (petajoules), not J->ZJ (1e-21) — so its
`_ZJ` column is actually petajoules. We default to 1e-21 for genuine zettajoules (a deliberate
correction); pass 1e-15 to byte-match the collaborator's original file on that column.
"""
import argparse
import os

import numpy as np
import xarray as xr

J_PER_TJ = 1e12


def _band(level):
    """A level name "lo_hi" -> the zero-padded GCOS band token "0000_0300"."""
    lo, hi = (int(x) for x in level.split("_"))
    return "%04d_%04d" % (lo, hi)


def build_dataset(blobs, j_to_zj, tag, provenance_link):
    """The combined GCOS Dataset over `years`, three views per level, from the factory blobs.

    Every blob must share the year axis, the baseline window, and cp0/rho0 (the deliverable is one
    consistent set of levels); mismatches raise.
    """
    years = window = cp0 = rho0 = None
    data_vars = {}
    for blob in blobs:
        yrs = blob["ohca"]["year"].values.astype("int64")
        if years is None:
            years, window = yrs, blob.attrs["time_window"]
            cp0, rho0 = float(blob.attrs["cp0"]), float(blob.attrs["rho0"])
        else:
            if not np.array_equal(yrs, years):
                raise SystemExit("year axes differ across levels (at %s)" % blob.attrs["level"])
            if blob.attrs["time_window"] != window:
                raise SystemExit("baseline windows differ across levels (%s vs %s)"
                                 % (blob.attrs["time_window"], window))
            if (float(blob.attrs["cp0"]), float(blob.attrs["rho0"])) != (cp0, rho0):
                raise SystemExit("cp0/rho0 differ across levels (at %s)" % blob.attrs["level"])

        area, vol = float(blob.attrs["area_m2"]), float(blob.attrs["volume_m3"])
        band = _band(blob.attrs["level"])
        anom_jm2 = blob["ohca"].values / area * J_PER_TJ         # TJ -> J/m^2, float64

        data_vars["GCOS_%s_OHCA_J_m2_oc" % band] = xr.DataArray(
            anom_jm2, dims=("years",), attrs={"units": "J/m2", "GCOS_area": area})
        data_vars["GCOS_%s_OHCA_ZJ" % band] = xr.DataArray(
            j_to_zj * area * anom_jm2, dims=("years",), attrs={"units": "ZJ", "GCOS_area": area})
        data_vars["GCOS_%s_vol_ave_temp_anom" % band] = xr.DataArray(
            area * anom_jm2 / (cp0 * rho0 * vol), dims=("years",),
            attrs={"units": "degC", "GCOS_volume": vol})

        if "ohca_sd" in blob:
            jm2_sd = blob["ohca_sd"].values / area * J_PER_TJ
            note = "worst-case ensemble 1-sigma: n_fac-weighted sum of the per-constituent SDs"
            data_vars["GCOS_%s_OHCA_J_m2_oc_sd" % band] = xr.DataArray(
                jm2_sd, dims=("years",), attrs={"units": "J/m2", "GCOS_area": area, "comment": note})
            data_vars["GCOS_%s_OHCA_ZJ_sd" % band] = xr.DataArray(
                j_to_zj * area * jm2_sd, dims=("years",),
                attrs={"units": "ZJ", "GCOS_area": area, "comment": note})
            data_vars["GCOS_%s_vol_ave_temp_anom_sd" % band] = xr.DataArray(
                area * jm2_sd / (cp0 * rho0 * vol), dims=("years",),
                attrs={"units": "degC", "GCOS_volume": vol, "comment": note})

    out = xr.Dataset(data_vars, coords={"years": ("years", years.astype("float64"))})
    out.attrs["time_window"] = window
    out.attrs["provenance_tag"] = tag
    if provenance_link is not None:
        out.attrs["provenance_link"] = provenance_link
    return out


def filename(tag, window):
    """gcos_<tag>_<window>.nc — window is the baseline label carried by the blobs (e.g. 2005_2024)."""
    return "gcos_%s_%s.nc" % (tag, window.replace("-", "_"))


def main():
    ap = argparse.ArgumentParser(description="GCOS packaging: ohc_derive blobs -> GCOS deliverable")
    ap.add_argument("blobs", nargs="+", help="ohc_derive outputs, one per synthetic level")
    ap.add_argument("--tag", required=True, help="provenance tag: filename token + provenance_tag attr")
    ap.add_argument("--provenance-link", default=None, help="URL/path to the provenance record")
    ap.add_argument("--j-to-zj", default=1e-21, type=float,
                    help="OHCA_ZJ scale; 1e-21 = true zettajoules (default). Pass 1e-15 to byte-match "
                         "the original file, whose _ZJ column is actually petajoules.")
    ap.add_argument("--out", default=".")
    cfg = ap.parse_args()
    cfg.tag = "".join(cfg.tag.split())                           # whitespace-stripped, otherwise verbatim

    blobs = [xr.open_dataset(p) for p in cfg.blobs]
    for p, b in zip(cfg.blobs, blobs):
        if "ohca" not in b.data_vars:
            raise SystemExit("%s carries no ohca; run ohc_derive with --quantities ohca" % p)
        if b.attrs.get("time_window", "all") == "all":
            raise SystemExit("%s has no baseline window; GCOS needs ohc_derive run with --time-window" % p)
        if "cp0" not in b.attrs or "rho0" not in b.attrs:
            raise SystemExit("%s lacks cp0/rho0; GCOS needs the physical constants" % p)

    out = build_dataset(blobs, cfg.j_to_zj, cfg.tag, cfg.provenance_link)
    os.makedirs(cfg.out, exist_ok=True)
    dest = os.path.join(cfg.out, filename(cfg.tag, out.attrs["time_window"]))
    out.to_netcdf(dest, engine="netcdf4")
    print("wrote", dest)


if __name__ == "__main__":
    main()
