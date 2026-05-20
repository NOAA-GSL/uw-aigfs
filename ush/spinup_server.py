#! /usr/bin/env python
import sys
import logging

from ecflow import Client

from uwtools.api.config import get_yaml_config
from uwtools.api.logging import use_uwtools_logger

use_uwtools_logger()

server_config = get_yaml_config(sys.argv[1])
server_config.dereference()

ecf_config = server_config["ecf_vars"]
host = ecf_config.pop("ECF_LOGHOST")
port = ecf_config.pop("ECF_PORT")

try:
    ecf_client = Client(host, port)
    ecf_client.ping()
except RuntimeError:
    msg = f"Error trying to start the ecFlow server on {host}:{port}"
    logging.error(msg)
    raise

for var, val in ecf_config.items():
    ecf_client.alter("/", "add", "variable", var, str(val))

