"""Research-data library; importing it performs no acquisition or storage I/O."""

from niftyverse.builder import build, build_fixture, extract, extract_fixture
from niftyverse.planning import (
    Capability,
    DataPlan,
    DatasetRequest,
    ResearchDependency,
    compile_plan,
    research_preflight,
)
from niftyverse.result import SliceResult

__version__ = "0.1.0"

__all__ = [
    "Capability",
    "DataPlan",
    "DatasetRequest",
    "ResearchDependency",
    "SliceResult",
    "__version__",
    "build",
    "build_fixture",
    "compile_plan",
    "extract",
    "extract_fixture",
    "research_preflight",
]
