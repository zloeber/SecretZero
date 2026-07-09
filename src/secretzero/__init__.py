"""SecretZero: Secrets orchestration, lifecycle, and bootstrap engine."""

# Guard: a caller-injected PYTHONPATH (e.g. an embedding app) can shadow our
# bundled deps and crash import (ModuleNotFoundError pydantic_core._pydantic_core).
# Force our own site-packages ahead of any env-injected path.
import sys as _sys
import sysconfig as _sc

_own = _sc.get_paths()["purelib"]
if _own in _sys.path:
    _sys.path.remove(_own)
_sys.path.insert(0, _own)
del _sys, _sc, _own

import os
from os import path

here = path.abspath(path.dirname(__file__))

SCRIPT_PATH = os.path.abspath(os.path.split(__file__)[0])
DATA_PATH = os.getenv("SECRETZERO_DATA", os.path.join(SCRIPT_PATH, "data"))

try:
    from ._version import version as __version__
except ImportError:
    from setuptools_scm import get_version

    __version__ = get_version(root="../../", relative_to=__file__)
