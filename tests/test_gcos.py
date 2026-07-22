"""GCOS export: baseline-anomaly zero-mean, the three quantity formulas, attrs, filename."""
import numpy as np

import gcos
from conftest import monthly_total


def test_quantities_and_baseline():
    area, vol = 1e14, 3e16
    cp0, rho0 = 3989.244, 1030.0
    dens = {2004: 1.0e-4, 2005: 2.0e-4, 2006: 3.0e-4}   # TJ/m^2 yearly densities
    combined = [{"name": "0_300", "low": 0, "high": 300,
                 "total": monthly_total(area, dens), "area": area, "volume": vol}]

    ds = gcos.build_dataset(combined, cp0, rho0, baseline=(2005, 2006),
                            j_to_zj=1e-15, gcos_tag="GCOS 2026 T",
                            collaborators="LocalGP by X")

    jm2 = ds["GCOS_0000_0300_OHCA_J_m2_oc"].values
    zj = ds["GCOS_0000_0300_OHCA_ZJ"].values
    vt = ds["GCOS_0000_0300_vol_ave_temp_anom"].values
    yrs = ds["years"].values

    # baseline (2005-2006) mean of the J/m^2 anomaly is exactly zero
    base = (yrs >= 2005) & (yrs <= 2006)
    assert abs(jm2[base].mean()) < 1e-6 * np.abs(jm2).max()

    # J/m^2 = (density - baseline mean) * 1e12 (TJ/m^2 -> J/m^2)
    base_mean = (2.0e-4 + 3.0e-4) / 2
    expect = (np.array([1.0e-4, 2.0e-4, 3.0e-4]) - base_mean) * 1e12
    assert np.allclose(jm2, expect)

    # the other two are exact functions of J/m^2
    assert np.allclose(zj, 1e-15 * area * jm2)
    assert np.allclose(vt, area * jm2 / (cp0 * rho0 * vol))

    # attrs land on the right variables
    assert ds["GCOS_0000_0300_OHCA_J_m2_oc"].attrs["GCOS_area"] == area
    assert ds["GCOS_0000_0300_OHCA_ZJ"].attrs["GCOS_area"] == area
    assert ds["GCOS_0000_0300_vol_ave_temp_anom"].attrs["GCOS_volume"] == vol
    assert ds.attrs["description"] == "GCOS 2026 T, LocalGP by X"


def test_true_zj_constant():
    # 1e-21 gives physically-correct ZJ; check it just rescales the OHCA_ZJ column.
    area, vol = 1e14, 3e16
    combined = [{"name": "0_2000", "low": 0, "high": 2000,
                 "total": monthly_total(area, {2004: 0.0, 2005: 1.0e-3}),
                 "area": area, "volume": vol}]
    pj = gcos.build_dataset(combined, 3989.244, 1030.0, (2005, 2005), 1e-15, "T", "X")
    zj = gcos.build_dataset(combined, 3989.244, 1030.0, (2005, 2005), 1e-21, "T", "X")
    r = pj["GCOS_0000_2000_OHCA_ZJ"].values / zj["GCOS_0000_2000_OHCA_ZJ"].values
    assert np.allclose(r[np.isfinite(r)], 1e6)   # PJ is 1e6x the true ZJ


def test_filename_matches_convention():
    assert (gcos.filename("GCOS 2026 OP20260127b", (2005, 2024))
            == "gcos2026op20260127b_LocalGP_Giglio_etal_using2005_2024baseline.nc")
