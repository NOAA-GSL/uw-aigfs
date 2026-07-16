#!/usr/bin/env python3

from uwtools.api.config import get_yaml_config

def main():
    """
    Stage the workflow manager artifacts and experiment YAML in the experiment directory.
    """
    user_config_files = parse_args()
    experiment_config, user_config, app_home = prepare_configs(user_config_files)
    #validated = validate(experiment_config.as_dict())
    experiment_dir, experiment_file = setup_experiment_directory(validated)
    #generate_workflow_files(experiment_config, experiment_file, app_home, user_config, validated)
    #stage_grid_files(experiment_config, experiment_dir)


def parse_args() -> list[Path]:
    """
    Parse command-line arguments.
    """
    use_uwtools_logger()
    parser = argparse.ArgumentParser(
        description="Configure an experiment with the following input:"
    )
    parser.add_argument("user_config_files", nargs="+", help="Paths to the user config files.")
    return [Path(p) for p in parser.parse_args().user_config_files]

def prepare_configs(user_config_files: list[Path]) -> tuple[YAMLConfig, YAMLConfig, Path]:
    """
    Combine base, user, and platform configs into one experiment config.
    """
    # Set up the experiment
    experiment_config = get_yaml_config(Path("./default_config.yaml"))
    user_config = get_yaml_config({})
    for cfg_file in user_config_files:
        cfg = get_yaml_config(cfg_file)
        user_config.update_from(cfg)
        experiment_config.update_from(cfg)
    app_home = Path(__file__).parent.parent.resolve()
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
