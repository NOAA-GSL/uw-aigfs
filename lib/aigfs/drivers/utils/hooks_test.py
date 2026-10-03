import os
from unittest.mock import patch

from pytest import fixture, mark

from aigfs.drivers.utils import hooks
from aigfs.strings import STR

# Fixtures


@fixture
def cycle(utc):
    return utc(2025, 10, 1, 18)


# Tests


@mark.parametrize(("driver_name", "lead"), [(STR.aigfs_ics, None), (STR.aigfs_post, 6)])
def test_drivers_utils_hooks_run_post_write_hook__no_cmd(cycle, driver_name, lead):
    with patch.object(hooks, "run_shell_cmd") as run_shell_cmd:
        hooks.run_post_write_hook(
            cmd=None, driver_name=driver_name, cycle=cycle, paths={}, lead=lead
        )
    run_shell_cmd.assert_not_called()


def test_drivers_utils_hooks_run_post_write_hook__leadtime(cycle, tmp_path):
    out = tmp_path / "hook.out"
    hooks.run_post_write_hook(
        cmd=f"echo $CYCLE $LEADTIME $PATH_A >{out}",
        driver_name=STR.aigfs_post,
        cycle=cycle,
        paths={"PATH_A": tmp_path / "a"},
        lead=6,
    )
    assert out.read_text().strip() == f"2025-10-01T18:00:00 6 {tmp_path / 'a'}"


def test_drivers_utils_hooks_run_post_write_hook__no_leadtime(cycle, tmp_path):
    out = tmp_path / "hook.out"
    # A LEADTIME value in the calling environment must not leak into a no-leadtime hook:
    with patch.dict(os.environ, {"LEADTIME": "42"}):
        hooks.run_post_write_hook(
            cmd=f"echo $CYCLE ${{LEADTIME-unset}} $PATH_A >{out}",
            driver_name=STR.aigfs_ics,
            cycle=cycle,
            paths={"PATH_A": tmp_path / "a"},
        )
    assert out.read_text().strip() == f"2025-10-01T18:00:00 unset {tmp_path / 'a'}"


def test_drivers_utils_hooks_run_post_write_hook__failure(cycle, logcap):
    hooks.run_post_write_hook(cmd="false", driver_name=STR.aigfs_ics, cycle=cycle, paths={})
    assert "post_write_hook failed" in logcap.text


@mark.parametrize(
    ("driver_name", "lead", "msg"),
    [
        (STR.aigfs_ics, 6, "Leadtime must not be specified for driver aigfs_ics"),
        (STR.aigfs_inference, None, "Leadtime must be specified for driver aigfs_inference"),
        (STR.aigfs_post, None, "Leadtime must be specified for driver aigfs_post"),
    ],
)
def test_drivers_utils_hooks_run_post_write_hook__bad_lead(cycle, driver_name, lead, msg, logcap):
    with patch.object(hooks, "run_shell_cmd") as run_shell_cmd:
        hooks.run_post_write_hook(
            cmd="true", driver_name=driver_name, cycle=cycle, paths={}, lead=lead
        )
    assert msg in logcap.text
    run_shell_cmd.assert_not_called()
