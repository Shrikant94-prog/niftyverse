"""An eager typed result with an immutable display snapshot."""

from dataclasses import dataclass, field

import polars as pl

from niftyverse.core import BuildEvent, FixtureRow


@dataclass(frozen=True, slots=True, repr=False)
class SliceResult:
    """Owned fixture result; data access is explicit and returns a frame clone."""

    _frame: pl.DataFrame = field(repr=False)
    preview_rows: tuple[FixtureRow, ...]
    committed_rows: int
    raw_sha256: str
    mode: str
    event: BuildEvent = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event", BuildEvent(self.committed_rows))

    def to_polars(self, *, max_rows: int = 100_000) -> pl.DataFrame:
        """Return an explicit eager result copy; display never calls this."""
        if self._frame.height > max_rows:
            raise ValueError(
                f"result has {self._frame.height} rows, exceeding max_rows={max_rows}"
            )
        return self._frame.clone()

    def __repr__(self) -> str:
        from niftyverse.display import render_text

        return render_text(self)

    def _repr_html_(self) -> str:
        from niftyverse.display import render_html

        return render_html(self)

    def _repr_mimebundle_(
        self,
        include: set[str] | None = None,
        exclude: set[str] | None = None,
    ) -> dict[str, str]:
        """IPython protocol with no IPython dependency or active kernel."""
        values = {"text/plain": repr(self), "text/html": self._repr_html_()}
        return {
            key: value
            for key, value in values.items()
            if (include is None or key in include) and (exclude is None or key not in exclude)
        }
