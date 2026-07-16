from __future__ import annotations

from datetime import datetime, timedelta  # noqa: TC003
from pathlib import Path  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt, model_validator
from uwtools.api.driver import yaml_keys_to_classes


class Config(BaseModel):
    user: User

class User(BaseModel):
    cycle_freq: timedelta
    driver_validation_blocks: list[str] = Field(default_factory=list)
    experiment_dir: Path
    first_cycle: datetime
    last_cycle: datetime
    platform: str

    @model_validator(mode="after")
    def first_and_last_cycle(self):
        if self.last_cycle < self.first_cycle:
            msg = "last_cycle cannot precede first_cycle"
            raise ValueError(msg)
        return self


def validate(config: dict) -> Config:
    return Config(**config)
