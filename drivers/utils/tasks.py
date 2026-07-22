"""
Reusable tasks for the AIGFS drivers
"""

from pathlib import Path
from iotaa import Asset
from uwtools.utils.processing import run_shell_cmd


@external
def file(path: Path | str):
    """
    An existing file.

    :param path: Path to the file.
    """
    path = Path(path)
    yield "File %s" % (path)
    yield Asset(path, path.is_file)


@task
def single_shell_command(, cmd: str):
    """
    Run a shell command.
    """
    path = self.rundir / cmd.split()[-1]
    taskname = f"Running wgrib2 command: {cmd}"
    yield taskname
    yield Asset(path, path.is_file)
    yield [file(fp) for fp in self.config["inputfiles"]]
    run_shell_cmd(cmd=cmd, cwd=self.rundir, taskname=taskname)

