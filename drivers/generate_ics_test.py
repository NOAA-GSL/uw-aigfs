"""
GenICs driver tests.
"""

from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from unittest.mock import Mock, patch

from iotaa import Asset, external
from pytest import fixture, mark

from . import generate_ics


@fixture
def atask():
    @external
    def f(ready: bool):
        yield "A %sready task" % ("" if ready else "not-")
        yield Asset(ready, lambda: ready)

    return f


@fixture
def config(tmp_path):
    return {
        "aigfs_ics": {
            "execution": {
                "executable": "uw execute -h",
                "batchargs": {"walltime": "00:05:00"},
            },
            "files_to_link": {
                "data/a.t00z.pgrb2.0p25.f000": str(tmp_path / "a.grib2"),
                "data/b.t00z.pgrb2.0p25.f006": str(tmp_path / "b.grib2"),
            },
            "variable_extraction_yaml": str(
                Path(__file__).parent.parent / "parm" / "wgrib2_data.yaml"
            ),
            "rundir": str(tmp_path / "prep"),
        }
    }


@fixture
def cycle():
    return datetime(2025, 10, 1, 18, tzinfo=timezone.utc)


@fixture
def driverobj(config, cycle):
    return generate_ics.GenICs(
        config=config,
        cycle=cycle,
        batch=True,
        schema_file=Path(__file__).parent / "generate_ics.jsonschema",
    )


@mark.parametrize("ready", list(product([True, False], repeat=4)))
def test_provisioned_rundir(atask, ready, driverobj, logcap):
    mocks = [Mock(wraps=atask(x)) for x in ready]
    with (
        patch.object(driverobj, "files_copied", mocks[0]) as files_copied,
        patch.object(driverobj, "files_hardlinked", mocks[1]) as files_hardlinked,
        patch.object(driverobj, "files_linked", mocks[2]) as files_linked,
        patch.object(driverobj, "runscript", mocks[3]) as runscript,
    ):
        node = driverobj.provisioned_rundir()
        assert "provisioned run directory" in logcap.text
        for x in [files_copied, files_hardlinked, files_linked, runscript]:
            x.assert_called_once_with()
        assert node.ready is all(ready)


def test_driver_name(driverobj):
    assert driverobj.driver_name() == "aigfs_ics"


def test_wgrib2_tasks(driverobj, tmp_path):
    def make_output(*_args, **_kwargs):
        cmd = _kwargs["cmd"]
        (driverobj.rundir / cmd.split()[-1]).touch()

    for f in ("a.grib2", "b.grib2"):
        (tmp_path / f).touch()
    with patch.object(generate_ics, "run_shell_cmd", side_effect=make_output) as run:
        driverobj.wgrib2_tasks()
        assert run.call_count == 7


def test__wgrib2_commands(driverobj):
    cmds = driverobj._wgrib2_commands
    assert len(cmds) == 7
