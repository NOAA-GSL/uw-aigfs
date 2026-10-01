import inspect
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from iotaa import Asset, collection, external, task

from aigfs import setup
from aigfs.drivers.ics import AIGFSICs
from aigfs.drivers.inference import AIGFSInference
from aigfs.drivers.post import AIGFSPost
from aigfs.strings import STR

type CycleT = datetime | str

PWD = Path(os.environ["PWD"])
CFG = PWD / "aigfs.yaml"
CMD = f"podman run -v .:{PWD} ghcr.io/maddenp-cu/aigfs:latest run cmd"


# Public tasks:


@task
def config(cycle_: CycleT) -> Iterator:
    _, taskname = _dt_taskname(cycle_, "config")
    yield taskname
    yield Asset(CFG, CFG.is_file)
    yield None
    user = PWD / "user.yaml"
    c = setup.compose_configs(workflow=None, platform="oci", user_config_files=[user])
    setup.validate(c)
    setup.set_up_rundir(c, workflow=None, prefix=taskname)


@task
def forecast(cycle_: CycleT) -> Iterator:
    dt, taskname = _dt_taskname(cycle_, "forecast")
    yield taskname
    cls = AIGFSInference
    driver = cls(
        cycle=dt,
        config=CFG,
        key_path=["forecast"],
        schema_file=_schema(cls),
    )
    yield [Asset(path, path.is_file) for path in driver.output["forecast"]]
    yield prep(dt)
    driver.run(iotaa={"root": True})


@collection
def post(cycle_: CycleT) -> Iterator:
    dt, taskname = _dt_taskname(cycle_, "post")
    yield taskname
    cls = AIGFSInference
    driver = cls(
        cycle=dt,
        config=CFG,
        key_path=["forecast"],
        schema_file=_schema(cls),
    )
    yield [_post_one_leadtime(dt, path) for path in driver.output["forecast"]]


@task
def prep(cycle_: CycleT) -> Iterator:
    dt, taskname = _dt_taskname(cycle_, "prep")
    yield taskname
    cls = AIGFSICs
    driver = cls(
        cycle=dt,
        config=CFG,
        key_path=["prep"],
        schema_file=_schema(cls),
    )
    path = driver.output["ics"]
    yield Asset(path, path.is_file)
    yield _timegate(dt)
    driver.run(iotaa={"root": True})


# Private tasks:


@task
def _forecast_one_leadtime(dt: datetime, gribfile: Path) -> Iterator:
    dt, taskname = _dt_taskname(dt, str(gribfile))
    yield taskname
    yield Asset(gribfile, gribfile.is_file)
    yield forecast(dt)


@task
def _post_one_leadtime(dt: datetime, gribfile: Path) -> Iterator:
    # e.g. aigfs.t00z.pres.f018.grib2
    #                       fff
    fff = str(gribfile.name).split(".")[3][1:]
    dt, taskname = _dt_taskname(dt, "%s %s" % (fff, "post"))
    yield taskname
    cls = AIGFSPost
    driver = cls(
        cycle=dt,
        leadtime=timedelta(hours=int(fff)),
        config=CFG,
        key_path=["post"],
        schema_file=_schema(cls),
    )
    # Done when indexes are delivered, if delivery is configured, else when they are generated:
    output = driver.output
    paths = output.get(STR.delivered, output[STR.idx])
    yield [Asset(path, path.is_file) for path in paths]
    yield _forecast_one_leadtime(dt, gribfile)
    driver.run(iotaa={"root": True})


@external
def _timegate(dt: datetime) -> Iterator:
    cutoff = dt + timedelta(hours=3, minutes=35)
    yield "UTC > %s" % cutoff.replace(tzinfo=None)
    yield Asset(None, lambda: datetime.now(UTC) > cutoff)


# Private helpers:


def _dt_taskname(cycle_: CycleT, step: str) -> tuple[datetime, str]:
    dt = (
        datetime.fromisoformat(cycle_).replace(tzinfo=timezone.utc)
        if isinstance(cycle_, str)
        else cycle_
    )
    return dt, "%s %s" % (dt.strftime("%Y%m%d %HZ"), step)


def _schema(cls: type) -> Path:
    return Path(inspect.getfile(cls)).with_suffix(".jsonschema")
