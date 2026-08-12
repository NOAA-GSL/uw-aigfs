from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import xarray as xr
from pytest import fixture

from . import aigfs_inference

# Fixtures


@fixture
def config(tmp_path):
    return {
        "aigfs_inference": {
            "diffs_stddev_path": str(tmp_path / "diffs_stddev"),
            "execution": {"executable": "uw execute -h"},
            "forecast_freq": 6,
            "forecast_length": 24,
            "ics_path": str(tmp_path / "aigfs.t18z.ic.nc"),
            "json_path": str(tmp_path / "json"),
            "mean_path": str(tmp_path / "mean"),
            "model_weights_path": str(tmp_path / "model_weihts"),
            "rundir": str(tmp_path / "run"),
            "stddev_path": str(tmp_path / "stddev"),
        }
    }


@fixture
def cycle():
    return datetime(2025, 10, 1, 18, tzinfo=timezone.utc)


@fixture
def driverobj(config, cycle):
    return aigfs_inference.AIGFSInference(
        config=config,
        cycle=cycle,
        schema_file=Path(__file__).parent / "aigfs_inference.jsonschema",
    )


@fixture
def ds():
    t0 = np.datetime64("2025-10-01T18:00")
    times = np.array([np.timedelta64(0, "h"), np.timedelta64(6, "h")])
    datetimes = np.array([t0, t0 + np.timedelta64(6, "h")])
    return xr.Dataset(
        {"temperature": (["batch", "time", "x"], np.ones((1, 2, 3)))},
        coords={
            "batch": [0],
            "time": times,
            "datetime": (["batch", "time"], datetimes.reshape(1, 2)),
            "x": [0, 1, 2],
        },
    )


# Tests


def test_drivers_AIGFSInference_initial_conditions(driverobj, ds, logcap):
    path = Path(driverobj.config["ics_path"])
    ds.to_netcdf(path)
    node = driverobj.initial_conditions()
    assert node.ready
    ds_check(node.ref)
    assert "initial conditions" in logcap.text


def test_drivers_AIGFSInference_driver_name(driverobj):
    assert driverobj.driver_name() == "aigfs_inference"


def test_drivers_aigfs_inference__adjust_time(ds, logcap):
    # fcst_steps=4 => needs 6 time steps, ds has 2, so the if block is entered.
    ds_check(aigfs_inference._adjust_time(ds=ds, fcst_steps=4, taskname="test"))
    assert "test: Updating dataset to account for forecast length" in logcap.text


def test_drivers_aigfs_inference__adjust_time__noop(ds):
    # fcst_steps=0 => needs 2 time steps, ds has 2, so the if block is NOT entered.
    result = aigfs_inference._adjust_time(ds=ds, fcst_steps=0, taskname="test")
    xr.testing.assert_identical(result, ds)


# Helpers


def ds_check(ds: xr.Dataset):
    # Should have fcst_steps + 2 = 6 time steps now:
    assert len(ds["time"]) == 6
    # Time values are 6-hourly timedeltas:
    expected_times = np.array([np.timedelta64(6 * i, "h") for i in range(6)])
    np.testing.assert_array_equal(ds["time"].values, expected_times)
    # Datetime values are absolute times starting from the original start:
    t0 = np.datetime64("2025-10-01T18:00")
    expected_datetimes = np.array([t0 + np.timedelta64(6 * i, "h") for i in range(6)])
    np.testing.assert_array_equal(ds["datetime"].values[0], expected_datetimes)
    # Original data at existing time indices is preserved, new indices are NaN:
    assert float(ds["temperature"].isel(batch=0, time=0, x=0)) == 1.0
    assert np.isnan(float(ds["temperature"].isel(batch=0, time=2, x=0)))
