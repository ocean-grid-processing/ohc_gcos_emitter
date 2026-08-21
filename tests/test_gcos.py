"""gcos: the three per-area views from the factory's ohca, and the cross-level consistency guards."""
import numpy as np
import pytest
import xarray as xr

import gcos


def _blob(level="0_2000", area=1e12, vol=1e15, window="2005-2024", with_sd=True):
    """A synthetic ohc_derive blob: extensive ohca (TJ, baseline-referenced) + geometry + constants."""
    ds = xr.Dataset({"ohca": ("year", np.array([1.0, 2.0]))}, coords={"year": [2005, 2006]})
    if with_sd:
        ds["ohca_sd"] = ("year", np.array([0.1, 0.2]))
    ds.attrs.update({"level": level, "area_m2": area, "volume_m3": vol, "cp0": 3989.0, "rho0": 1030.0,
                     "time_window": window})
    return ds


def test_three_views_from_ohca():
    out = gcos.build_dataset([_blob(area=1e12)], j_to_zj=1e-21, tag="dev", provenance_link=None)
    assert np.allclose(out["GCOS_0000_2000_OHCA_J_m2_oc"].values, [1.0, 2.0])   # ohca/area*1e12 (area 1e12)
    assert np.allclose(out["GCOS_0000_2000_OHCA_ZJ"].values, 1e-21 * 1e12 * np.array([1.0, 2.0]))
    assert np.allclose(out["GCOS_0000_2000_vol_ave_temp_anom"].values,
                       1e12 * np.array([1.0, 2.0]) / (3989.0 * 1030.0 * 1e15))
    assert out["GCOS_0000_2000_OHCA_J_m2_oc"].attrs["units"] == "J/m2"
    assert out.attrs["time_window"] == "2005-2024"


def test_sd_views_present_and_scaled():
    out = gcos.build_dataset([_blob(area=1e12)], 1e-21, "dev", None)
    assert np.allclose(out["GCOS_0000_2000_OHCA_J_m2_oc_sd"].values, [0.1, 0.2])
    assert np.allclose(out["GCOS_0000_2000_OHCA_ZJ_sd"].values, 1e-21 * 1e12 * np.array([0.1, 0.2]))


def test_mean_only_blob_has_no_sd():
    out = gcos.build_dataset([_blob(with_sd=False)], 1e-21, "dev", None)
    assert "GCOS_0000_2000_OHCA_J_m2_oc_sd" not in out.data_vars


def test_j_to_zj_petajoule_mode():
    out = gcos.build_dataset([_blob(area=1e12)], j_to_zj=1e-15, tag="dev", provenance_link=None)
    assert np.allclose(out["GCOS_0000_2000_OHCA_ZJ"].values, 1e-15 * 1e12 * np.array([1.0, 2.0]))


def test_multiple_levels_share_one_year_axis():
    out = gcos.build_dataset([_blob(level="0_700", vol=7e14), _blob(level="0_2000", vol=2e15)],
                             1e-21, "dev", None)
    assert "GCOS_0000_0700_OHCA_J_m2_oc" in out.data_vars
    assert "GCOS_0000_2000_OHCA_J_m2_oc" in out.data_vars
    assert list(out["years"].values) == [2005.0, 2006.0]


def test_year_axis_mismatch_errors():
    other = _blob(level="0_700").assign_coords(year=[2005, 2007])
    with pytest.raises(SystemExit):
        gcos.build_dataset([_blob(level="0_2000"), other], 1e-21, "dev", None)


def test_baseline_window_mismatch_errors():
    with pytest.raises(SystemExit):
        gcos.build_dataset([_blob(level="0_700", window="2005-2024"),
                            _blob(level="0_2000", window="2004-2024")], 1e-21, "dev", None)


def test_cp0_rho0_mismatch_errors():
    other = _blob(level="0_700")
    other.attrs["cp0"] = 4000.0
    with pytest.raises(SystemExit):
        gcos.build_dataset([_blob(level="0_2000"), other], 1e-21, "dev", None)


def test_filename():
    assert gcos.filename("dev", "2005-2024") == "gcos_dev_2005_2024.nc"


def test_round_trip_through_files(tmp_path):
    src = str(tmp_path / "derive_dev_0_2000.nc")
    _blob().to_netcdf(src)
    blob = xr.open_dataset(src)
    out = gcos.build_dataset([blob], 1e-21, "dev", None)
    dest = str(tmp_path / gcos.filename("dev", out.attrs["time_window"]))
    out.to_netcdf(dest)
    back = xr.open_dataset(dest)
    assert "GCOS_0000_2000_OHCA_ZJ" in back.data_vars
