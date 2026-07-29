#!/usr/bin/env python3

import argparse
import logging
import sys
from pathlib import Path

from uwtools.api import rocoto
from uwtools.api.config import YAMLConfig, get_yaml_config, realize
from uwtools.api.logging import use_uwtools_logger

sys.path.append(str(Path(__file__).parent.parent))

from ush.validation import Config, validate


def generate_rocoto_files(
    experiment_config: YAMLConfig,
    experiment_file: Path,
    app_home: Path,
    user_config: YAMLConfig,
    validated: Config,
) -> None:
    """
    Generate the Rocoto XML and the experiment YAML.
    """
    workflow_config = get_yaml_config(
        get_yaml_config(app_home / "parm" / "wflow" / "rocoto" / "aigfs_base.yaml")
    )
    for config in (experiment_config, user_config):
        workflow_config.update_from(config)
    realize(
        input_config=workflow_config,
        output_file=experiment_file,
        update_config={"user": {"app_home": str(app_home)}},
    )
    rocoto_xml = experiment_file.parent / "rocoto.xml"
    rocoto_valid = rocoto.realize(config=experiment_file, output_file=rocoto_xml)
    if not rocoto_valid:
        logging.error("Invalid Rocoto XML")
        sys.exit(1)


def main():
    """
    Stage the workflow manager artifacts and experiment YAML in the experiment directory.
    """
    user_config_files = parse_args()
    experiment_config, user_config, app_home = prepare_configs(user_config_files)
    validated = validate(experiment_config.as_dict())
    experiment_dir, experiment_file = setup_experiment_directory(validated)
    generate_rocoto_files(
        experiment_config, experiment_file, app_home, user_config, experiment_config
    )


def parse_args() -> list[Path]:
    """
    Parse command-line arguments.
    """
    use_uwtools_logger()
    parser = argparse.ArgumentParser(description="Configure an experiment from user config files.")
    parser.add_argument(
        "user_config_files",
        help="paths to the user config files",
        metavar="PATH",
        nargs="+",
        type=Path,
    )
    return parser.parse_args().user_config_files


def prepare_configs(user_config_files: list[Path]) -> tuple[YAMLConfig, YAMLConfig, Path]:
    """
    Combine base, user, and platform configs into one experiment config.
    """
    # Set up the experiment.
    app_home = Path(__file__).parent.parent.resolve()
    experiment_config = app_home / "ush" / "default_config.yaml"
    user_config = get_yaml_config({})
    for cfg_file in user_config_files:
        cfg = get_yaml_config(cfg_file)
        user_config.update_from(cfg)
        experiment_config.update_from(cfg)
    machine = experiment_config["user"]["platform"]
    platform_config = get_yaml_config(app_home / "parm" / "machines" / f"{machine}.yaml")

    # Make sure user_config is last to override any settings from supplementals
    for supp_config in (platform_config, user_config):
        experiment_config.update_from(supp_config)
    experiment_config.dereference()
    return experiment_config, user_config, app_home


def setup_experiment_directory(validated: Config) -> tuple[Path, Path]:
    """
    Create the experiment directory and write experiment.yaml.
    """
    experiment_dir = validated.user.experiment_dir
    logging.info("Experiment will be set up here: %s", experiment_dir)
    experiment_dir.mkdir(parents=True, exist_ok=True)
    experiment_file = experiment_dir / "experiment.yaml"
    return experiment_dir, experiment_file


if __name__ == "__main__":
    main()  # pragma: no cover
