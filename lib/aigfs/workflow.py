import fcntl
import inspect
import logging
import os
import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from iotaa import Asset, collection, external, task
from uwtools.api.driver import Driver

from aigfs import setup
from aigfs.drivers.ics import AIGFSICs
from aigfs.drivers.inference import AIGFSInference
from aigfs.drivers.post import AIGFSPost
from aigfs.strings import STR

type CycleT = datetime | str

PWD = Path(os.environ["PWD"])
CFG = PWD / STR.aigfs_yaml
CMD = f"podman run -v .:{PWD} ghcr.io/maddenp-cu/aigfs:latest run cmd"


# Public tasks:


@task
def config(cycle_: CycleT) -> Iterator:
    _, taskname = _dt_taskname(cycle_, "config")
    yield taskname
    yield Asset(CFG, CFG.is_file)
    yield None
    user = PWD / STR.user_yaml
    c = setup.compose_configs(workflow=None, platform=STR.oci, user_config_files=[user])
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
        key_path=[STR.forecast],
        schema_file=_schema(cls),
    )
    assets = [Asset(path, path.is_file) for path in driver.output[STR.forecast]]
    yield assets
    yield prep(dt)
    _run(driver, taskname, assets)


@collection
def post(cycle_: CycleT) -> Iterator:
    dt, taskname = _dt_taskname(cycle_, "post")
    yield taskname
    cls = AIGFSInference
    driver = cls(
        cycle=dt,
        config=CFG,
        key_path=[STR.forecast],
        schema_file=_schema(cls),
    )
    yield [_post_one_leadtime(dt, path) for path in driver.output[STR.forecast]]


@task
def prep(cycle_: CycleT) -> Iterator:
    dt, taskname = _dt_taskname(cycle_, "prep")
    yield taskname
    cls = AIGFSICs
    driver = cls(
        cycle=dt,
        config=CFG,
        key_path=[STR.prep],
        schema_file=_schema(cls),
    )
    path = driver.output[STR.ics]
    assets = [Asset(path, path.is_file)]
    yield assets
    yield _timegate(dt)
    _run(driver, taskname, assets)


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
        key_path=[STR.post],
        schema_file=_schema(cls),
    )
    # Assets are delivered indexes; fallback is generated indexes:
    output = driver.output
    paths = output.get(STR.delivered, output[STR.idx])
    assets = [Asset(path, path.is_file) for path in paths]
    yield assets
    yield _forecast_one_leadtime(dt, gribfile)
    _run(driver, taskname, assets)


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


def _run(driver: Driver, taskname: str, assets: list[Asset]) -> None:
    """
    Run the driver, unless another process is already running it, or its assets are ready.

    A non-blocking exclusive flock on a per-task lock file in the driver's run directory provides
    mutual exclusion between concurrent workflow invocations. The lock is released when the file is
    closed, including on process exit.
    """
    driver.rundir.mkdir(parents=True, exist_ok=True)
    lockfile = driver.rundir / ("%s.lock" % re.sub(r"[^\w.-]", "_", taskname))
    with lockfile.open("w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logging.info("%s: Running in another process", taskname)
            return
        if all(asset.ready() for asset in assets):
            logging.info("%s: Made ready by another process", taskname)
            return
        driver.run(iotaa={"root": True})


def _schema(cls: type) -> Path:
    return Path(inspect.getfile(cls)).with_suffix(".jsonschema")
