"""Atomic source-report decoding; no disk extraction, canonical mapping or writes.

Registry signatures come from Phase 02 CM/FO captures at 2016-09-01 and
2026-10-16. Filenames and presumed transition dates do not choose the schema.
Exact strings (including missing tokens) and observed extra fields are retained.
"""

import csv
import hashlib
import io
import math
import re
import stat
import struct
import zipfile
import zlib
from dataclasses import dataclass
from datetime import date
from typing import Literal


class IngestionFailure(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class IngestionLimits:
    max_compressed: int = 128 * 1024 * 1024
    max_expanded: int = 512 * 1024 * 1024
    max_members: int = 16
    max_ratio: float = 100
    max_rows: int = 100000
    max_row_chars: int = 1024 * 1024
    max_output_chars: int = 16 * 1024 * 1024

    def __post_init__(self) -> None:
        if min(
            self.max_compressed,
            self.max_expanded,
            self.max_members,
            self.max_rows,
            self.max_row_chars,
            self.max_output_chars,
        ) <= 0 or (not math.isfinite(self.max_ratio) or self.max_ratio <= 0):
            raise ValueError("invalid ingestion limits")


CM_LEGACY = tuple(
    "SYMBOL SERIES OPEN HIGH LOW CLOSE LAST PREVCLOSE TOTTRDQTY "
    "TOTTRDVAL TIMESTAMP TOTALTRADES ISIN".split()
)
FO_LEGACY = tuple(
    "INSTRUMENT SYMBOL EXPIRY_DT STRIKE_PR OPTION_TYP OPEN HIGH LOW "
    "CLOSE SETTLE_PR CONTRACTS VAL_INLAKH OPEN_INT CHG_IN_OI TIMESTAMP".split()
)
UDIFF = tuple(
    "TradDt BizDt Sgmt Src FinInstrmTp FinInstrmId ISIN TckrSymb SctySrs "
    "XpryDt FininstrmActlXpryDt StrkPric OptnTp FinInstrmNm OpnPric HghPric "
    "LwPric ClsPric LastPric PrvsClsgPric UndrlygPric SttlmPric OpnIntrst "
    "ChngInOpnIntrst TtlTradgVol TtlTrfVal TtlNbOfTxsExctd SsnId NewBrdLotQty "
    "Rmks Rsvd1 Rsvd2 Rsvd3 Rsvd4".split()
)
_NUMERIC = frozenset(
    "OPEN HIGH LOW CLOSE LAST PREVCLOSE TOTTRDQTY TOTTRDVAL TOTALTRADES "
    "STRIKE_PR SETTLE_PR CONTRACTS VAL_INLAKH OPEN_INT CHG_IN_OI OpnPric HghPric "
    "LwPric ClsPric LastPric PrvsClsgPric UndrlygPric SttlmPric StrkPric OpnIntrst "
    "ChngInOpnIntrst TtlTradgVol TtlTrfVal TtlNbOfTxsExctd NewBrdLotQty".split()
)
_MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()


@dataclass(frozen=True)
class SourceRow:
    line: int
    values: tuple[str, ...]


@dataclass(frozen=True)
class SourceReport:
    source: str
    member: str
    sha256: str
    schema_sha256: str
    generation: str
    headers: tuple[str, ...]
    extra_fields: tuple[str, ...]
    rows: tuple[SourceRow, ...]
    complete: Literal[False] = False


def _safe_member(info: zipfile.ZipInfo) -> None:
    name = info.orig_filename
    components = name.split("/")
    if (
        not name
        or "\\" in name
        or ":" in name
        or "\x00" in name
        or any(part in {"", ".", ".."} for part in components)
        or stat.S_ISLNK(info.external_attr >> 16)
        or info.flag_bits & 1
    ):
        raise IngestionFailure("unsafe_member")
    if not name.lower().endswith(".csv") or info.compress_type not in {
        zipfile.ZIP_STORED,
        zipfile.ZIP_DEFLATED,
    }:
        raise IngestionFailure("unexpected_member")


def _source_date(value: str, legacy: bool) -> date:
    try:
        if legacy:
            day, month, year = value.upper().split("-")
            if len(year) != 4 or len(day) != 2 or month not in _MONTHS:
                raise ValueError
            return date(int(year), _MONTHS.index(month) + 1, int(day))
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError
        return date.fromisoformat(value)
    except ValueError:
        raise IngestionFailure("invalid_date") from None


def _parse(
    body: bytes, dataset: str, session: date, limits: IngestionLimits
) -> tuple[str, tuple[str, ...], tuple[str, ...], tuple[SourceRow, ...]]:
    if body.lstrip().startswith(b"<"):
        raise IngestionFailure("source_blocked")
    if b"\x00" in body:
        raise IngestionFailure("invalid_csv")
    text = body.decode("utf-8-sig", errors="strict")
    lines = text.splitlines(keepends=True)
    if any(len(line) > limits.max_row_chars for line in lines):
        raise IngestionFailure("row_size_limit")
    reader = csv.reader(lines, dialect="excel", strict=True)
    try:
        raw_headers = next(reader)
    except StopIteration:
        raise IngestionFailure("empty_report") from None
    if not raw_headers or len(raw_headers) > 128:
        raise IngestionFailure("schema_drift")
    trailing = raw_headers[-1] == ""
    headers = tuple(raw_headers[:-1] if trailing else raw_headers)
    if len(set(headers)) != len(headers) or "" in headers:
        raise IngestionFailure("duplicate_header")
    known = CM_LEGACY if dataset == "cm" else FO_LEGACY
    if set(known) <= set(headers):
        generation, required, legacy = f"{dataset}_legacy", known, True
    elif set(UDIFF) <= set(headers):
        generation, required, legacy = f"{dataset}_udiff", UDIFF, False
    else:
        raise IngestionFailure("schema_drift")
    extra = tuple(h for h in headers if h not in required)
    indices = {h: i for i, h in enumerate(headers)}
    rows: list[SourceRow] = []
    keys: set[tuple[str, ...]] = set()
    total_chars = 0
    for values in reader:
        if len(rows) >= limits.max_rows:
            raise IngestionFailure("row_limit")
        if len(values) != len(raw_headers) or (trailing and values[-1] != ""):
            raise IngestionFailure("row_width")
        if trailing:
            values.pop()
        total_chars += sum(map(len, values))
        if total_chars > limits.max_output_chars or sum(map(len, values)) > limits.max_row_chars:
            raise IngestionFailure("output_limit")
        for header in _NUMERIC & indices.keys():
            value = values[indices[header]]
            if value in {"", "-"}:
                continue  # preserve declared empty and dash tokens, never infer zero
            if not re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value):
                raise IngestionFailure("invalid_number")
            if len(value.replace("-", "").replace(".", "")) > 38:
                raise IngestionFailure("numeric_overflow")
        timestamp = values[indices["TIMESTAMP" if legacy else "TradDt"]]
        if _source_date(timestamp, legacy) != session:
            raise IngestionFailure("session_mismatch")
        if not legacy:
            if values[indices["Sgmt"]] != dataset.upper() or values[indices["Src"]] != "NSE":
                raise IngestionFailure("source_mismatch")
            if _source_date(values[indices["BizDt"]], False) != session:
                raise IngestionFailure("session_mismatch")
        key_fields = (
            (
                ("SYMBOL", "SERIES")
                if dataset == "cm"
                else ("INSTRUMENT", "SYMBOL", "EXPIRY_DT", "STRIKE_PR", "OPTION_TYP")
            )
            if legacy
            else (("FinInstrmId", "SsnId"))
        )
        key = tuple(values[indices[h]] for h in key_fields)
        if any(not value for value in key):
            raise IngestionFailure("missing_identity")
        if key in keys:
            raise IngestionFailure("duplicate_key")
        keys.add(key)
        rows.append(SourceRow(reader.line_num, tuple(values)))
    if not rows:
        raise IngestionFailure("empty_report")
    return generation, headers, extra, tuple(rows)


def _check_directory(body: bytes, limits: IngestionLimits) -> None:
    # Check the central directory before ZipFile allocates ZipInfo objects.
    # Observed reports are ordinary single-disk ZIPs; ZIP64 is unsupported.
    end = body.rfind(b"PK\x05\x06", max(0, len(body) - 65557))
    if end < 0 or end + 22 > len(body):
        raise IngestionFailure("invalid_zip")
    disk, start_disk, entries_disk, entries, size, offset, comment = struct.unpack_from(
        "<4H2IH", body, end + 4
    )
    if (
        disk
        or start_disk
        or entries_disk != entries
        or entries == 65535
        or end + 22 + comment != len(body)
        or offset + size != end
    ):
        raise IngestionFailure("invalid_zip")
    if entries > limits.max_members:
        raise IngestionFailure("member_limit")
    cursor, count = offset, 0
    while cursor < end:
        if cursor + 46 > end or body[cursor : cursor + 4] != b"PK\x01\x02":
            raise IngestionFailure("invalid_zip")
        name_size, extra_size, comment_size = struct.unpack_from("<3H", body, cursor + 28)
        if name_size > 1024 or extra_size > 4096 or comment_size > 1024:
            raise IngestionFailure("member_metadata_limit")
        cursor += 46 + name_size + extra_size + comment_size
        count += 1
        if count > limits.max_members:
            raise IngestionFailure("member_limit")
    if cursor != end or count != entries:
        raise IngestionFailure("invalid_zip")


def read_report(
    body: bytes,
    *,
    dataset: Literal["cm", "fo"],
    session: date,
    source: str = "",
    limits: IngestionLimits | None = None,
) -> SourceReport:
    """Validate a whole observed single-member report or return no report.

    A source report is not canonical market coverage. Dataset adapters still own
    identity/unit semantics, calendar/scope reconciliation and publication.
    Bounds cover input/expanded buffers, output characters/rows and CSV fields;
    this synchronous pure decoder must be called outside a notebook event loop.
    """
    limits = limits or IngestionLimits()
    if dataset not in {"cm", "fo"}:
        raise ValueError("unsupported report dataset")
    if len(body) > limits.max_compressed:
        raise IngestionFailure("compressed_limit")
    if body.lstrip().startswith(b"<"):
        raise IngestionFailure("source_blocked")
    _check_directory(body, limits)
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            infos = archive.infolist()
            if len(infos) > limits.max_members:
                raise IngestionFailure("member_limit")
            names: set[str] = set()
            expanded = 0
            for info in infos:
                _safe_member(info)
                if info.filename.casefold() in names:
                    raise IngestionFailure("duplicate_member")
                names.add(info.filename.casefold())
                expanded += info.file_size
                if expanded > limits.max_expanded:
                    raise IngestionFailure("expanded_limit")
                if info.file_size > max(1, info.compress_size) * limits.max_ratio:
                    raise IngestionFailure("ratio_limit")
            if len(infos) != 1:
                raise IngestionFailure("unexpected_member_count")
            info = infos[0]
            with archive.open(info) as member:
                content = member.read(limits.max_expanded + 1)
                if len(content) > limits.max_expanded:
                    raise IngestionFailure("expanded_limit")
            generation, headers, extra, rows = _parse(content, dataset, session, limits)
            return SourceReport(
                source,
                info.filename,
                hashlib.sha256(body).hexdigest(),
                hashlib.sha256("\0".join(headers).encode()).hexdigest(),
                generation,
                headers,
                extra,
                rows,
            )
    except zipfile.BadZipFile, EOFError, zlib.error, RuntimeError:
        raise IngestionFailure("invalid_zip") from None
    except csv.Error, UnicodeDecodeError:
        raise IngestionFailure("invalid_csv") from None
