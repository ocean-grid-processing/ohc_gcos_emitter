"""Read ohc_derive outputs and combine mapped layers into combined-layer time series.

Input is one `ohc_derive` NetCDF per mapped layer, built with `--transforms integral,area`. Each
provides `ohc_integral(time)` in TJ (the area-weighted horizontal integral) and the scalar
`area_total` in m^2 — exactly the `d_i * areaTot_i` and `areaTot_i` of the original tseries.
Combination is then the weighted sum

    total_L(t)  = sum_i  n_fac_i * integral_i(t)                 (TJ)
    area_L      = area of the shallowest contributor              (m^2, reference/denominator)
    volume_L    = sum_i  n_fac_i * dz_i * area_i                  (m^3)

matching WMO2024_create_tseries_with_uq_for_combined.m. Everything is 1-D; no grids involved.

**Uncertainty (optional).** If the derive inputs were built with the ensemble on, each carries
`ohc_integral_ens` (member, time). Per layer we form the ensemble std of the *yearly* integral —
yearly-mean per member, then std across members (ddof=1) — and combine those with the same
weights: `total_sd_L(y) = sum_i n_fac_i * integral_sd_yearly_i(y)`. This is the linear "worst-case"
sum (layers treated as fully correlated) of `create_eval_string_std`. All-or-nothing: a level gets
an SD only if every contributor carries the ensemble.
"""
import xarray as xr


def read_layer(nc):
    """Read one mapped layer's derive output.

    Returns a dict: tag, integral(time) [TJ, float64], area [m^2], top/bottom [m], cp0, rho0,
    product, period, and `integral_sd_yearly` — the ensemble std of the yearly integral (year,)
    [TJ] if `ohc_integral_ens` is present (ensemble build), else None.
    """
    ds = xr.open_dataset(nc, decode_times=True)
    a = ds.attrs
    if "ohc_integral" not in ds.data_vars or "area_total" not in ds.data_vars:
        raise SystemExit(
            "%s missing ohc_integral/area_total — build it with "
            "`derive.py ... --transforms integral,area`" % nc)
    tag = a.get("mapped_layer") or a.get("layer_m")
    if not tag or "_" not in str(tag):
        raise SystemExit("%s has no usable mapped_layer/layer_m attr (got %r)" % (nc, tag))
    top, bottom = (int(x) for x in str(tag).split("_"))

    integral_sd_yearly = None
    if "ohc_integral_ens" in ds.data_vars:
        ens = ds["ohc_integral_ens"].astype("float64")       # (member, time) TJ
        # spread of the YEARLY integral: yearly-mean per member, then std across members (ddof=1)
        integral_sd_yearly = (ens.groupby("time.year").mean("time")
                                 .std("member", ddof=1))       # (year,) TJ

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
        "integral_sd_yearly": integral_sd_yearly,            # (year,) TJ or None
    }


def uncertainty_available(needed, by_tag):
    """Whether the combined SD can be built: True if *every* needed tag carries an ensemble SD,
    False if none do. Raises SystemExit on a partial mix — an SD needs all its contributors, so a
    missing one is a loud error, not a silently dropped term.
    """
    have = [t for t in needed if by_tag[t].get("integral_sd_yearly") is not None]
    if not have:
        return False
    if len(have) != len(needed):
        missing = [t for t in needed if by_tag[t].get("integral_sd_yearly") is None]
        raise SystemExit(
            "uncertainty: ensemble present for %s but missing for %s — re-run derive on the "
            "missing layer(s) with the ensemble on (drop --no-ensemble), or none of the combined "
            "layers can get error bars." % (have, missing))
    return True


def combine_level(level, by_tag, reference="shallowest"):
    """Combine one Level's contributors from `by_tag` (tag -> read_layer dict).

    Returns {name, low, high, total(time) [TJ], area [m^2], volume [m^3], total_sd_yearly}.
    `total_sd_yearly` is the linear n_fac-weighted sum of the contributors' yearly integral SDs
    (year,) [TJ] if *every* contributor carries one, else None.
    `reference` selects the denominator footprint; only "shallowest" is implementable from the
    scalar handoff (the others need per-layer gridded masks — see the README).
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
    total_sd_yearly = None
    have_all_sd = all(by_tag[c.tag].get("integral_sd_yearly") is not None
                      for c in level.contributors)
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
        if have_all_sd:                                        # worst-case linear SD sum
            sd_term = c.n_fac * layer["integral_sd_yearly"]
            total_sd_yearly = sd_term if total_sd_yearly is None else total_sd_yearly + sd_term

    area = by_tag[level.contributors[0].tag]["area"]           # reference = shallowest contributor
    return {
        "name": level.name,
        "low": level.low,
        "high": level.high,
        "total": total,
        "area": area,
        "volume": volume,
        "total_sd_yearly": total_sd_yearly,                    # (year,) TJ or None
    }
