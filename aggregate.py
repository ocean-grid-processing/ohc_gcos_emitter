"""Read ohc_derive outputs and combine mapped layers into combined-layer time series.

Input is one `ohc_derive` NetCDF per mapped layer, built with `--transforms integral,area
--no-ensemble` (the GCOS deliverable carries no uncertainty). Each provides `ohc_integral(time)`
in TJ (the area-weighted horizontal integral) and the scalar `area_total` in m^2 — exactly the
`d_i * areaTot_i` and `areaTot_i` of the original tseries. Combination is then the weighted sum

    total_L(t)  = sum_i  n_fac_i * integral_i(t)                 (TJ)
    area_L      = area of the shallowest contributor              (m^2, reference/denominator)
    volume_L    = sum_i  n_fac_i * dz_i * area_i                  (m^3)

matching WMO2024_create_tseries_with_uq_for_combined.m. Everything is 1-D; no grids involved.
"""
import xarray as xr


def read_layer(nc):
    """Read one mapped layer's derive output.

    Returns a dict: tag, integral(time) [TJ, float64], area [m^2], top/bottom [m], cp0, rho0,
    product, period.
    """
    ds = xr.open_dataset(nc, decode_times=True)
    a = ds.attrs
    if "ohc_integral" not in ds.data_vars or "area_total" not in ds.data_vars:
        raise SystemExit(
            "%s missing ohc_integral/area_total — build it with "
            "`derive.py ... --transforms integral,area --no-ensemble`" % nc)
    tag = a.get("mapped_layer") or a.get("layer_m")
    if not tag or "_" not in str(tag):
        raise SystemExit("%s has no usable mapped_layer/layer_m attr (got %r)" % (nc, tag))
    top, bottom = (int(x) for x in str(tag).split("_"))
    return {
        "tag": str(tag),
        "integral": ds["ohc_integral"].astype("float64"),   # (time,) TJ
        "area": float(ds["area_total"]),                     # m^2
        "top": top,
        "bottom": bottom,
        "cp0": float(a["cp0"]),
        "rho0": float(a["rho0"]),
        "product": a.get("product", ""),
        "period": a.get("period", ""),
    }


def combine_level(level, by_tag, reference="shallowest"):
    """Combine one Level's contributors from `by_tag` (tag -> read_layer dict).

    Returns {name, low, high, total(time) [TJ], area [m^2], volume [m^3]}.
    `reference` selects the denominator footprint; only "shallowest" is implementable from the
    scalar handoff (the others need per-layer gridded masks — see combine_schema.md).
    """
    if reference != "shallowest":
        raise NotImplementedError(
            "reference_area=%r needs a gridded footprint (per-layer masks); only 'shallowest' "
            "is implemented for the series-level combine." % reference)

    missing = [c.tag for c in level.contributors if c.tag not in by_tag]
    if missing:
        raise SystemExit("level %s: missing contributor derive input(s) %s" % (level.name, missing))

    total = None
    volume = 0.0
    for c in level.contributors:
        layer = by_tag[c.tag]
        bounds_dz = layer["bottom"] - layer["top"]
        if abs(c.dz - bounds_dz) > 1e-9:
            raise SystemExit(
                "dz mismatch for %s in level %s: config dz=%g but layer bounds give %g"
                % (c.tag, level.name, c.dz, bounds_dz))
        term = c.n_fac * layer["integral"]
        total = term if total is None else total + term       # xarray aligns on the time coord
        volume += c.n_fac * c.dz * layer["area"]

    area = by_tag[level.contributors[0].tag]["area"]           # reference = shallowest contributor
    return {
        "name": level.name,
        "low": level.low,
        "high": level.high,
        "total": total,
        "area": area,
        "volume": volume,
    }
