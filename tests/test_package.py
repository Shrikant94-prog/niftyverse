"""Package identity and optional import contracts, independent of adapters."""

import importlib.metadata
from pathlib import Path

from packaging.specifiers import SpecifierSet


def test_identity_and_python_boundary() -> None:
    import niftyverse

    metadata = importlib.metadata.metadata("niftyverse")
    assert metadata["Name"] == "niftyverse"
    assert niftyverse.__version__ == metadata["Version"]
    supported = SpecifierSet(metadata["Requires-Python"])
    assert "3.14.7" in supported
    assert "3.12.0" not in supported
    assert "3.15.0" not in supported
    assert Path(niftyverse.__file__).with_name("py.typed").is_file()


def test_filings_boundary_has_actionable_error(monkeypatch: object) -> None:
    import pytest

    from niftyverse.filings import FilingProcessorUnavailable, require_filing_processor

    def missing(name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", missing)  # type: ignore[attr-defined]
    with pytest.raises(FilingProcessorUnavailable, match="niftyverse\\[filings\\]"):
        require_filing_processor()
