from functools import cache

from pathlib import Path

from iotaa import Asset, collection, task
from uwtools.api.driver import DriverCycleLeadtimeBased
from uwtools.utils.processing import run_shell_cmd
from uwtools.utils.tasks import file


class AIGFSPost(DriverCycleLeadtimeBased):
    @collection
    def provisioned_rundir(self):
        """
        Run directory provisioned with all required content.
        """
        yield self.taskname("provisioned run directory")
        required = [
                self.runscript()]
        yield required

    @collection
    def wgrib2_tasks(self, threads=2):
        """
        Map wgrib2 executions to tasks.
        """
        yield "wgrib2 tasks"
        yield [self._single_shell_command(cmd) for cmd in self._wgrib2_commands()]

    @task
    def delivery(self):
        """
        Ouput files copied to destination.
        """
        yield "Deliver files"
        output_path = Path(self.config["deliver_to"])
        inputfiles = [Path(fp) for fp in self.config["inputfiles"]]
        files = {}
        for fp in (inputfiles, self.ouput["idx"]):
            files[output_path / fp.name] = fp
        yield [Asset(path, (path).is_file) for path in files]
        yield [self.wgrib2_tasks(), Copier(config=files).go("files to deliver")]


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
        return {"idx": [Path(cmd.split()[-1]) for cmd in self._wgrib2_commands]}


    # Private helper methods
    @cache
    def _wgrib2_commands(self):
        """
        Generate wgrib2 commands to run for this task.
        """
        wgrib2_commands = []
        inputfiles = self.config["inputfiles"]
        outputdir = self.config["outputdir"]
        for input_file in inputfiles:
            fp = Path(input_file)
            wgrib2_commands.append(f"wgrib2 -s {fp} > {outputdir}/{fp.name}.idx")
        return wgrib2_commands
