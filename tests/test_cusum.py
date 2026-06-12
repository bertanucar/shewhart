import numpy as np
import pytest

import shewhart as sw


def test_hand_computed_tabular_cusum():
    # center 10, sigma 1, k = 0.5, h = 4: C+ = [0, 0, 0, 0.5, 2.0, 4.5]
    r = sw.cusum([10, 10, 10, 11, 12, 13], center=10, sigma=1, k=0.5, h=4)
    np.testing.assert_allclose(
        r.table["cusum_pos"].to_numpy(), [0, 0, 0, 0.5, 2.0, 4.5]
    )
    np.testing.assert_allclose(r.table["cusum_neg"].to_numpy(), 0.0)
    assert r.stats["cusum_limit"] == 4.0
    assert not r.ok
    assert r.signals[0].points == (5,)  # only the last point crosses H


def test_downward_shift_accumulates_on_negative_side():
    r = sw.cusum([10, 9, 8, 7, 6], center=10, sigma=1, k=0.5, h=4)
    assert r.table["cusum_neg"].iloc[-1] < 0
    assert not r.ok


def test_in_control_data_is_quiet():
    rng = np.random.default_rng(3)
    r = sw.cusum(rng.normal(50, 2, 80), center=50, sigma=2)
    assert r.ok


def test_fit_path_and_baseline_roundtrip(tmp_path):
    data = [10.2, 10.4, 10.1, 10.5, 10.3, 10.2, 10.6]
    r = sw.cusum(data)
    assert r.stats["center"] == pytest.approx(np.mean(data))
    assert "Phase I" in r.meta["source"]

    path = tmp_path / "cusum.json"
    r.baseline.save(path)
    r2 = sw.cusum(data, limits=str(path))
    assert "Phase II" in r2.meta["source"]
    with pytest.raises(ValueError, match="fitted for 'imr'"):
        sw.cusum(data, limits=sw.imr(data).baseline)


def test_parameter_validation_teaches():
    with pytest.raises(ValueError, match="k=0.5"):
        sw.cusum([1, 2, 3], k=-1)


def test_plot_smoke():
    import matplotlib

    matplotlib.use("Agg")
    ax = sw.cusum([10, 10, 11, 12, 13], center=10, sigma=1).plot()
    assert ax.get_title().startswith("CUSUM")
