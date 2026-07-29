import logging
import sys
from functools import cached_property
from pathlib import Path
from shutil import copy

from iotaa import Asset, Node, collection, external, task
from uwtools.api.driver import DriverCycleLeadtimeBased
from uwtools.utils.processing import run_shell_cmd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.exceptions import ConfigError
from utils.tasks import file


class AIGFSPost(DriverCycleLeadtimeBased):
    @collection
    def delivery(self):
        """
        Output files copied to destination.
        """
        yield "Delivered output"
        d = self._deliver_to
        if isinstance(d, Path):
            yield [self._delivered(path) for path in self._delivered2idx.keys()]
        else:
            yield d

    @collection
    def provisioned_rundir(self):
        """
        Run directory provisioned with all required content.
        """
        yield self.taskname("provisioned run directory")
        required = [self.runscript()]
        yield required

    @collection
    def wgrib2_tasks(self, threads=2):
        """
        Map wgrib2 executions to tasks.
        """
        yield "wgrib2 tasks"
        yield [self._single_shell_command(cmd) for cmd in self._wgrib2_commands]

    @task
    def _delivered(self, path: Path):
        yield f"Delivered GRIB index {path}"
        yield Asset(path, path.is_file)
        req = self._idx(self._delivered2idx[path])
        yield req
        path.parent.mkdir(parents=True, exist_ok=True)
        copy(req.ref, path)
        logging.debug(f"Copied {req.ref} -> {path}")

    @external
    def _gribfile(self, path: Path):
        yield f"GRIB file {path}"
        yield Asset(path, path.is_file)
        
    @task
    def _idx(self, path: Path):
        taskname = f"GRIB index {path}"
        yield taskname
        yield Asset(path, path.is_file)
        req = self._gribfile(self._idx2grib[path])
        yield req
        path.parent.mkdir(parents=True, exist_ok=True)
        cmd = f"wgrib2 -s {req.ref} >{path}.tmp && mv {path}.tmp {path}"
        run_shell_cmd(cmd, cwd=path.parent, taskname=taskname)

    @task
    def _single_shell_command(self, cmd: str):
        """
        Run a shell command.
        """
        path = self.rundir / cmd.split()[-1]
        taskname = f"Running wgrib2 command: {cmd}"
        yield taskname
        yield Asset(path, path.is_file)
        yield [file(fp) for fp in self.config["inputfiles"]]
        run_shell_cmd(cmd=cmd, cwd=self.rundir, taskname=taskname)

    @external
    def _valid_driver_config(self, reason: str):
        yield reason
        yield Asset(None, lambda: False)

    # Public helper methods

    @classmethod
    def driver_name(cls) -> str:
        """
        Returns the name of this driver.
        """
        return "aigfs_post"

    @property
    def output(self) -> dict[str, Path] | dict[str, list[Path]]:
        """
        Returns a description of the file(s) created when this component runs.
        """
        return {"idx": self._idxmap.keys()}

    # Private helper methods

    @cached_property
    def _deliver_to(self) -> Path | Node:
        key = "deliver_to"
        if key in self.config:
            return Path(self.config[key])
        else:
            reason = f"Definition of '{key}' in 'delivery' task config block"
            return self._valid_driver_config(reason)

    @cached_property
    def _delivered2idx(self) -> dict[Path, Path]:
        d = self._deliver_to
        assert isinstance(d, Path)
        srcs = self._idx2grib.keys()
        dsts = [d / x.name for x in srcs]
        return dict(zip(dsts, srcs))

    @cached_property
    def _idx2grib(self) -> dict[Path, Path]:
        srcs = [Path(x) for x in self.config["inputfiles"]]
        dsts = [Path(self.config["outputdir"], x.name).with_suffix(".idx") for x in srcs]
        return dict(zip(dsts, srcs))

    @cached_property
    def _wgrib2_commands(self):
        """
        Generate wgrib2 commands to run for this task.
        """
        wgrib2_commands = []
        inputfiles = self.config["inputfiles"]
        idxfiles = self.output["idx"]
        for infile, idxfile in zip(inputfiles, idxfiles):
            wgrib2_commands.append(
                f"wgrib2 -s {infile} > {idxfile}.tmp && mv {idxfile}.tmp {idxfile}"
            )
        return wgrib2_commands
