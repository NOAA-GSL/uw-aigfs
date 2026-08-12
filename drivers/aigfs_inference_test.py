from datetime import datetime, timezone
from pathlib import Path
import xarray as xr
from pytest import fixture
from unittest.mock import patch, Mock
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


# Tests


def test_drivers_AIGFSInference_initial_conditions(driverobj):
    path = Path(driverobj.config["ics_path"])
    ds = xr.Dataset({"temperature": (["x"], [10, 20, 30])}, coords={"x": [0, 1, 2]})
    ds.to_netcdf(path)
    with patch.object(aigfs_inference, "_adjust_time", Mock(wraps=lambda x, _: x)) as _adjust_time:
        node = driverobj.initial_conditions()
    assert node.ready
    assert node.ref == ds  # a no-op now due to mocked _adjust_time()
    _adjust_time.assert_called_once_with(ds, 4)


def test_drivers_AIGFSInference_driver_name(driverobj):
    assert driverobj.driver_name() == "aigfs_inference"
