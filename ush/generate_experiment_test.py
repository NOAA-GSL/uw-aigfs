from unittest.mock import Mock, patch

from . import generate_experiment


def test_ush_generate_experiment_generate_experiment_files():
    pass


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
    pass


def test_ush_generate_experiment_prepare_configs():
    pass


def test_ush_generate_experiment_set_up_experiment_directory():
    pass
