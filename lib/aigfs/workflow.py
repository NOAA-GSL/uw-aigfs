import fcntl
import inspect
import logging
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from iotaa import Asset, collection, external, task
from uwtools.api.driver import Driver
from uwtools.api.utils import run_shell_cmd

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
    user = PWD / "user.yaml"
    c = setup.compose_configs(workflow=None, platform=STR.oci, user_config_files=[user])
    setup.validate(c)
    setup.set_up_rundir(c, workflow=None, prefix=taskname)


@task
def forecast(cycle_: CycleT) -> Iterator:
    dt, taskname = _dt_taskname(cycle_, "forecast")
    yield taskname
    cls = AIGFSInference
    key_path: list = [STR.forecast]
    driver = cls(
        cycle=dt,
        config=CFG,
        key_path=key_path,
        schema_file=_schema(cls),
    )
    assets = [Asset(path, path.is_file) for path in driver.output[STR.forecast]]
    yield assets
    yield prep(dt)
    cmd = _cmd(driver, key_path, dt)
    _execute(cmd, driver.rundir, taskname, assets)


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
    key_path: list = [STR.prep]
    driver = cls(
        cycle=dt,
        config=CFG,
        key_path=key_path,
        schema_file=_schema(cls),
    )
    path = driver.output[STR.ics]
    assets = [Asset(path, path.is_file)]
    yield assets
    yield _timegate(dt)
    cmd = _cmd(driver, key_path, dt)
    _execute(cmd, driver.rundir, taskname, assets)


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
    key_path: list = [STR.post]
    leadtime = timedelta(hours=int(fff))
    driver = cls(
        cycle=dt, leadtime=leadtime, config=CFG, key_path=key_path, schema_file=_schema(cls)
    )
    # Assets are delivered indexes; fallback is generated indexes:
    output = driver.output
    paths = output.get(STR.delivered, output[STR.idx])
    assets = [Asset(path, path.is_file) for path in paths]
    yield assets
    yield _forecast_one_leadtime(dt, gribfile)
    cmd = _cmd(driver, key_path, dt, leadtime)
    _execute(cmd, driver.rundir, taskname, assets)


@external
def _timegate(dt: datetime) -> Iterator:
    cutoff = dt + timedelta(hours=3, minutes=35)
    yield "UTC > %s" % cutoff.replace(tzinfo=None)
    yield Asset(None, lambda: datetime.now(UTC) > cutoff)


# Private helpers:


def _cmd(
    driver: Driver,
    key_path: list,
    dt: datetime,
    leadtime: timedelta | None = None,
    prefix: str = "",
) -> str:
    cmd = [
        prefix,
        f"{PWD}/bin/run cmd",
        "uw execute",
        "--module %s" % driver.__module__,
        "--classname %s" % driver.__class__.__name__,
        "--task run",
        "--config %s" % CFG,
        "--key-path %s" % ".".join(key_path),
        "--cycle %s" % dt.strftime("%Y%m%dT%H"),
    ]
    if leadtime is not None:
        cmd.append("--leadtime %s" % int(leadtime.total_seconds() / 3600))
    return " ".join(cmd).strip()


def _dt_taskname(cycle_: CycleT, step: str) -> tuple[datetime, str]:
    dt = (
        datetime.fromisoformat(cycle_).replace(tzinfo=timezone.utc)
        if isinstance(cycle_, str)
        else cycle_
    )
    return dt, "%s %s" % (dt.strftime("%Y%m%d %HZ"), step)


def _execute(cmd: str, rundir: Path, taskname: str, assets: list[Asset]) -> None:

    # flock (exclusive, non-blocking) on a per-task lockfile in the rundir so that only one
    # process at a time runs a specific driver parameterization. The lock is released when the file
    # is closed or the process exits.

    def log(proc):
        for line in proc.stdout:
            logging.info("%s: %s", taskname, line.rstrip("\r\n"))

    rundir.mkdir(parents=True, exist_ok=True)
    lockfile = rundir / (".lock-%s" % taskname.replace(" ", "-"))
    with lockfile.open("w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logging.info("%s: Running in another process", taskname)
            return
        if all(asset.ready() for asset in assets):
            logging.info("%s: Made ready by another process", taskname)
            return
        run_shell_cmd(cmd, callback=log, cwd=rundir, taskname=taskname)


def _schema(cls: type) -> Path:
    return Path(inspect.getfile(cls)).with_suffix(".jsonschema")
