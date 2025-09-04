from twevals.decorators import eval
from twevals.schemas import EvalResult
from twevals.parametrize import parametrize

__all__ = ["eval", "EvalResult", "parametrize"]

# Resolve version from installed package metadata to avoid hard-coding.
try:  # Python 3.8+
    from importlib.metadata import version as _pkg_version, PackageNotFoundError
except Exception:  # pragma: no cover
    _pkg_version = None
    PackageNotFoundError = Exception

try:
    __version__ = _pkg_version("twevals") if _pkg_version else "0.0.0"
except PackageNotFoundError:
    __version__ = "0.0.0"
