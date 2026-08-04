"""combine_level arithmetic: weighted total, shallowest-contributor area, volume, guards."""
import numpy as np
import pytest

import aggregate
from layers import Contributor, Level
from conftest import make_layer


def test_total_area_volume():
    by = {
        "15_20": make_layer("15_20", 15, 20, area=100.0, integral_values=[2.0, 2.0]),
        "15_300": make_layer("15_300", 15, 300, area=80.0, integral_values=[5.0, 5.0]),
    }
    lv = Level("0_300", (Contributor("15_20", 3, 5), Contributor("15_300", 1, 285)))
    out = aggregate.combine_level(lv, by)

    assert np.allclose(out["total"].values, 3 * 2.0 + 1 * 5.0)   # 11 each month
    assert out["area"] == 100.0                                  # shallowest (15_20)
    assert out["volume"] == 3 * 5 * 100.0 + 1 * 285 * 80.0       # 24300
    assert (out["low"], out["high"]) == (0, 300)


def test_area_is_shallowest_not_deepest():
    # shallowest has the larger footprint; the deep contributor's smaller area must NOT be used.
    by = {
        "700_1850": make_layer("700_1850", 700, 1850, area=50.0, integral_values=[1.0]),
        "1800_1850": make_layer("1800_1850", 1800, 1850, area=40.0, integral_values=[1.0]),
    }
    lv = Level("700_2000", (Contributor("700_1850", 1, 1150), Contributor("1800_1850", 3, 50)))
    out = aggregate.combine_level(lv, by)
    assert out["area"] == 50.0                                   # 700_1850 (contributors[0])


def test_reference_other_than_shallowest_not_implemented():
    by = {"15_20": make_layer("15_20", 15, 20, 100.0, [1.0])}
    lv = Level("x_y", (Contributor("15_20", 3, 5),))
    with pytest.raises(NotImplementedError):
        aggregate.combine_level(lv, by, reference="deepest")


def test_dz_mismatch_raises():
    by = {"15_20": make_layer("15_20", 15, 20, 100.0, [1.0])}   # bounds dz = 5
    lv = Level("x_y", (Contributor("15_20", 3, 999),))          # config dz wrong
    with pytest.raises(SystemExit):
        aggregate.combine_level(lv, by)


def test_missing_contributor_raises():
    by = {"15_20": make_layer("15_20", 15, 20, 100.0, [1.0])}
    lv = Level("0_300", (Contributor("15_20", 3, 5), Contributor("15_300", 1, 285)))
    with pytest.raises(SystemExit):
        aggregate.combine_level(lv, by)


def test_sd_is_nfac_weighted_linear_sum():
    # two contributors carrying yearly SDs -> combined total_sd_yearly = Σ n_fac · sd_i, per year
    by = {
        "15_20": make_layer("15_20", 15, 20, 100.0, [2.0] * 24, sd_yearly={2004: 1.0, 2005: 2.0}),
        "15_300": make_layer("15_300", 15, 300, 80.0, [5.0] * 24, sd_yearly={2004: 0.5, 2005: 1.5}),
    }
    lv = Level("0_300", (Contributor("15_20", 3, 5), Contributor("15_300", 1, 285)))
    tsy = aggregate.combine_level(lv, by)["total_sd_yearly"]
    assert np.allclose(tsy.sel(year=2004).values, 3 * 1.0 + 1 * 0.5)
    assert np.allclose(tsy.sel(year=2005).values, 3 * 2.0 + 1 * 1.5)


def test_sd_none_when_a_contributor_lacks_ensemble():
    by = {
        "15_20": make_layer("15_20", 15, 20, 100.0, [2.0] * 12, sd_yearly={2004: 1.0}),
        "15_300": make_layer("15_300", 15, 300, 80.0, [5.0] * 12),   # no ensemble
    }
    lv = Level("0_300", (Contributor("15_20", 3, 5), Contributor("15_300", 1, 285)))
    assert aggregate.combine_level(lv, by)["total_sd_yearly"] is None


def test_uncertainty_available_all_none_and_partial_raises():
    a_sd = make_layer("a", 0, 10, 1.0, [1.0], sd_yearly={2004: 1.0})
    b_sd = make_layer("b", 0, 10, 1.0, [1.0], sd_yearly={2004: 1.0})
    b_plain = make_layer("b", 0, 10, 1.0, [1.0])
    assert aggregate.uncertainty_available(["a", "b"], {"a": a_sd, "b": b_sd}) is True
    assert aggregate.uncertainty_available(["a", "b"],
                                           {"a": make_layer("a", 0, 10, 1.0, [1.0]), "b": b_plain}) is False
    with pytest.raises(SystemExit):                              # partial mix -> loud error
        aggregate.uncertainty_available(["a", "b"], {"a": a_sd, "b": b_plain})
