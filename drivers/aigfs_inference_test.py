from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import numpy as np
import xarray as xr
from iotaa import Asset, task
from pytest import fixture

from . import aigfs_inference

if TYPE_CHECKING:
    from graphcast import graphcast  # type: ignore[import-untyped]
# Fixtures


@fixture
def config(tmp_path):
    return {
        "aigfs_inference": {
            "diffs_stddev_path": str(tmp_path / "diffs_stddev_by_level.nc"),
            "execution": {"executable": "uw execute -h"},
            "forecast_freq": 6,
            "forecast_length": 24,
            "ics_path": str(tmp_path / "aigfs.t18z.ic.nc"),
            "json_path": str(tmp_path / "tables"),
            "mean_path": str(tmp_path / "mean_by_level.nc"),
            "model_weights_path": str(tmp_path / "weights.npz"),
            "rundir": str(tmp_path / "run"),
            "stddev_path": str(tmp_path / "stddev_by_level.nc"),
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
    ones = np.ones((1, 2, 1))
    return xr.Dataset(
        {
            "geopotential_at_surface": (["batch", "time", "x"], ones.copy()),
            "land_sea_mask": (["batch", "time", "x"], ones.copy()),
            "pressure": (["batch", "time", "x"], ones.copy()),
            "temperature": (["batch", "time", "x"], ones.copy(), {"long_name": "temp"}),
            "total_precipitation_6hr": (["batch", "time", "x"], ones.copy()),
        },
        coords={
            "batch": [0],
            "datetime": (["batch", "time"], datetimes.reshape(1, 2)),
            "time": times,
            "x": [0],
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


def test_drivers_AIGFSInference_inputs_targets_forcings(driverobj, logcap):
    inputs = xr.Dataset({"input_var": (["x"], [1, 2])})
    targets = xr.Dataset({"target_var": (["x"], [3, 4])})
    forcings = xr.Dataset({"forcing_var": (["x"], [5, 6])})

    @task
    def ics() -> Iterator:
        yield "mock initial_conditions"
        ref = xr.Dataset()
        yield Asset(ref, lambda: bool(ref))
        yield None
        ref.update(xr.Dataset({"temperature": (["x"], [10, 20])}))

    @task
    def mws() -> Iterator:
        yield "mock model_weights"
        ref: list[graphcast.CheckPoints] = []
        yield Asset(ref, lambda: bool(ref))
        yield None

        @dataclass
        class TaskConfig:
            input_duration: str = "12h"

        ref.append(Mock(task_config=TaskConfig()))

    with (
        patch.object(driverobj, "initial_conditions", Mock(wraps=ics)),
        patch.object(driverobj, "model_weights", Mock(wraps=mws)),
        patch(
            "drivers.aigfs_inference.data_utils.extract_inputs_targets_forcings",
            return_value=(inputs, targets, forcings),
        ) as extract,
    ):
        node = driverobj.inputs_targets_forcings()
    assert node.ready
    assert "inputs, targets, and forcings" in logcap.text
    # node.ref is the datasets list with (inputs, targets, forcings):
    assert len(node.ref) == 3
    xr.testing.assert_identical(node.ref[0], inputs)
    xr.testing.assert_identical(node.ref[1], targets)
    xr.testing.assert_identical(node.ref[2], forcings)
    # extract was called with the ics dataset and correct kwargs:
    call_args = extract.call_args
    xr.testing.assert_identical(call_args[0][0], xr.Dataset({"temperature": (["x"], [10, 20])}))
    assert call_args[1]["target_lead_times"] == slice("6h", "24h")


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


def test_drivers_aigfs_inference__clean_ics(ds):
    result = aigfs_inference._clean_ics(ds)
    # Dropped variables are gone:
    for var in ["geopotential_at_surface", "land_sea_mask", "total_precipitation_6hr"]:
        assert var not in result.data_vars
    # long_name attribute was removed:
    assert "long_name" not in result["temperature"].attrs
    # Only time index 1 was kept, and time was shifted back by 6h:
    assert len(result["time"]) == 1
    np.testing.assert_array_equal(result["time"].values, [np.timedelta64(0, "h")])


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
