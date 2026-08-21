from pathlib import Path
from unittest.mock import Mock, patch

from pytest import raises

from aigfs import setup


def test_setup_compose_configs():
    platform = "jet"
    user_config_files = [Path("/path/to/a.yaml")]
    with patch.object(setup, "compose_to_dict") as compose_to_dict:
        compose_to_dict.return_value = {"app": {"rundir": "/some/path"}}
        result = setup.compose_configs(platform, user_config_files)
    assert result == {"app": {"rundir": "/some/path"}}
    compose_to_dict.assert_called_once_with(
        [
            setup._ETC / "base.yaml",
            setup._ETC / "workflow" / "rocoto" / "base.yaml",
            setup._PLATFORM / "jet.yaml",
            Path("/path/to/a.yaml"),
        ],
        realize=True,
    )


def test_setup_main():
    with (
        patch.object(setup, "compose_configs") as compose_configs,
        patch.object(setup, "parse_args") as parse_args,
        patch.object(setup, "set_up_rundir") as set_up_rundir,
        patch.object(setup, "validate") as validate,
    ):
        args = Mock()
        args.platform = "jet"
        args.user_config_files = [Path("/path/to/a.yaml")]
        parse_args.return_value = args
        compose_configs.return_value = {"app": {"key": "val"}}
        setup.main()
        parse_args.assert_called_once_with()
        compose_configs.assert_called_once_with("jet", [Path("/path/to/a.yaml")])
        validate.assert_called_once_with({"app": {"key": "val"}})
        set_up_rundir.assert_called_once_with("jet", {"app": {"key": "val"}})


def test_setup_parse_args():
    with patch.object(setup, "_PLATFORM") as mock_platform:
        mock_platform.glob.return_value = [Path("jet.yaml")]
        with patch("sys.argv", ["prog", "jet", "/path/to/a.yaml", "/path/to/b.yaml"]):
            result = setup.parse_args()
    assert result.platform == "jet"
    assert result.user_config_files == [Path("/path/to/a.yaml"), Path("/path/to/b.yaml")]


def test_setup_set_up_rundir(logcap, tmp_path):
    rundir = tmp_path / "rundir"
    config: dict = {"app": {"rundir": str(rundir)}}
    with (
        patch.object(setup, "YAMLConfig") as YAMLConfig,
        patch.object(setup, "rocoto") as rocoto,
    ):
        rocoto.realize.return_value = True
        setup.set_up_rundir("jet", config)
    assert rundir.is_dir()
    assert YAMLConfig.call_args_list[0].args[0] == config
    extended = {**config, "platform": "jet"}
    assert YAMLConfig.call_args_list[1].args[0] == extended
    YAMLConfig.return_value.dump.assert_called_once_with(rundir / "aigfs.yaml")
    rocoto.realize.assert_called_once_with(YAMLConfig(extended), rundir / "rocoto.xml")
    assert f"AIGFS will be set up here: {rundir}" in logcap.text


def test_setup_set_up_rundir_invalid_xml(logcap, tmp_path):
    rundir = tmp_path / "rundir"
    config: dict = {"app": {"rundir": str(rundir)}}
    with (
        patch.object(setup, "YAMLConfig"),
        patch.object(setup, "rocoto") as rocoto,
    ):
        rocoto.realize.return_value = False
        with raises(SystemExit):
            setup.set_up_rundir("jet", config)
    assert "Invalid Rocoto XML" in logcap.text
