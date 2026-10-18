"""An eager typed result with an immutable display snapshot."""

from dataclasses import dataclass, field

import polars as pl

from niftyverse.core import FixtureRow


@dataclass(frozen=True, slots=True, repr=False)
class SliceResult:
    """Owned fixture result; data access is explicit and returns a frame clone."""

    _frame: pl.DataFrame = field(repr=False)
    preview_rows: tuple[FixtureRow, ...]
    committed_rows: int
    raw_sha256: str
    mode: str

    def to_polars(self) -> pl.DataFrame:
        """Return an explicit eager result copy; display never calls this."""
        return self._frame.clone()
