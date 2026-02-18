"""SecretZero: Secrets orchestration, lifecycle, and bootstrap engine."""
import os
from os import path

here = path.abspath(path.dirname(__file__))

try:
    from ._version import version as __version__
except ImportError:
    from setuptools_scm import get_version

    __version__ = get_version(root="../../", relative_to=__file__)