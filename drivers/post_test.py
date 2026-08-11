from collections.abc import Iterator

# import numpy as np
# import xarray as xr
from datetime import datetime, timedelta, timezone
from pathlib import Path

# from itertools import product
# from textwrap import dedent
from unittest.mock import Mock, patch

from iotaa import Asset, Node, task
from pytest import fixture  # , mark, raises

from . import post

# Fixtures


# @fixture
# def atask():
#     @external
#     def f(ready: bool):
#         yield "A %sready task" % ("" if ready else "not-")
#         yield Asset(ready, lambda: ready)

#     return f


@fixture
def config(tmp_path):
    return {
        "aigfs_post": {
            "deliver_to": str(tmp_path / "delivery"),
            "execution": {
                "executable": "uw execute -h",
            },
            "inputfiles": [
                str(tmp_path / "run" / "aigfs.t00z.sfc.f006.grib2"),
                str(tmp_path / "run" / "aigfs.t00z.pres.f006.grib2"),
            ],
            "outputdir": str(tmp_path / "post"),
            "rundir": str(tmp_path / "run"),
        }
    }


@fixture
def cycle():
    return datetime(2025, 10, 1, 18, tzinfo=timezone.utc)


@fixture
def driverobj(config, cycle):
    return post.AIGFSPost(
        config=config,
        cycle=cycle,
        leadtime=timedelta(hours=6),
        schema_file=Path(__file__).parent / "post.jsonschema",
    )


# Tests


# @mark.parametrize("ready", list(product([True, False], repeat=4)))
# def test_GenICs_provisioned_rundir(atask, ready, driverobj, logcap):
#     mocks = [Mock(wraps=atask(x)) for x in ready]
#     with (
#         patch.object(driverobj, "files_copied", mocks[0]) as files_copied,
#         patch.object(driverobj, "files_hardlinked", mocks[1]) as files_hardlinked,
#         patch.object(driverobj, "files_linked", mocks[2]) as files_linked,
#         patch.object(driverobj, "runscript", mocks[3]) as runscript,
#     ):
#         node = driverobj.provisioned_rundir()
#     assert "provisioned run directory" in logcap.text
#     for x in [files_copied, files_hardlinked, files_linked, runscript]:
#         x.assert_called_once_with()
#     assert node.ready is all(ready)


def test_AIGFSPost__idx_delivered(driverobj):
    @task
    def mock__idx(path: Path) -> Iterator:
        yield f"mock__idx {path}"
        yield Asset(path, path.is_file)
        yield None
        path.parent.mkdir(exist_ok=True, parents=True)
        path.touch()

    path = Path(driverobj._deliver_to, "aigfs.t00z.sfc.f006.grib2.idx")
    assert not path.exists()
    with patch.object(driverobj, "_idx", Mock(wraps=mock__idx)) as _idx:
        node = driverobj._idx_delivered(path)
    assert node.ready
    _idx.assert_called_once_with(driverobj._delivered2idx[path])
    assert path.is_file()


def test_AIGFSPost__valid_driver_config(driverobj, logcap):
    reason = "Catastrophic failure"
    node = driverobj._valid_driver_config(reason=reason)
    assert not node.ready
    assert reason in logcap.text


def test_AIGFSPost_driver_name(driverobj):
    assert driverobj.driver_name() == "aigfs_post"


def test_AIGFSPost_output(driverobj):
    do = Path(driverobj.config["outputdir"])
    assert driverobj.output == {
        "idx": [do / "aigfs.t00z.sfc.f006.grib2.idx", do / "aigfs.t00z.pres.f006.grib2.idx"]
    }


def test_AIGFSPost__deliver_to(driverobj):
    assert driverobj._deliver_to == Path(driverobj.config["deliver_to"])


def test_AIGFSPost__deliver_to__fail(driverobj):
    del driverobj._config["deliver_to"]
    node = driverobj._deliver_to
    assert isinstance(node, Node)
    assert not node.ready


def test_AIGFSPost__delivered2idx(driverobj):
    dd = driverobj._deliver_to
    do = Path(driverobj.config["outputdir"])
    assert driverobj._delivered2idx == {
        dd / "aigfs.t00z.sfc.f006.grib2.idx": do / "aigfs.t00z.sfc.f006.grib2.idx",
        dd / "aigfs.t00z.pres.f006.grib2.idx": do / "aigfs.t00z.pres.f006.grib2.idx",
    }


def test_AIGFSPost__idx2grib(driverobj):
    di = driverobj.rundir
    do = Path(driverobj.config["outputdir"])
    assert driverobj._idx2grib == {
        do / "aigfs.t00z.sfc.f006.grib2.idx": di / "aigfs.t00z.sfc.f006.grib2",
        do / "aigfs.t00z.pres.f006.grib2.idx": di / "aigfs.t00z.pres.f006.grib2",
    }
