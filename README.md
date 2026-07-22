# ohc_combine

Combines mapped-layer `ohc_derive` outputs into **combined depth layers** and exports the
GCOS/WMO-report deliverable — the single-product downstream step that produces
`gcos<tag>_LocalGP_Giglio_etal_using<b0>_<b1>baseline.nc`. It ports
`WMO2024_create_tseries_with_uq_for_combined.m` + `WMO2024_create_tseries_to_Karina_for_WMOreport.m`.

```
ohc_ingest ─▶ publish (wmo, bathy_floor=300) ─▶ ohc_derive (integral, area, --no-ensemble) ─▶ ohc_combine
```

## Model

Layer combination happens on the **already-integrated 1-D series**, not on grids. Each mapped
layer's `ohc_derive` output gives `ohc_integral(time)` (TJ) and the scalar `area_total` (m²) —
exactly the `dᵢ·areaTotᵢ` and `areaTotᵢ` of the original. For a combined layer with contributors
listed shallowest-first (see `layers.py`):

```
total_L(t) = Σᵢ n_facᵢ · integralᵢ(t)            # TJ
area_L     = area of the shallowest contributor   # m²  (the GCOS denominator)
volume_L   = Σᵢ n_facᵢ · dzᵢ · areaᵢ              # m³
```

`n_fac` scales a thin measured layer up to the depth slab it stands in for (`15_20`×3 → `0–15 m`;
`1800_1850`×3 → `1850–2000 m`); `dz` is the contributor's own thickness. The **export** then
takes the annual mean of `total_L/area_L`, subtracts the baseline-window mean (float64 — it's a
large-mean cancellation on absolute OHC), and writes three quantities per layer.

## Combined layers (config)

Defined in [`layers.py`](layers.py) — edit there to add/remove layers; `--levels` selects a
subset per run. Current table: `0_300`, `0_700`, `0_1000` (net-new), `700_2000`, `0_2000`. The
collaborator's reference file predates `0_1000`, so reproduce it with the other four.

## Run

```bash
pip install -r requirements.txt

# per mapped layer (6 of them): publish with the WMO domain, then derive integral+area
python ../ohc_ingest/scripts/publish.py STORE_15_20.zarr --experiment B --product LocalGP --preset wmo
python ../ohc_derive/derive.py OHC_..._lev15_20_..._LocalGP.nc --transforms integral,area --no-ensemble --out derive/
# ... repeat for 15_300, 300_700, 700_1000, 700_1850, 1800_1850 ...

# combine → the GCOS deliverable (reproduce the reference file: the original four levels)
python combine.py derive/derive_*.nc \
    --gcos-tag "GCOS 2026 OP20260127b" \
    --levels 0_300,0_700,700_2000,0_2000 \
    --ref-window 2005:2024 --out .
```

Output: `gcos2026op20260127b_LocalGP_Giglio_etal_using2005_2024baseline.nc`, dim `years`, with
`GCOS_<lo>_<hi>_{OHCA_J_m2_oc, OHCA_ZJ, vol_ave_temp_anom}` per level + `GCOS_area`/`GCOS_volume`
attributes. See [`combine_schema.md`](combine_schema.md).

## Parity notes

- **`OHCA_ZJ` is true zettajoules** (`1e-21`, the default). The original scaled by `1e-15`
  (= J→PJ), so its `_ZJ` column is really petajoules; we correct it by decision. Pass
  `--j-to-zj 1e-15` to byte-match the original on that one column.
- **Reference area = shallowest contributor** (`--reference shallowest`, the only mode). For the
  `0_X` layers this equals the uniform 300 m bathymetry floor applied at ingest, so a 300–2000 m
  shelf cell counts in the `0_2000` denominator with no deep water. Changing that ("bottom must be
  wet") is `--reference deepest|intersection`, which needs per-layer **gridded** masks and raises
  `NotImplementedError` here — a deliberate follow-up, not a silent denominator swap.
- **Uncertainty is dropped** — the deliverable carries none, so `--no-ensemble` throughout.
- **float64 mean.** The mean OHC is float64 end to end (ingest → zarr → publish `--dtype float64`,
  the default), so the large-mean anomaly cancellation keeps full double precision. The 100-member
  ensemble stays float32 (it only feeds `_sd`, which this deliverable doesn't use).

## Tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Analytic checks on synthetic inputs (no files): the weighted total / shallowest-area / volume,
the reference-area guard, the `dz` and missing-contributor guards, and the export's
baseline-zero-mean + the three quantity formulas + the PJ-vs-ZJ constant. End-to-end validation
is reproducing the collaborator's `.nc` (match `GCOS_area`/`GCOS_volume` first, then the series).
