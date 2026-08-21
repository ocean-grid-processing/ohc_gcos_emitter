# ohc_gcos_emitter

`ohc_gcos_emitter` packages `ohc_derive` blobs into the GCOS/WMO-report deliverable — one NetCDF
spanning every level, `gcos_<tag>_<b0>_<b1>.nc`, where `<tag>` is the provenance tag
(whitespace-stripped, otherwise verbatim) and `<b0>_<b1>` are the baseline-window years.

```
ohc_ingest ─▶ publish ─▶ ohc_derive (--quantities ohca --time-window 2005:2024) ─▶ ohc_gcos_emitter ─▶ GCOS .nc
```

The analysis is all upstream now. `ohc_derive` does the `n_fac` cross-layer combine, the annual mean,
and the OHCA baseline window. Each per-level blob hands over `ohca` — the annual OHC anomaly,
basin-integrated (TJ), already referenced to the baseline window — plus `area_m2`, `volume_m3`,
`cp0`, `rho0`, and the `time_window` it was built with. This emitter is the packaging: express each
level's anomaly three ways and assemble one file across levels.

## What it computes

Per level, from `ohca` (TJ) and that level's `area` / `volume` / `cp0` / `rho0`:

```
GCOS_<lo>_<hi>_OHCA_J_m2_oc(y)      = ohca / area * 1e12                       # J/m²
GCOS_<lo>_<hi>_OHCA_ZJ(y)           = j_to_zj * area * OHCA_J_m2_oc            # ZJ (see below)
GCOS_<lo>_<hi>_vol_ave_temp_anom(y) = area * OHCA_J_m2_oc / (cp0*rho0*volume)  # degC
```

The baseline subtraction that defines the anomaly already happened in the factory (`--time-window`);
this step never re-subtracts. `<lo>_<hi>` are the level's dbar bounds, zero-padded
(`GCOS_0000_2000_…`). Every level lands in one file on a shared `years` axis, and the emitter errors
if the levels disagree on the year axis, the baseline window, or cp0/rho0.

> **OHCA_ZJ is true zettajoules** (`--j-to-zj`, default `1e-21`). The original scaled by `1e-15` =
> J→**peta**joules, so its `_ZJ` column is mislabelled and 10⁶× too large. We emit real ZJ; pass
> `--j-to-zj 1e-15` to byte-match the original on that one column. The other two views are unaffected.

**Error bars.** If the derive run kept the ensemble, each blob carries `ohca_sd`, and every view gets
a `*_sd` companion — the factory's yearly anomaly SD pushed through the same deterministic factors.
Note the SD is the spread of the **anomaly** members (each demeaned by its own window), the factory's
convention; the retired emitter used the spread of the absolute yearly value.

## Building the input

`ohc_gcos_emitter` consumes one `ohc_derive` blob per synthetic level, built with the GCOS baseline
window and the ensemble on:

```bash
python ../ohc_derive/run.py OHC_<constituents>.nc \
    --level 0_2000 --bathy etopo60.nc --quantities ohca \
    --time-window 2005:2024 --tag <tag> --out <dir>
```

Each blob **must** carry:

- data var **`ohca`** (annual anomaly, TJ), and **`ohca_sd`** for the `_sd` columns (present when the
  derive run kept the ensemble);
- attrs **`area_m2`**, **`volume_m3`**, **`cp0`**, **`rho0`**, **`level`**, and **`time_window`** — a
  real window, not `"all"`, since a GCOS file is defined by its baseline.

The emitter errors on any missing piece. `cp0`/`rho0` ride in from the submissions' attributes and
must agree across the levels. `--quantities ohca` is all GCOS needs — the three views are all derived
from it.

## Usage

### Environment

See `Dockerfile` for a containerized environment; build the same into an anaconda env on blanca for
running on the CU cluster.

### Test

```bash
docker image build -t ohc_gcos_emitter:test .
docker container run -v $(pwd):/app ohc_gcos_emitter:test pytest
```

End-to-end validation is a separate exercise — reproduce
[this 2026 result](https://zenodo.org/records/18187866) and diff it (match `GCOS_area`/`GCOS_volume`
first, then the series) with [`parity.py`](parity.py).

### Run

```bash
python gcos.py derive_<tag>_*.nc --tag GCOS-2026-OP20260127b [--provenance-link URL] [--j-to-zj 1e-21] [--out DIR]
```

See [`gcos.slurm`](gcos.slurm) for a real run.

#### gcos.py options

| option | default | effect |
|---|---|---|
| `derive_*.nc` (positional, 1+) | *(required)* | `ohc_derive` blobs, one per synthetic level; each must carry `ohca` and a real `time_window`. They all go into one file. |
| `--tag` | *(required)* | provenance tag (e.g. `GCOS-2026-OP20260127b`): the filename token (whitespace-stripped, case preserved, no other munging) and the `provenance_tag` header attr. |
| `--provenance-link` | *(none)* | URL/path to the provenance record; written to the `provenance_link` attr. |
| `--j-to-zj` | `1e-21` | `OHCA_ZJ` scale — `1e-21` = true zettajoules; `1e-15` byte-matches the original's (mislabelled petajoule) `_ZJ` column. |
| `--out` | `.` | output directory (created if absent). |

The baseline `<b0>_<b1>` in the filename comes from the blobs' `time_window` — no `--ref-window`.
Level selection is by which blobs you pass — no `--levels`. The reference area is the factory
footprint (the shallowest wet area) — no `--reference`.

## Notes

- **Reference area = the factory footprint** — the cells the level actually holds water in (the
  shallowest wet area, minus dropped columns), the same "shallowest contributor" convention, now
  computed upstream.
- **Error bars are a worst-case linear sum** across constituents (treated as fully correlated),
  computed in the factory; all-or-nothing there (a missing constituent ensemble errors upstream).
- **float64 end to end** through ingest → derive, so the large-mean anomaly cancellation keeps
  precision in both the values and the `_sd` spread.
