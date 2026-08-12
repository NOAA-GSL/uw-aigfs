import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from pytest import raises

from . import generate_experiment
from .validation import Config, User


def test_ush_generate_experiment_generate_experiment_files(tmp_path):
    experiment_file = tmp_path / "experiment.yaml"
    experiment_config = Mock()
    with (
        patch.object(generate_experiment, "realize") as realize,
        patch.object(generate_experiment, "rocoto") as rocoto,
    ):
        rocoto.realize.return_value = True
        generate_experiment.generate_experiment_files(experiment_config, experiment_file)
    realize.assert_called_once_with(
        input_config=generate_experiment.APP_HOME / "parm" / "wflow" / "rocoto" / "aigfs_base.yaml",
        output_file=experiment_file,
        update_config=experiment_config,
    )
    rocoto.realize.assert_called_once_with(
        config=experiment_file,
        output_file=tmp_path / "rocoto.xml",
    )


def test_ush_generate_experiment_generate_experiment_files_invalid_xml(tmp_path):
    experiment_file = tmp_path / "experiment.yaml"
    with (
        patch.object(generate_experiment, "realize"),
        patch.object(generate_experiment, "rocoto") as rocoto,
    ):
        rocoto.realize.return_value = False
        with raises(SystemExit):
            generate_experiment.generate_experiment_files(Mock(), experiment_file)


def test_ush_generate_experiment_main():
    with (
        patch.object(generate_experiment, "parse_args") as parse_args,
        patch.object(generate_experiment, "prepare_configs") as prepare_configs,
        patch.object(generate_experiment, "validate") as validate,
        patch.object(generate_experiment, "set_up_experiment_directory") as s_u_e_d,
        patch.object(generate_experiment, "generate_experiment_files") as generate_experiment_files,
    ):
        s_u_e_d.return_value = (Mock(), Mock())
        generate_experiment.main()
        parse_args.assert_called_once_with()
        prepare_configs.assert_called_once_with(parse_args())
        validate.assert_called_once_with(prepare_configs().as_dict())
        s_u_e_d.assert_called_once_with(validate())
        generate_experiment_files.assert_called_once_with(prepare_configs(), s_u_e_d()[1])


def test_ush_generate_experiment_parse_args():
    with patch("sys.argv", ["prog", "/path/to/a.yaml", "/path/to/b.yaml"]):
        result = generate_experiment.parse_args()
    assert result == [Path("/path/to/a.yaml"), Path("/path/to/b.yaml")]


def test_ush_generate_experiment_prepare_configs():
    user_config_files = [Path("/tmp/a.yaml")]  # noqa: S108
    mock_user_config = {"user": {"platform": "testmachine"}}
    mock_experiment_config = Mock()
    with patch.object(generate_experiment, "compose") as compose:
        compose.side_effect = [mock_user_config, mock_experiment_config]
        result = generate_experiment.prepare_configs(user_config_files)
    assert result is mock_experiment_config
    mock_experiment_config.update_from.assert_called_once_with(
        {"user": {"app_home": str(generate_experiment.APP_HOME)}}
    )
    # First call: compose user configs
    # Second call: compose with default, platform, and user configs
    assert compose.call_count == 2
    second_call = compose.call_args_list[1]
    assert second_call[1]["configs"] == [
        generate_experiment.APP_HOME / "parm" / "default_config.yaml",
        generate_experiment.APP_HOME / "parm" / "machines" / "testmachine.yaml",
        *user_config_files,
    ]
    assert second_call[1]["realize"] is True


def test_ush_generate_experiment_set_up_experiment_directory(tmp_path, caplog):
    experiment_dir = tmp_path / "myexp"
    validated = Config(
        user=User(
            cycle_freq=timedelta(hours=6),
            experiment_dir=experiment_dir,
            first_cycle=datetime(2025, 10, 1, 18, tzinfo=timezone.utc),
            last_cycle=datetime(2025, 10, 2, 18, tzinfo=timezone.utc),
            platform="test",
        )
    )
    with caplog.at_level(logging.INFO):
        result_dir, result_file = generate_experiment.set_up_experiment_directory(validated)
    assert result_dir == experiment_dir
    assert result_dir.is_dir()
    assert result_file == experiment_dir / "experiment.yaml"
    assert "Experiment will be set up here" in caplog.text
