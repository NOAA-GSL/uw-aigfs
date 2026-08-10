import logging

from pytest import fixture


@fixture
def logcap(caplog):
    caplog.handler.setFormatter(logging.Formatter("%(message)s"))
    caplog.set_level(logging.DEBUG)
    return caplog
