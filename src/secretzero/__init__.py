"""SecretZero: Secrets orchestration, lifecycle, and bootstrap engine."""

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
