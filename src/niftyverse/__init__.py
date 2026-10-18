"""Research-data library; importing it performs no acquisition or storage I/O."""

from niftyverse.builder import build_fixture, extract_fixture
from niftyverse.result import SliceResult

__version__ = "0.1.0"

__all__ = ["SliceResult", "__version__", "build_fixture", "extract_fixture"]
