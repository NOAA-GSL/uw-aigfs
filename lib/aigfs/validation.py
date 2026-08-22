"""
Support for validating AIGFS configurations.
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from pprint import pformat
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

# Validation classes


class Partition(BaseModel):
    """
    Model for the `app.platform.partition:` block.
    """

    model_config = ConfigDict(extra="forbid")

    compute: str | None = None
    netaccess: str | None = None
    task: str | None = None

    @model_validator(mode="after")
    def at_least_one(self) -> "Partition":
        model = self.model_dump()
        if not any(model.values()):
            msg = "Specify at least one partition name (%s)" % ", ".join(model.keys())
            raise ValueError(msg)
        return self


class Scheduler(BaseModel):
    """
    Model for the `app.platform.scheduler:` block.
    """

    model_config = ConfigDict(extra="forbid")

    account: str | None = None
    type: Literal["pbs", "slurm"]


class Platform(BaseModel):
    """
    Model for the `app.platform:` block.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    partition: Partition | None = None
    scheduler: Scheduler


class App(BaseModel):
    """
    Model for the `app:` block.
    """

    model_config = ConfigDict(extra="forbid")

    cycle_freq: timedelta
    first_cycle: datetime
    home: Path
    last_cycle: datetime
    modeldir: Path
    platform: Platform
    rundir: Path

    @model_validator(mode="after")
    def first_and_last_cycle(self) -> "App":
        if self.last_cycle < self.first_cycle:
            msg = "last_cycle cannot precede first_cycle"
            raise ValueError(msg)
        return self


class Config(BaseModel):
    """
    Model for the overall AIGFS config.
    """

    model_config = ConfigDict(extra="forbid")

    app: App
    forecast: dict
    post: dict
    prep: dict
    timevars: dict  # PM REMOVE
    user: dict | None = None


# Public functions


def validate(config: dict[str, object]) -> Config:
    """
    Validate a config.
    """
    try:
        return Config.model_validate(config)
    except ValidationError as e:
        logging.error("Config validation failed:")
        lines = pformat(e.errors()).split("\n")
        for line in lines:
            logging.error(line)
        sys.exit(1)
