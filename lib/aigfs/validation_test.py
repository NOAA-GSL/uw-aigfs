from datetime import timedelta

from pydantic import ValidationError
from pytest import fixture, mark, raises

from aigfs import validation


@fixture
def app(args_app):
    return validation.App(**args_app)


@fixture
def args_app(tmp_path, utc):
    return dict(
        cycle_freq=timedelta(hours=1),
        first_cycle=utc(2026, 1, 1, 0),
        home=tmp_path,
        last_cycle=utc(2026, 1, 31, 23),
        modeldir=tmp_path,
        platform=validation.Platform(
            name="jet",
            partition=validation.Partition(
                compute="p-compute",
                netaccess="p-netaccess",
                task="p-task",
            ),
            scheduler=validation.Scheduler(
                account="me",
                type="slurm",
            ),
        ),
        rundir=tmp_path,
    )


@mark.parametrize("compute", ["a", None])
@mark.parametrize("netaccess", ["b", None])
@mark.parametrize("task", ["c", None])
def test_validation_Partition(compute, netaccess, task):
    if any([compute, netaccess, task]):
        obj = validation.Partition(compute=compute, netaccess=netaccess, task=task)
        mapping = {compute: obj.compute, netaccess: obj.netaccess, task: obj.task}.items()
        for expected, actual in mapping:
            assert expected == actual
    else:  # if no partitions are specified
        with raises(ValidationError) as e:
            validation.Partition(compute=compute, netaccess=netaccess, task=task)
        assert e.value.error_count() == 1
        msg = "Specify at least one partition name (compute, netaccess, task)"
        assert msg in e.value.errors()[0]["msg"]


def test_validation_Scheduler():
    for val in ["pbs", "slurm"]:
        assert validation.Scheduler(type=val).type == val  # type: ignore[arg-type]
    obj = validation.Scheduler(account="me", type="slurm")
    assert obj.account == "me"
    assert obj.type == "slurm"


def test_validation_Scheduler_bad_type():
    with raises(ValidationError) as e:
        validation.Scheduler(type="foo")  # type: ignore[arg-type]
    assert e.value.error_count() == 1
    msg = "Input should be 'pbs' or 'slurm'"
    assert msg in e.value.errors()[0]["msg"]


# def test_validation_Platform():
#     obj = validation.Platform(
#         name="ursa",
#         partition=validation.Partition(),
#         scheduler=validation.Scheduler(),
#     )


def test_validation_App(args_app):
    assert validation.App(**args_app)


def test_validation_App_fail(args_app, utc):
    args_app["last_cycle"] = utc(1970, 1, 1, 0)
    with raises(ValueError, match="last_cycle cannot precede first_cycle"):
        validation.App(**args_app)


def test_validation_Config(app):
    args_app = dict(app=app, forecast={}, post={}, prep={}, timevars={})
    assert validation.Config(**args_app)
    args_app["user"] = {}
    assert validation.Config(**args_app)


def test_validation_validate(app):
    config = dict(app=app, forecast={}, post={}, prep={}, timevars={})
    assert validation.validate(config=config)
    config["user"] = {}
    assert validation.validate(config=config)


def test_validation_validate_fail(args_app, logcap):
    del args_app["rundir"]
    with raises(SystemExit) as e:
        validation.validate({"app": args_app})
    assert e.value.code == 1
    assert "Config validation failed:" in logcap.text
    assert "'loc': ('app', 'rundir')" in logcap.text
