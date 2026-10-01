from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from pytest import fixture, mark

from aigfs import workflow
from aigfs.drivers.inference import AIGFSInference

# Fixtures


@fixture
def cfg(tmp_path):
    path = tmp_path / "aigfs.yaml"
    with patch.object(workflow, "CFG", path), patch.object(workflow, "PWD", tmp_path):
        yield path


@fixture
def cycle(utc):
    return utc(2025, 10, 1, 18)


@fixture
def gribfiles(tmp_path):
    return [tmp_path / ("aigfs.t18z.pres.f%03d.grib2" % h) for h in (6, 12)]


def driver(output: dict) -> Mock:
    obj = Mock(output=output)
    return Mock(return_value=obj)


# Tests


def test_workflow_config__exists(cfg, cycle, touch):
    touch(cfg)
    with patch.object(workflow, "setup") as setup:
        node = workflow.config(cycle)
    assert node.ready
    assert node.taskname == "20251001 18Z config"
    setup.compose_configs.assert_not_called()


@mark.usefixtures("cfg")
def test_workflow_config__missing(tmp_path):
    with patch.object(workflow, "setup") as setup:
        node = workflow.config("2025-10-01T18")
    assert not node.ready
    setup.compose_configs.assert_called_once_with(
        workflow=None, platform="oci", user_config_files=[tmp_path / "user.yaml"]
    )
    c = setup.compose_configs.return_value
    setup.validate.assert_called_once_with(c)
    setup.set_up_rundir.assert_called_once_with(c, workflow=None, prefix="20251001 18Z config")


@mark.parametrize("ready", [True, False])
def test_workflow_forecast(atask, cfg, cycle, gribfiles, ready):
    cls = driver({"forecast": gribfiles})
    with (
        patch.object(workflow, "AIGFSInference", cls),
        patch.object(workflow, "_schema", return_value=Path("/s")),
        patch.object(workflow, "prep", Mock(wraps=lambda _: atask(ready))) as prep,
    ):
        run = cls.return_value.run
        if ready:
            run.side_effect = lambda *_, **_k: [gribfile.touch() for gribfile in gribfiles]
        node = workflow.forecast(cycle)
    assert node.taskname == "20251001 18Z forecast"
    cls.assert_called_once_with(
        cycle=cycle, config=cfg, key_path=["forecast"], schema_file=Path("/s")
    )
    prep.assert_called_once_with(cycle)
    assert node.ready is ready
    if ready:
        run.assert_called_once_with(iotaa={"root": True})
    else:
        run.assert_not_called()


@mark.parametrize("ready", [True, False])
def test_workflow_post(atask, cfg, cycle, gribfiles, ready):
    cls = driver({"forecast": gribfiles})
    with (
        patch.object(workflow, "AIGFSInference", cls),
        patch.object(workflow, "_schema", return_value=Path("/s")),
        patch.object(
            workflow, "_post_one_leadtime", Mock(wraps=lambda *_: atask(ready=ready))
        ) as _post_one_leadtime,
    ):
        node = workflow.post(cycle)
    assert node.ready is ready
    assert node.taskname == "20251001 18Z post"
    cls.assert_called_once_with(
        cycle=cycle, config=cfg, key_path=["forecast"], schema_file=Path("/s")
    )
    for path in gribfiles:
        _post_one_leadtime.assert_any_call(cycle, path)


@mark.parametrize("ready", [True, False])
def test_workflow_prep(atask, cfg, cycle, ready, tmp_path):
    ics = tmp_path / "ics.nc"
    cls = driver({"ics": ics})
    with (
        patch.object(workflow, "AIGFSICs", cls),
        patch.object(workflow, "_schema", return_value=Path("/s")),
        patch.object(workflow, "_timegate", Mock(wraps=lambda _: atask(ready))) as _timegate,
    ):
        run = cls.return_value.run
        if ready:
            run.side_effect = lambda *_, **_k: ics.touch()
        node = workflow.prep(cycle)
    assert node.taskname == "20251001 18Z prep"
    cls.assert_called_once_with(cycle=cycle, config=cfg, key_path=["prep"], schema_file=Path("/s"))
    _timegate.assert_called_once_with(cycle)
    assert node.ready is ready
    if ready:
        run.assert_called_once_with(iotaa={"root": True})
    else:
        run.assert_not_called()


@mark.parametrize("ready", [True, False])
def test_workflow__forecast_one_leadtime(atask, cycle, gribfiles, ready, touch):
    path = gribfiles[0]
    if ready:
        touch(path)
    with patch.object(workflow, "forecast", Mock(wraps=lambda _: atask(ready=True))) as forecast:
        node = workflow._forecast_one_leadtime(cycle, path)
    assert node.taskname == f"20251001 18Z {path}"
    assert node.ready is ready
    forecast.assert_called_once_with(cycle)


@mark.parametrize("ready", [True, False])
def test_workflow__post_one_leadtime(atask, cfg, cycle, gribfiles, ready):
    path = gribfiles[1]
    cls = driver({})
    with (
        patch.object(workflow, "AIGFSPost", cls),
        patch.object(workflow, "_schema", return_value=Path("/s")),
        patch.object(
            workflow, "_forecast_one_leadtime", Mock(wraps=lambda *_: atask(ready))
        ) as _forecast_one_leadtime,
    ):
        run = cls.return_value.run
        if ready:
            run.side_effect = lambda *_, **_k: Path(f"{path}.idx").touch()
        node = workflow._post_one_leadtime(cycle, path)
    assert node.taskname == "20251001 18Z 012 post"
    _forecast_one_leadtime.assert_called_once_with(cycle, path)
    assert node.ready is ready
    if ready:
        cls.assert_called_once_with(
            cycle=cycle,
            leadtime=timedelta(hours=12),
            config=cfg,
            key_path=["post"],
            schema_file=Path("/s"),
        )
        cls.return_value.run.assert_called_once_with(iotaa={"root": True})
    else:
        cls.assert_not_called()


@mark.parametrize(("hours", "ready"), [(-4, True), (0, False)])
def test_workflow__timegate(hours, ready):
    dt = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=hours)
    node = workflow._timegate(dt)
    assert node.ready is ready
    cutoff = dt + timedelta(hours=3, minutes=35)
    assert node.taskname == "UTC > %s" % cutoff.replace(tzinfo=None)


def test_workflow__dt_taskname(cycle):
    assert workflow._dt_taskname(cycle, "foo") == (cycle, "20251001 18Z foo")
    assert workflow._dt_taskname("2025-10-01T18", "foo") == (cycle, "20251001 18Z foo")


def test_workflow__schema():
    path = workflow._schema(AIGFSInference)
    assert path.name == "inference.jsonschema"
    assert path.is_file()
