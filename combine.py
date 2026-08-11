#!/usr/bin/env python3
"""Combine mapped-layer ohc_derive outputs into the GCOS/WMO-report deliverable.

    python combine.py DERIVE_*.nc --gcos-tag "GCOS 2026 OP20260127b" \
        [--levels 0_300,0_700,700_2000,0_2000] [--ref-window 2005:2024] \
        [--j-to-zj 1e-21] [--reference shallowest] [--collaborators STR] [--out DIR]

Each DERIVE_*.nc is one mapped layer's ohc_derive output, built with
`derive.py ... --transforms integral,area` (add `--keep-members integral` for error bars). The
combined layers, their contributors, and the n_fac/dz weights live in layers.py (edit there to
add/remove layers; `--levels` selects a subset). See the README.

Requires: numpy, xarray>=2024.10, netCDF4.
"""
import argparse
import os

import layers as layers_mod
import aggregate
import gcos


def parse_window(s):
    a, b = (int(x) for x in s.replace("-", ":").split(":"))
    return (a, b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("derive", nargs="+", help="ohc_derive .nc files, one per mapped layer")
    ap.add_argument("--levels", default=None,
                    help="comma list of combined levels to emit (default: all in layers.py)")
    ap.add_argument("--ref-window", default="2005:2024",
                    help="baseline-mean window YEAR0:YEAR1 removed from the yearly series")
    ap.add_argument("--gcos-tag", required=True, help='e.g. "GCOS 2026 OP20260127b"')
    ap.add_argument("--collaborators", default="LocalGP by Giglio, Sukianto, Kuusela, Mills")
    ap.add_argument("--j-to-zj", default=1e-21, type=float,
                    help="OHCA_ZJ scale; 1e-21 = true zettajoules (default). Pass 1e-15 to "
                         "byte-match the original file, whose _ZJ column is actually petajoules.")
    ap.add_argument("--reference", default="shallowest",
                    help="combined-layer reference area (only 'shallowest' implemented)")
    ap.add_argument("--provenance-tag", default=None,
                    help="provenance id written to the header (e.g. the localGP run + component "
                         "git hashes)")
    ap.add_argument("--provenance-link", default=None,
                    help="URL/path to the provenance record for this output")
    ap.add_argument("--out", default=".")
    args = ap.parse_args()

    names = None if not args.levels else [s.strip() for s in args.levels.split(",")]
    levels = layers_mod.select_levels(names)
    ref_window = parse_window(args.ref_window)

    by_tag = {}
    cp0 = rho0 = None
    for nc in args.derive:
        layer = aggregate.read_layer(nc)
        by_tag[layer["tag"]] = layer
        if cp0 is None:
            cp0, rho0 = layer["cp0"], layer["rho0"]
        elif (cp0, rho0) != (layer["cp0"], layer["rho0"]):
            raise SystemExit("cp0/rho0 differ across inputs (%s vs %s)"
                             % ((cp0, rho0), (layer["cp0"], layer["rho0"])))

    need = layers_mod.required_tags(levels)
    absent = [t for t in need if t not in by_tag]
    if absent:
        raise SystemExit("missing derive inputs for contributor layer(s): %s "
                         "(needed by %s)" % (absent, [lv.name for lv in levels]))

    # Uncertainty is all-or-nothing across the needed contributors (raises on a partial mix).
    uncertainty = aggregate.uncertainty_available(need, by_tag)

    combined = [aggregate.combine_level(lv, by_tag, reference=args.reference) for lv in levels]
    ds = gcos.build_dataset(combined, cp0, rho0, ref_window, args.j_to_zj,
                            args.gcos_tag, args.collaborators)
    if args.provenance_tag is not None:
        ds.attrs["provenance_tag"] = args.provenance_tag       # localGP run + component git hashes
    if args.provenance_link is not None:
        ds.attrs["provenance_link"] = args.provenance_link     # URL/path to the provenance record

    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, gcos.filename(args.gcos_tag, ref_window))
    ds.to_netcdf(path, engine="netcdf4")
    print("wrote", path)
    print("levels:", ", ".join(lv.name for lv in levels))
    print("uncertainty:", "on — _sd columns written" if uncertainty else "off (mean-only inputs)")


if __name__ == "__main__":
    main()
