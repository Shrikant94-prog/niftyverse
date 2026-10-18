"""Optional filing processor boundary, pending source-backed selection."""


class FilingProcessorUnavailable(RuntimeError):
    """A supported, pinned filing processor has not been selected."""


def require_filing_processor() -> None:
    """Fail explicitly until Phase 02 evidence selects a bounded processor."""
    raise FilingProcessorUnavailable(
        "No filing processor selected. Phase 02 source, taxonomy and resource-limit evidence "
        "must select a Python 3.14 processor before structured decoding is available. "
        "The filings extra currently installs no parser."
    )
