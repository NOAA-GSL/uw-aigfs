"""
Support for user-defined hook commands run by the AIGFS drivers.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

from uwtools.api.utils import run_shell_cmd

from aigfs.strings import STR

# Drivers whose output is not associated with a forecast leadtime:
_NO_LEADTIME = {STR.aigfs_ics}


def run_post_write_hook(
    cmd: str | None,
    driver_name: str,
    cycle: datetime,
    paths: dict[str, Path],
    lead: int | None = None,
) -> None:
    """
    Run a user-defined post-write hook command, if one is defined.

    :param cmd: The shell command to run, or None to do nothing.
    :param driver_name: Name of the driver running the hook.
    :param cycle: The forecast cycle.
    :param paths: Environment-variable names mapped to just-written paths, exported to the command.
    :param lead: Forecast leadtime hours: Required for leadtime-based drivers, else forbidden.
    :raises: ValueError if lead is specified or omitted inappropriately for the driver.
    """
    if (lead is None) != (driver_name in _NO_LEADTIME):
        msg = "Leadtime must %sbe specified for driver %s" % (
            "not " if lead is not None else "",
            driver_name,
        )
        raise ValueError(msg)
    if not cmd:
        return
    env = {
        **os.environ,
        "CYCLE": cycle.strftime("%Y-%m-%dT%H:%M:%S"),
        **{k: str(v) for k, v in paths.items()},
    }
    if lead is None:
        env.pop("LEADTIME", None)
    else:
        env["LEADTIME"] = str(lead)
    success, _ = run_shell_cmd(cmd=cmd, env=dict(sorted(env.items())), taskname=STR.post_write_hook)
    if not success:
        logging.warning("%s failed", STR.post_write_hook)
