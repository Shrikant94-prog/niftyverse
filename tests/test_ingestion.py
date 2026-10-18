"""Owned adversarial inputs, independent of production decoder output."""

import io
import zipfile
from datetime import date
from pathlib import Path

import pytest

from niftyverse.ingestion import IngestionFailure, IngestionLimits, read_report

CM = (
    b"SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,"
    b"TIMESTAMP,TOTALTRADES,ISIN,\n"
)
ROW = b"ABC,EQ,1.00,2.00,1,1.50,1.50,1,10,15.00,01-SEP-2016,3,INE000000000,\n"


def archive(*members: tuple[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in members:
            z.writestr(name, data)
    return buffer.getvalue()


def test_source_strings_and_extra_fields() -> None:
    report = read_report(
        archive(("any-date.csv", CM + ROW)), dataset="cm", session=date(2016, 9, 1), source="owned"
    )
    assert report.generation == "cm_legacy"
    assert report.rows[0].values[report.headers.index("CLOSE")] == "1.50"
    assert report.rows[0].line == 2 and report.member == "any-date.csv"
    assert report.source == "owned" and report.complete is False
    extra = CM.rstrip(b"\n") + b"Note\n" + ROW.rstrip(b"\n") + b"source text\n"
    report = read_report(archive(("test.csv", extra)), dataset="cm", session=date(2016, 9, 1))
    assert report.extra_fields == ("Note",)
    assert report.rows[0].values[-1] == "source text"


@pytest.mark.parametrize(
    "name",
    [
        "../escape.csv",
        "/absolute.csv",
        "C:/escape.csv",
        "safe/../../escape.csv",
        "a\\..\\escape.csv",
        "nested.zip",
    ],
)
def test_unsafe_paths_and_types_leave_files_unchanged(tmp_path: Path, name: str) -> None:
    sentinel = tmp_path / "sentinel"
    sentinel.write_text("unchanged")
    with pytest.raises(IngestionFailure) as caught:
        read_report(archive((name, CM + ROW)), dataset="cm", session=date(2016, 9, 1))
    assert caught.value.code in {"unsafe_member", "unexpected_member"}
    assert list(tmp_path.iterdir()) == [sentinel] and sentinel.read_text() == "unchanged"


@pytest.mark.parametrize(
    "body,code",
    [
        (CM + ROW + b"ABC,EQ\n", "row_width"),
        (CM + ROW + ROW, "duplicate_key"),
        (CM.replace(b"CLOSE,", b"GONE,", 1) + ROW, "schema_drift"),
        (CM.replace(b"OPEN,", b"CLOSE,", 1) + ROW, "duplicate_header"),
        (CM + ROW.replace(b"1.50", b"NaN"), "invalid_number"),
        (CM + ROW.replace(b"01-SEP-2016", b"02-SEP-2016"), "session_mismatch"),
        (CM + b'"unterminated', "invalid_csv"),
        (b"<html>Access Denied</html>", "source_blocked"),
        (CM + ROW.replace(b"1.50", b"9" * 50), "numeric_overflow"),
        (CM + ROW.replace(b"ABC", b"A\x00B"), "invalid_csv"),
    ],
)
def test_atomic_csv_rejection(body: bytes, code: str) -> None:
    with pytest.raises(IngestionFailure) as caught:
        read_report(archive(("report.csv", body)), dataset="cm", session=date(2016, 9, 1))
    assert caught.value.code == code


def test_archive_limits_truncation_and_duplicates() -> None:
    body = archive(("report.csv", CM + ROW))
    for bad, limits, code in [
        (body, IngestionLimits(max_compressed=10), "compressed_limit"),
        (body, IngestionLimits(max_expanded=20), "expanded_limit"),
        (body, IngestionLimits(max_rows=1), "row_limit"),
        (archive(("report.csv", CM + ROW * 2)), IngestionLimits(max_rows=1), "row_limit"),
        (archive(("report.csv", b"A" * 100000)), IngestionLimits(max_ratio=2), "ratio_limit"),
        (body[:-20], IngestionLimits(), "invalid_zip"),
    ]:
        if code == "row_limit" and bad == body:
            continue  # one row is exactly the valid boundary
        with pytest.raises(IngestionFailure) as caught:
            read_report(bad, dataset="cm", session=date(2016, 9, 1), limits=limits)
        assert caught.value.code == code
    with pytest.warns(UserWarning, match="Duplicate"):
        duplicate = archive(("a.csv", CM + ROW), ("a.csv", CM + ROW))
    with pytest.raises(IngestionFailure, match="duplicate_member"):
        read_report(duplicate, dataset="cm", session=date(2016, 9, 1))


@pytest.mark.parametrize(
    "dataset,generation,field,expected",
    [
        ("cm", "legacy", "CLOSE", "1029.2"),
        ("fo", "legacy", "CLOSE", "8808.35"),
        ("cm", "udiff", "ClsPric", "1211.20"),
        ("fo", "udiff", "StrkPric", "375.00"),
    ],
)
def test_real_header_and_row_excerpt(
    dataset: str, generation: str, field: str, expected: str
) -> None:
    body = (
        Path(__file__).parent / "fixtures/reports" / f"{dataset}-{generation}.csv"
    ).read_bytes()
    session = date(2016, 9, 1) if generation == "legacy" else date(2026, 10, 16)
    report = read_report(
        archive(("unrelated-name.csv", body)),
        dataset=dataset,  # type: ignore[arg-type]
        session=session,
    )
    assert report.generation == f"{dataset}_{generation}"
    assert report.rows[0].values[report.headers.index(field)] == expected


def test_symlink_encryption_crc_and_member_count() -> None:
    import struct

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        info = zipfile.ZipInfo("link.csv")
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        z.writestr(info, CM + ROW)
    with pytest.raises(IngestionFailure, match="unsafe_member"):
        read_report(buffer.getvalue(), dataset="cm", session=date(2016, 9, 1))
    body = bytearray(archive(("report.csv", CM + ROW)))
    central = body.index(b"PK\x01\x02")
    struct.pack_into("<H", body, 6, 1)
    struct.pack_into("<H", body, central + 8, 1)
    with pytest.raises(IngestionFailure, match="unsafe_member"):
        read_report(bytes(body), dataset="cm", session=date(2016, 9, 1))
    body = bytearray(archive(("report.csv", CM + ROW)))
    central = body.index(b"PK\x01\x02")
    struct.pack_into("<I", body, central + 16, 123)
    with pytest.raises(IngestionFailure, match="invalid_zip"):
        read_report(bytes(body), dataset="cm", session=date(2016, 9, 1))
    with pytest.raises(IngestionFailure, match="member_limit"):
        read_report(
            archive(*[(f"a{i}.csv", b"x") for i in range(17)]),
            dataset="cm",
            session=date(2016, 9, 1),
        )


def test_expansion_rejected_before_allocation() -> None:
    import tracemalloc

    body = archive(("report.csv", b"x" * 2_000_000))
    tracemalloc.start()
    try:
        with pytest.raises(IngestionFailure, match="expanded_limit"):
            read_report(
                body,
                dataset="cm",
                session=date(2016, 9, 1),
                limits=IngestionLimits(max_expanded=1000),
            )
        _, peak = tracemalloc.get_traced_memory()
        assert peak < 1_000_000
    finally:
        tracemalloc.stop()


def test_ambiguous_expiry_rejects_entire_derivative_report() -> None:
    body = (Path(__file__).parent / "fixtures/reports/fo-legacy.csv").read_bytes()
    body = body.replace(b"29-Sep-2016", b"09/10/2016")
    with pytest.raises(IngestionFailure, match="invalid_date"):
        read_report(archive(("fo.csv", body)), dataset="fo", session=date(2016, 9, 1))


def test_csv_control_text_is_preserved_without_creating_records() -> None:
    body = CM.rstrip(b"\n") + b"Note\n" + ROW.rstrip(b"\n") + b"source\vtext\n"
    report = read_report(archive(("cm.csv", body)), dataset="cm", session=date(2016, 9, 1))
    assert len(report.rows) == 1 and report.rows[0].values[-1] == "source\vtext"
