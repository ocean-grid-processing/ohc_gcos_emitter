# ohc_combine

`ohc_combine` combines mapped-layer `ohc_derive` outputs into **combined depth layers** and exports the GCOS/WMO-report deliverable: `gcos<tag>_LocalGP_Giglio_etal_using<b0>_<b1>baseline.nc`. It's the single-product tail of the pipeline, and it ports `WMO2024_create_tseries_with_uq_for_combined.m` + `WMO2024_create_tseries_to_Karina_for_WMOreport.m`.

```
ohc_ingest ─▶ publish (--preset wmo) ─▶ ohc_derive (integral,area --no-ensemble) ─▶ ohc_combine ─▶ GCOS .nc
```

## What it computes

Combination happens on the **already-integrated 1-D series**, not on grids — `ohc_combine` never touches a map. Each mapped layer's `ohc_derive` output hands it two numbers per timestep: `ohc_integral(time)` in TJ (the area-weighted horizontal integral, = the original's `dᵢ·areaTotᵢ`) and the scalar `area_total` in m² (= `areaTotᵢ`). For a combined layer whose contributors are listed shallowest-first (in `layers.py`):

```
total_L(t) = Σᵢ n_facᵢ · integralᵢ(t)                    # TJ   — the combined heat content
area_L     = area_total of the shallowest contributor    # m²   — the GCOS denominator
volume_L   = Σᵢ n_facᵢ · dzᵢ · areaᵢ                     # m³
```

`n_facᵢ` scales a thin measured layer up to the depth slab it stands in for (`15_20`×3 covers the unmeasured `0–15 m`; `1800_1850`×3 covers `1850–2000 m`); `dzᵢ` is that contributor's own thickness, so `Σ n_fac·dz` recovers the nominal layer thickness.

The **export** then, per layer, takes the annual mean of the density `total_L/area_L`, subtracts the baseline-window mean (in **float64** — it's a large-mean cancellation on absolute OHC), and writes three views of that anomaly:

```
OHCA_J_m2_oc(y)      = (d_yr(y) − mean(d_yr over --ref-window)) × 1e12   # TJ/m² → J/m²
OHCA_ZJ(y)           = j_to_zj · area_L · OHCA_J_m2_oc(y)                # ZJ  (see Decisions)
vol_ave_temp_anom(y) = area_L · OHCA_J_m2_oc(y) / (cp0·rho0·volume_L)    # °C
```

where `d_yr(y)` is the annual mean of `total_L(t)/area_L` (TJ/m²). `cp0`/`rho0` come from the derive inputs' attributes (and must agree across them). Full output layout: [`combine_schema.md`](combine_schema.md).

## Combined layers (config)

The combined-layer table — each level's contributors, `n_fac`, `dz` — lives in [`layers.py`](layers.py); edit it there to add or remove layers, and `--levels` selects a subset per run. Current table: `0_300`, `0_700`, `0_1000` (net-new), `700_2000`, `0_2000`. The collaborator's reference file predates `0_1000`, so you reproduce it with the other four.

## Usage

### Environment

```bash
pip install -r requirements.txt          # numpy, xarray>=2024.10, netCDF4
```

### Test

Analytic checks on synthetic inputs — no data files, no cluster:

```bash
pip install -r requirements.txt -r requirements-dev.txt   # adds pytest, pandas
pytest
```

They cover the combine arithmetic (weighted total, shallowest-contributor area, volume), the guards (`dz`↔bounds, missing contributor, unimplemented `--reference`), and the export (baseline-zero-mean, the three quantity formulas, the PJ-vs-ZJ factor). End-to-end validation is a separate exercise — reproduce the collaborator's `.nc` and diff it (match `GCOS_area`/`GCOS_volume` first, then the series) with [`parity.py`](parity.py).

### Run

Combine consumes one `ohc_derive` output per **mapped** layer, so a full run is three steps: publish each layer with the WMO domain, derive its `integral`+`area`, then combine. For the reference file (the four original levels) you need **five** mapped layers — `700_1000` is only for `0_1000`.

```bash
# 1. publish each mapped layer with the WMO domain. --preset wmo drops fully-dry cells but keeps
#    partial continental-slope cells (see ohc_ingest for the preset). Mean-only stores are fine.
python ../ohc_ingest/scripts/publish.py STORE_15_20.zarr --experiment B --product LocalGP --preset wmo
# ... repeat: 15_300, 300_700, 700_1850, 1800_1850   (+ 700_1000 if you also want 0_1000)

# 2. derive the horizontal integral + area for each, central-only (the deliverable has no error bars):
python ../ohc_derive/derive.py OHC_..._lev15_20_..._LocalGP.nc --transforms integral,area --no-ensemble --out derive/
# ... one per mapped layer

# 3. combine → the GCOS deliverable (the four original levels):
python combine.py derive/derive_*.nc \
    --gcos-tag "GCOS 2026 OP20260127b" \
    --levels 0_300,0_700,700_2000,0_2000 \
    --ref-window 2005:2024 --out .
```

Output: `gcos2026op20260127b_LocalGP_Giglio_etal_using2005_2024baseline.nc` — dim `years`, with `GCOS_<lo>_<hi>_{OHCA_J_m2_oc, OHCA_ZJ, vol_ave_temp_anom}` per level and `GCOS_area`/`GCOS_volume` attributes.

#### combine.py options

All configuration is on the command line — no env, no config file. The one "config" that lives in code is the combined-layer table in `layers.py` (above).

| option | default | effect |
|---|---|---|
| `DERIVE_*.nc` (positional, 1+) | *(required)* | the `ohc_derive` outputs, one per **mapped** layer, each built with `--transforms integral,area --no-ensemble`. All contributors needed by the selected levels must be present (else a clear error). |
| `--gcos-tag` | *(required)* | e.g. `"GCOS 2026 OP20260127b"` — lowercased/space-stripped for the filename, and (with `--collaborators`) the global `description`. |
| `--levels` | all in `layers.py` | comma list of combined levels to emit (e.g. `0_300,0_700,700_2000,0_2000`). |
| `--ref-window` | `2005:2024` | baseline-mean window `YEAR0:YEAR1` subtracted from the yearly series; also names the file (`using<b0>_<b1>baseline`). Separator `-` or `:`. |
| `--j-to-zj` | `1e-21` | `OHCA_ZJ` scale — `1e-21` = true zettajoules (default); `1e-15` byte-matches the original's (mislabelled petajoule) `_ZJ` column. |
| `--reference` | `shallowest` | combined-layer reference-area policy. Only `shallowest` is implemented; `deepest`/`intersection` raise `NotImplementedError` (they need gridded per-layer masks). |
| `--collaborators` | `LocalGP by Giglio, Sukianto, Kuusela, Mills` | the `description` suffix (`"<gcos-tag>, <collaborators>"`). |
| `--out` | `.` | output directory (created if absent). |

`cp0`/`rho0` are **not** options — they're read from the derive inputs' attributes.

## Opinionated choices

A few things this step decides for you that aren't obvious from the output — what each means, and the flag to change it:

- **`OHCA_ZJ` is true zettajoules** (`--j-to-zj`, default `1e-21`). The original scaled by `1e-15`, which is J→**peta**joules — its `_ZJ` column is mislabelled and 10⁶× too large. We emit real ZJ by decision; pass `--j-to-zj 1e-15` to byte-match the original on that one column. `OHCA_J_m2_oc` and `vol_ave_temp_anom` are unaffected.
- **Reference area = shallowest contributor** (`--reference shallowest`, the only mode). For the `0_X` layers that equals the uniform 300 m bathymetry floor from ingest, so a 300–2000 m shelf cell sits in the `0_2000` denominator carrying no deep water. "Bottom-must-be-wet" (`--reference deepest|intersection`) needs per-layer gridded masks and raises `NotImplementedError` — a deliberate follow-up, not a silent denominator swap.
- **No uncertainty.** The deliverable carries none, so it's `--no-ensemble` throughout — the mean field alone (central values are byte-identical either way).
- **float64 mean.** OHC is float64 end to end (ingest → publish `--dtype float64`, the default), so the large-mean anomaly cancellation keeps full precision; the 100-member ensemble stays float32 (it only feeds `_sd`, unused here).
