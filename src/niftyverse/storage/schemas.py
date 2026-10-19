"""Versioned typed publication tables; no connection or filesystem side effects."""

import pyarrow as pa

TEXT = pa.string()
DAY = pa.date32()
MONEY = pa.decimal128(38, 8)
INSTANT = pa.timestamp("us", tz="UTC")
DIMENSION = pa.struct(
    [
        ("axis", TEXT),
        ("member", TEXT),
        ("typed_xml", TEXT),
        ("container", TEXT),
    ]
)


def schema(*fields: tuple[str, pa.DataType, bool]) -> pa.Schema:
    return pa.schema([pa.field(name, kind, nullable=nullable) for name, kind, nullable in fields])


PRICE = schema(
    ("listing_id", TEXT, False),
    ("series", TEXT, False),
    ("session_date", DAY, False),
    ("open", MONEY, True),
    ("high", MONEY, True),
    ("low", MONEY, True),
    ("close", MONEY, True),
    ("quantity", pa.int64(), True),
    ("quantity_unit", TEXT, False),
    ("turnover", MONEY, True),
    ("currency", TEXT, False),
    ("locator", TEXT, False),
    ("missing_reason", TEXT, True),
)
SCHEMAS = {
    "equity_daily": PRICE,
    "etf_daily": PRICE,
    "etf_metadata": schema(
        ("listing_id", TEXT, False),
        ("valid_from", DAY, False),
        ("valid_to", DAY, True),
        ("scheme_name", TEXT, True),
        ("classification", TEXT, True),
        ("locator", TEXT, False),
    ),
    "filing_documents": schema(
        ("document_id", TEXT, False),
        ("filing_id", TEXT, False),
        ("raw_sha256", TEXT, False),
        ("format", TEXT, False),
        ("parser_version", TEXT, False),
        ("taxonomy_version", TEXT, True),
        ("taxonomy_sha256", TEXT, True),
        ("publication_time", INSTANT, True),
        ("publication_precision", TEXT, False),
    ),
    "filing_source_assertions": schema(
        ("assertion_id", TEXT, False),
        ("document_id", TEXT, False),
        ("concept", TEXT, False),
        ("context_id", TEXT, False),
        ("entity", TEXT, False),
        ("entity_scheme", TEXT, False),
        ("period_start", DAY, True),
        ("period_end", DAY, True),
        ("instant", DAY, True),
        ("dimensions", pa.list_(DIMENSION), False),
        ("context_xml", TEXT, False),
        ("unit_numerator", pa.list_(TEXT), False),
        ("unit_denominator", pa.list_(TEXT), False),
        ("value", TEXT, True),
        ("raw_value", TEXT, False),
        ("nil", pa.bool_(), False),
        ("decimals", TEXT, True),
        ("precision", TEXT, True),
        ("locator", TEXT, False),
        ("mapping_status", TEXT, False),
    ),
    "financial_facts": schema(
        ("assertion_id", TEXT, False),
        ("entity_id", TEXT, False),
        ("concept", TEXT, False),
        ("period_start", DAY, True),
        ("period_end", DAY, False),
        ("period_kind", TEXT, False),
        ("basis", TEXT, False),
        ("scope", TEXT, False),
        ("unit", TEXT, False),
        ("dimensions", pa.list_(DIMENSION), False),
        ("value", MONEY, True),
        ("additivity", TEXT, False),
        ("derivation", TEXT, False),
    ),
}

KEYS = {
    "equity_daily": ("listing_id", "series", "session_date"),
    "etf_daily": ("listing_id", "series", "session_date"),
    "etf_metadata": ("listing_id", "valid_from"),
    "filing_documents": ("document_id",),
    "filing_source_assertions": ("assertion_id",),
    "financial_facts": (
        "assertion_id",
        "concept",
        "period_start",
        "period_end",
        "period_kind",
        "basis",
        "scope",
        "unit",
        "dimensions",
    ),
}

ANALYTICAL_KEY = (
    "entity_id",
    "concept",
    "period_start",
    "period_end",
    "period_kind",
    "basis",
    "scope",
    "unit",
    "dimensions",
)
