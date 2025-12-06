from ezvals.decorators import eval
from ezvals.schemas import EvalResult, TraceData
from ezvals.parametrize import parametrize
from ezvals.context import EvalContext
from ezvals.runner import run_evals

__all__ = ["eval", "EvalResult", "TraceData", "parametrize", "EvalContext", "run_evals"]

# Resolve version from installed package metadata to avoid hard-coding.
try:  # Python 3.8+
    from importlib.metadata import version as _pkg_version, PackageNotFoundError
except Exception:  # pragma: no cover
    _pkg_version = None
    PackageNotFoundError = Exception

try:
    __version__ = _pkg_version("ezvals") if _pkg_version else "0.0.0"
except PackageNotFoundError:
    __version__ = "0.0.0"
