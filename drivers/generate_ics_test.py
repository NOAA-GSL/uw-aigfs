"""
GenICs driver tests.
"""

from collections.abc import Iterator
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from textwrap import dedent
from unittest.mock import Mock, patch

from iotaa import Asset, external
from pytest import fixture, mark, raises

from . import generate_ics

# Fixtures


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
                "data/a.t00z.pgrb2.0p25.f000": str(tmp_path / "fh0.grib2"),
                "data/a.t00z.pgrb2.0p25.f006": str(tmp_path / "fh6.grib2"),
                "foo/bar": "/baz/quz",
            },
            "variable_extraction_yaml": str(tmp_path / "vars.yaml"),
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


@fixture
def varkit(driverobj):
    content = """
    ".pgrb2.0p25.f000":
      ":HGT:":
        levels:
          - ":surface:"
        load_once: true
      ":TMP:":
        levels:
          - ":2 m above ground:"
      ":PRMSL:":
        levels:
          - ":mean sea level:"
      ":VGRD|UGRD:":
        levels:
          - ":10 m above ground:"
      ":SPFH|VVEL|VGRD|UGRD|HGT|TMP:":
        levels:
          - ":(200|850|1000) mb:"
    ".pgrb2.0p25.f006":
      ":LAND:":
        levels:
          - ":surface:"
        load_once: true
      "^(597):":
        levels:
          - ":surface:"
      ":FOO:":
        levels:
          - ":surface:"
        load_once: false
    """
    Path(driverobj.config["variable_extraction_yaml"]).write_text(dedent(content))
    d = driverobj.rundir / "data"
    keys = [
        Path(f"{d}/HGT_surface_00.pgrb2.0p25.f000.nc"),
        Path(f"{d}/TMP_2_m_above_ground_00.pgrb2.0p25.f000.nc"),
        Path(f"{d}/PRMSL_mean_sea_level_00.pgrb2.0p25.f000.nc"),
        Path(f"{d}/VGRD.UGRD_10_m_above_ground_00.pgrb2.0p25.f000.nc"),
        Path(f"{d}/SPFH.VVEL.VGRD.UGRD.HGT.TMP_.200.850.1000._mb_00.pgrb2.0p25.f000.nc"),
        Path(f"{d}/LAND_surface_00.pgrb2.0p25.f006.nc"),
        Path(f"{d}/^.597._surface_00.pgrb2.0p25.f006.nc"),
    ]
    cmd = "wgrib2 -match ':%s:' -match '%s' -nc_nlev %s -netcdf {ncfile} %s/a.t00z.pgrb2.0p25.f00%s"
    vals = [
        cmd % ("surface", ":HGT:", 1, d, 0),
        cmd % ("2 m above ground", ":TMP:", 1, d, 0),
        cmd % ("mean sea level", ":PRMSL:", 1, d, 0),
        cmd % ("10 m above ground", ":VGRD|UGRD:", 1, d, 0),
        cmd % ("(200|850|1000) mb", ":SPFH|VVEL|VGRD|UGRD|HGT|TMP:", 3, d, 0),
        cmd % ("surface", ":LAND:", 1, d, 6),
        cmd % ("surface", "^(597):", 1, d, 6),
    ]
    expected = dict(zip(keys, vals, strict=True))
    return driverobj, expected


# Tests


def test_GenICs_ncfiles(varkit):
    @external
    def mock__ncfile(path: Path, _: str) -> Iterator:
        yield "mock _ncfile"
        yield Asset(path, lambda: True)

    driverobj, expected = varkit
    with patch.object(driverobj, "_ncfile", Mock(wraps=mock__ncfile)) as _ncfile:
        node = driverobj.ncfiles()
    assert node.ready
    for path, cmd in expected.items():
        _ncfile.assert_any_call(path, cmd)


@mark.parametrize("ready", list(product([True, False], repeat=4)))
def test_GenICs_provisioned_rundir(atask, ready, driverobj, logcap):
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


@mark.parametrize("ready", list(product([True, False], repeat=3)))
def test_GenICs__ncfile(atask, ready, driverobj, logcap):
    path = driverobj.rundir / "a.nc"
    mocks = [Mock(wraps=atask(x)) for x in ready]
    with (
        patch.object(driverobj, "files_copied", mocks[0]) as files_copied,
        patch.object(driverobj, "files_hardlinked", mocks[1]) as files_hardlinked,
        patch.object(driverobj, "files_linked", mocks[2]) as files_linked,
    ):
        node = driverobj._ncfile(path=path, cmd="touch {ncfile}")
        assert f"netCDF file {path}" in logcap.text
        for x in [files_copied, files_hardlinked, files_linked]:
            x.assert_called_once_with()
        assert node.ready is all(ready)


def test_GenICs_driver_name(driverobj):
    assert driverobj.driver_name() == "aigfs_ics"


def test_GenICs__ncfiles_to_cmds(varkit):
    driverobj, expected = varkit
    mapping = driverobj._ncfiles_to_cmds
    assert mapping == expected


def test_GenICs__ncfiles_to_cmds__bad_grib_filenames(varkit):
    driverobj, _ = varkit
    config = driverobj._config["files_to_link"]
    key = next(iter(config))
    config[key.replace("t00z", "z00t")] = config[key]
    with raises(ValueError, match="GRIB files don't have names expected by this driver!"):
        assert driverobj._ncfiles_to_cmds
