import inspect
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from aigfs import setup
from aigfs.drivers.ics import AIGFSICs
from aigfs.drivers.inference import AIGFSInference
from aigfs.drivers.post import AIGFSPost
from iotaa import Asset, collection, external, task

type CycleT = datetime | str

DIR = Path("/home/maddenp/git/uw-aigfs")  # /run/aigfs
CFG = DIR / "aigfs.yaml"
CMD = f"podman run -v .:{DIR} ghcr.io/maddenp-cu/aigfs:latest run cmd"


@task
def config(cycle_: CycleT) -> Iterator:
    _, taskname = _dt_taskname(cycle_, "config")
    yield taskname
    yield Asset(CFG, CFG.is_file)
    yield None
    user = DIR / "user.yaml"
    c = setup.compose_configs(workflow=None, platform="oci", user_config_files=[user])
    setup.validate(c)
    setup.set_up_rundir(c, workflow=None, prefix=taskname)


@task
def forecast(cycle_: CycleT) -> Iterator:
    dt, taskname = _dt_taskname(cycle_, "forecast")
    yield taskname
    class_ = AIGFSInference
    schema = _schema(class_)
    driver = class_(cycle=dt, config=CFG, key_path=["forecast"], schema_file=schema)
    yield [Asset(path, path.is_file) for path in driver.output["forecasts"]]
    yield prep(dt)
    driver.run(iotaa={"root": True})


@collection
def post(cycle_: CycleT) -> Iterator:
    dt, taskname = _dt_taskname(cycle_, "post")
    yield taskname
    class_ = AIGFSInference
    schema = _schema(class_)
    driver = class_(cycle=dt, config=CFG, key_path=["forecast"], schema_file=schema)
    yield [_post_one_leadtime(dt, path) for path in driver.output["forecasts"]]


@task
def prep(cycle_: CycleT) -> Iterator:
    dt, taskname = _dt_taskname(cycle_, "prep")
    yield taskname
    class_ = AIGFSICs
    schema = _schema(class_)
    driver = class_(cycle=dt, config=CFG, key_path=["prep"], schema_file=schema)
    path = driver.output["ics"]
    yield Asset(path, path.is_file)
    yield _timegate(dt)
    driver.run(iotaa={"root": True})


@task
def _forecast_one_leadtime(dt: datetime, gribfile: Path) -> Iterator:
    dt, taskname = _dt_taskname(dt, str(gribfile))
    yield taskname
    yield Asset(gribfile, gribfile.is_file)
    yield forecast(dt)


@task
def _post_one_leadtime(dt: datetime, gribfile: Path) -> Iterator:
    idxfile = Path(f"{gribfile}.idx")
    dt, taskname = _dt_taskname(dt, str(idxfile))
    yield taskname
    yield Asset(idxfile, idxfile.is_file)
    yield _forecast_one_leadtime(dt, gribfile)
    leadtime = timedelta(hours=int(str(gribfile.name).split(".")[3][1:]))
    class_ = AIGFSPost
    schema = _schema(class_)
    driver = class_(cycle=dt, leadtime=leadtime, config=CFG, key_path=["post"], schema_file=schema)
    driver.run(iotaa={"root": True})


@external
def _timegate(dt: datetime) -> Iterator:
    cutoff = dt + timedelta(hours=3, minutes=35)
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
