# ohc_combine output schema

One NetCDF, `<gcos_tag>_LocalGP_Giglio_etal_using<b0>_<b1>baseline.nc`, matching the
collaborator's GCOS/WMO-report format.

## Dimensions & coordinates

| name | meaning |
|---|---|
| `years` | calendar years present in the input series (e.g. 2004…2025), stored as `double` |

## Variables (per combined layer `<lo>_<hi>`, zero-padded to 4 digits)

| variable | dims | units | definition |
|---|---|---|---|
| `GCOS_<lo>_<hi>_OHCA_J_m2_oc` | `(years,)` | J/m² | `d_yr − mean(d_yr over ref-window)`, where `d_yr` = annual mean of `total/area` |
| `GCOS_<lo>_<hi>_OHCA_ZJ` | `(years,)` | ZJ | `j_to_zj · area · OHCA_J_m2_oc` |
| `GCOS_<lo>_<hi>_vol_ave_temp_anom` | `(years,)` | °C | `area · OHCA_J_m2_oc / (cp0·rho0·volume)` |

`j_to_zj` defaults to `1e-21` (true zettajoules). The original file used `1e-15` (= J→PJ, so its
`_ZJ` column is actually petajoules); pass `--j-to-zj 1e-15` to byte-match it on that column.

## Attributes

- Per variable: `GCOS_area` (m²) on the two `OHCA_*` variables; `GCOS_volume` (m³) on
  `vol_ave_temp_anom`.
- Global: `description = "<gcos_tag>, <collaborators>"`.

## Provenance of the inputs

`area` is the shallowest contributor's `area_total`; `volume = Σ n_fac·dz·area`; `total(t) =
Σ n_fac·integralᵢ(t)`. `cp0`/`rho0` are read from the derive inputs' attributes (must agree across
inputs). The `years` axis and the annual means come from the monthly `time` coordinate carried
through `ohc_ingest → publish → ohc_derive`.

## Deliberate deviations from the original

- **`OHCA_ZJ` is true zettajoules** (`1e-21`), correcting the original's `1e-15` (petajoules,
  mislabelled ZJ). This is the one column that will *not* byte-match the collaborator's file at the
  default; run `--j-to-zj 1e-15` to compare it directly. `OHCA_J_m2_oc` and `vol_ave_temp_anom` are
  unaffected.
- **No uncertainty variables** — the deliverable carries none.
- **Reference area = shallowest contributor only** — `deepest`/`intersection` need gridded
  per-layer masks and are not implemented (they raise rather than silently mislead).
