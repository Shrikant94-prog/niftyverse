"""Verified official ETF CSV columns; validate the whole bounded source."""

import csv
import hashlib
import io
import re
from datetime import datetime, timedelta

from niftyverse.etfs import EtfMetadata, EtfSnapshot
from niftyverse.ingestion import _source_date
from niftyverse.market_prices import MarketDataFailure, number, quantity
from niftyverse.temporal import Evidence, text, utc

HEADER = (
    "Symbol",
    "Underlying Asset",
    "SecurityName",
    "DateofListing",
    "MarketLot",
    "ISINNumber",
    "FaceValue",
    "ETF Underlying",
    "Underlying Key",
)


def decode_etf_catalogue(
    body: bytes,
    *,
    observed_at: datetime,
    source_id: str,
    max_bytes: int = 8 * 1024 * 1024,
    max_rows: int = 100_000,
) -> EtfSnapshot:
    utc(observed_at)
    text(source_id)
    if not body or len(body) > max_bytes or max_rows < 1:
        raise MarketDataFailure("source_limit")
    try:
        rows = csv.reader(io.StringIO(body.decode("utf-8-sig")), strict=True)
        if tuple(next(rows)) != HEADER:
            raise MarketDataFailure("unsupported_etf_catalogue")
        digest = hashlib.sha256(body).hexdigest()
        result: list[EtfMetadata] = []
        symbols: set[str] = set()
        isins: set[str] = set()
        for line, values in enumerate(rows, 2):
            if len(values) != len(HEADER) or len(result) >= max_rows:
                raise MarketDataFailure("invalid_etf_catalogue_row")
            raw = dict(zip(HEADER, (v.strip() for v in values), strict=True))
            symbol, isin = raw["Symbol"], raw["ISINNumber"]
            if not symbol or re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", isin) is None:
                raise MarketDataFailure("invalid_etf_identity")
            if symbol in symbols or isin in isins:
                raise MarketDataFailure("duplicate_etf_identity")
            symbols.add(symbol)
            isins.add(isin)
            listing_date = raw["DateofListing"]
            if re.fullmatch(r"[0-9]{2}-[A-Za-z]{3}-[0-9]{2}", listing_date):
                short_year = int(listing_date[-2:])
                listing_date = listing_date[:-2] + str(
                    (2000 if short_year <= 68 else 1900) + short_year
                )
            listed = _source_date(listing_date, True)
            if listed > observed_at.date():
                raise MarketDataFailure("future_listing_date")
            lot, face = quantity(raw["MarketLot"]), number(raw["FaceValue"])
            if lot == 0 or face == 0:
                raise MarketDataFailure("invalid_etf_unit_metadata")
            evidence = Evidence(
                observed_at.date(),
                observed_at.date() + timedelta(days=1),
                observed_at,
                source_id,
                f"etf_catalogue.csv:{line}",
            )

            def optional(value: str) -> str | None:
                return None if value in {"", "-", "--"} else value

            result.append(
                EtfMetadata(
                    symbol,
                    isin,
                    optional(raw["SecurityName"]),
                    optional(raw["Underlying Asset"]),
                    listed,
                    lot,
                    face,
                    optional(raw["ETF Underlying"]),
                    optional(raw["Underlying Key"]),
                    evidence,
                    digest,
                    tuple(raw.items()),
                )
            )
        if not result:
            raise MarketDataFailure("empty_etf_catalogue")
        return EtfSnapshot(observed_at, source_id, digest, tuple(result))
    except (UnicodeError, csv.Error, StopIteration, ValueError) as error:
        if isinstance(error, MarketDataFailure):
            raise
        raise MarketDataFailure("invalid_etf_catalogue") from error
