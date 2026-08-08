#!/usr/bin/env python3
"""Compare our GCOS deliverable .nc against https://zenodo.org/records/18187866, variable by variable.

    python parity.py OURS.nc THEIRS.nc [--rtol 1e-6]

For every shared variable it reports the max absolute and max relative difference and a pass/fail
against --rtol, and it compares the GCOS_area / GCOS_volume attributes. It handles the two known,
intentional differences:

  * OHCA_ZJ (and its OHCA_ZJ_sd companion) — we default to *true* zettajoules (j_to_zj = 1e-21)
    while the original used 1e-15 (which is actually petajoules), so both `_ZJ` columns are 1e6x
    smaller. The script detects this and reports the reconciled (x1e6) comparison for them.
  * Extra levels — if either file has a level the other lacks (e.g. our aspirational 0_1000),
    it's listed as ours-only / theirs-only and skipped rather than counted as a mismatch.

Requires: xarray, netCDF4, numpy.
"""
import argparse

import numpy as np
import xarray as xr


def maxdiff(a, b):
    """(max |a-b|, max |a-b| / max|b|) over finite entries."""
    a = np.asarray(a, dtype="float64")
    b = np.asarray(b, dtype="float64")
    ad = float(np.nanmax(np.abs(a - b)))
    denom = float(np.nanmax(np.abs(b))) or 1.0
    return ad, ad / denom


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ours")
    ap.add_argument("theirs")
    ap.add_argument("--rtol", type=float, default=1e-6)
    args = ap.parse_args()

    o = xr.open_dataset(args.ours)
    t = xr.open_dataset(args.theirs)

    print("dims  ours:", dict(o.sizes), " theirs:", dict(t.sizes))
    if "years" in o and "years" in t:
        same = np.array_equal(o["years"].values, t["years"].values)
        print("years identical:", bool(same),
              "" if same else "  (ours %s.. theirs %s..)" % (o["years"].values[:1], t["years"].values[:1]))

    shared = sorted(set(o.data_vars) & set(t.data_vars) - {"years"})
    only_o = sorted(set(o.data_vars) - set(t.data_vars))
    only_t = sorted(set(t.data_vars) - set(o.data_vars))

    worst = 0.0
    print("\n%-38s %11s %10s  %s" % ("variable", "max|Δ|", "rel", "notes"))
    for v in shared:
        ad, rd = maxdiff(o[v].values, t[v].values)
        note = ""
        if "_OHCA_ZJ" in v:                        # reconcile true-ZJ (ours) vs PJ (theirs); value + _sd
            ad6, rd6 = maxdiff(o[v].values * 1e6, t[v].values)
            if rd6 < rd:
                ad, rd, note = ad6, rd6, "x1e6 true-ZJ↔PJ"
        for attr in ("GCOS_area", "GCOS_volume"):   # attribute parity
            if attr in o[v].attrs and attr in t[v].attrs:
                tv = float(t[v].attrs[attr])
                ra = abs(float(o[v].attrs[attr]) - tv) / (abs(tv) or 1.0)
                note += "  %s rel=%.1e" % (attr, ra)
        worst = max(worst, rd)
        print("[%s] %-38s %11.3e %10.2e  %s"
              % ("ok " if rd <= args.rtol else "OFF", v, ad, rd, note))

    if only_o:
        print("\nours-only (skipped):", only_o)
    if only_t:
        print("theirs-only (MISSING from ours):", only_t)

    print("\nWORST relative difference over shared variables: %.2e  (rtol=%g)" % (worst, args.rtol))
    ok = worst <= args.rtol and not only_t
    print("RESULT:", "PASS" if ok else "REVIEW")


if __name__ == "__main__":
    main()
