"""
Shared logic.
"""

from functools import cache
from pathlib import Path

HOMEDIR = Path(__file__).parent.parent.parent.resolve()
ETCDIR = HOMEDIR / "etc"
PLATFORMDIR = ETCDIR / "platform"


@cache
def platforms():
    return [x.with_suffix("").name for x in PLATFORMDIR.glob("*.yaml")]
