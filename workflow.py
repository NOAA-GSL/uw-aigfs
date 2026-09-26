import inspect
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import FrameType
from typing import cast

from aigfs import setup
from aigfs.drivers.ics import AIGFSICs
from aigfs.drivers.inference import AIGFSInference
from aigfs.drivers.post import AIGFSPost
from iotaa import Asset, external, task

type CycleT = datetime | str

DIR = Path("/home/maddenp/git/uw-aigfs")  # /run/aigfs
CFG = DIR / "aigfs.yaml"
CMD = f"podman run -v .:{DIR} ghcr.io/maddenp-cu/aigfs:latest run cmd"


@task
def config(cycle_: CycleT) -> Iterator:
    step = cast(FrameType, inspect.currentframe()).f_code.co_name
    _, taskname = _dt_taskname(cycle_, step)
    yield taskname
    yield Asset(CFG, CFG.is_file)
    yield None
    user = DIR / "user.yaml"
    c = setup.compose_configs(workflow=None, platform="oci", user_config_files=[user])
    setup.validate(c)
    setup.set_up_rundir(c, workflow=None, prefix=taskname)


@task
def forecast(cycle_: CycleT) -> Iterator:
    step = cast(FrameType, inspect.currentframe()).f_code.co_name
    dt, taskname = _dt_taskname(cycle_, step)
    yield taskname
    class_ = AIGFSInference
    schema = _schema(class_)
    driver = class_(cycle=dt, config=CFG, key_path=[step], schema_file=schema)
    yield [Asset(path, path.is_file) for path in driver.output["forecasts"]]
    yield prep(dt)
    driver.run(iotaa={"root": True})


@task
def post_one_leadtime(cycle_: CycleT, leadtime: int | timedelta) -> Iterator:
    leadtime = leadtime if isinstance(leadtime, timedelta) else timedelta(hours=leadtime)
    fff = "%03d" % (leadtime.total_seconds() / 3600)
    dt, taskname = _dt_taskname(cycle_, f"{fff} post")
    yield taskname
    class_ = AIGFSPost
    schema = _schema(class_)
    driver = class_(cycle=dt, leadtime=leadtime, config=CFG, key_path=["post"], schema_file=schema)
    yield [Asset(path, path.is_file) for path in driver.output["idx"]]
    yield forecast(dt)
    driver.run(iotaa={"root": True})


@task
def prep(cycle_: CycleT) -> Iterator:
    step = cast(FrameType, inspect.currentframe()).f_code.co_name
    dt, taskname = _dt_taskname(cycle_, step)
    yield taskname
    class_ = AIGFSICs
    schema = _schema(class_)
    driver = class_(cycle=dt, config=CFG, key_path=[step], schema_file=schema)
    path = driver.output["ics"]
    yield Asset(path, path.is_file)
    yield _timegate(dt)
    driver.run(iotaa={"root": True})


@external
def _timegate(cycle_: datetime) -> Iterator:
    cutoff = cycle_ + timedelta(hours=3, minutes=35)
    yield "UTC > %s" % cutoff.replace(tzinfo=None)
    yield Asset(None, lambda: datetime.now(UTC) > cutoff)


def _dt_taskname(cycle_: CycleT, step: str) -> tuple[datetime, str]:
    dt = (
        datetime.fromisoformat(cycle_).replace(tzinfo=timezone.utc)
        if isinstance(cycle_, str)
        else cycle_
    )
    return dt, "%s %s" % (dt.strftime("%Y%m%d %HZ"), step)


def _schema(class_: type) -> Path:
    return Path(inspect.getfile(class_)).with_suffix(".jsonschema")
