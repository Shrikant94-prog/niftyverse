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
    "market_state_observations": schema(
        ("observation_id", TEXT, False),
        ("listing_id", TEXT, False),
        ("segment", TEXT, False),
        ("state_kind", TEXT, False),
        ("state", TEXT, False),
        ("value", TEXT, True),
        ("observed_on", DAY, False),
        ("effective_from", DAY, True),
        ("effective_to", DAY, True),
        ("known_at", INSTANT, False),
        ("publication_time", INSTANT, True),
        ("publication_precision", TEXT, False),
        ("source_timezone", TEXT, False),
        ("lower", MONEY, True),
        ("upper", MONEY, True),
        ("basis", TEXT, False),
        ("source_id", TEXT, False),
        ("locator", TEXT, False),
        ("publication_date", DAY, True),
    ),
    "equity_daily": PRICE,
    "etf_daily": PRICE,
    "security_daily_details": schema(
        ("listing_id", TEXT, False),
        ("series", TEXT, False),
        ("session_date", DAY, False),
        ("quantity_unit", TEXT, False),
        ("trades", pa.int64(), True),
        ("settlement_price", MONEY, True),
        ("last_price", MONEY, True),
        ("previous_close", MONEY, True),
        ("delivered_quantity", pa.int64(), True),
        ("comparable_quantity", pa.int64(), True),
        ("delivery_fraction", pa.decimal128(38, 12), True),
        ("published_delivery_percent", MONEY, True),
        ("delivery_reason", TEXT, True),
        ("source_turnover", MONEY, True),
        ("source_turnover_unit", TEXT, True),
        ("quantity_definition", TEXT, False),
        ("price_basis", TEXT, False),
        ("representation", TEXT, False),
        ("raw_sha256", TEXT, False),
        ("locator", TEXT, False),
    ),
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
    "market_state_observations": ("listing_id", "segment", "state_kind", "observation_id"),
    "equity_daily": ("listing_id", "series", "session_date"),
    "etf_daily": ("listing_id", "series", "session_date"),
    "security_daily_details": ("listing_id", "series", "session_date"),
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
