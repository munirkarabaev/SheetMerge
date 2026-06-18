"""Parse uploaded CSV files into metadata used by AI suggestions."""

import csv
from dataclasses import dataclass
from io import StringIO

from django.utils import timezone

from core.models import MergesetFile


SNIFFED_DELIMITERS = ",;\t|"
MAX_SAMPLE_ROWS = 10


class CsvParseError(ValueError):
    """Raised when an uploaded file cannot produce a reliable CSV structure."""


@dataclass(frozen=True)
class CsvParseResult:
    """Structural metadata extracted from a CSV file."""

    headers: list[str]
    sample_rows: list[list[str]]
    delimiter: str
    row_count: int


def read_csv_metadata(source_file: MergesetFile) -> CsvParseResult:
    """Read and validate headers, delimiter, and data-row count."""

    source_file.file.open("rb")
    try:
        raw_content = source_file.file.read()
    finally:
        source_file.file.close()

    try:
        content = raw_content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CsvParseError("The CSV file must use UTF-8 encoding.") from error

    if not content.strip():
        raise CsvParseError("The CSV file is empty.")

    try:
        dialect = csv.Sniffer().sniff(
            content[:8192],
            delimiters=SNIFFED_DELIMITERS,
        )
    except csv.Error:
        dialect = csv.excel

    try:
        reader = csv.reader(StringIO(content, newline=""), dialect, strict=True)
        headers = [header.strip() for header in next(reader)]
        _validate_headers(headers)

        row_count = 0
        sample_rows = []
        for line_number, row in enumerate(reader, start=2):
            if not row or not any(value.strip() for value in row):
                continue
            if len(row) != len(headers):
                raise CsvParseError(
                    f"Row {line_number} has {len(row)} columns; "
                    f"expected {len(headers)}."
                )
            row_count += 1
            if len(sample_rows) < MAX_SAMPLE_ROWS:
                sample_rows.append([value.strip() for value in row])
    except StopIteration as error:
        raise CsvParseError("The CSV file does not contain a header row.") from error
    except csv.Error as error:
        raise CsvParseError(f"The CSV structure is invalid: {error}.") from error

    return CsvParseResult(
        headers=headers,
        sample_rows=sample_rows,
        delimiter=dialect.delimiter,
        row_count=row_count,
    )


def parse_mergeset_file(source_file: MergesetFile) -> bool:
    """Parse one stored CSV and persist either metadata or a failure reason."""

    try:
        result = read_csv_metadata(source_file)
    except CsvParseError as error:
        source_file.parse_status = MergesetFile.ParseStatus.FAILED
        source_file.headers = []
        source_file.sample_rows = []
        source_file.delimiter = ""
        source_file.row_count = None
        source_file.parse_error = str(error)
        parsed = False
    else:
        source_file.parse_status = MergesetFile.ParseStatus.PARSED
        source_file.headers = result.headers
        source_file.sample_rows = result.sample_rows
        source_file.delimiter = result.delimiter
        source_file.row_count = result.row_count
        source_file.parse_error = ""
        parsed = True

    source_file.parsed_at = timezone.now()
    source_file.save(
        update_fields=[
            "parse_status",
            "headers",
            "sample_rows",
            "delimiter",
            "row_count",
            "parse_error",
            "parsed_at",
        ]
    )
    return parsed


def _validate_headers(headers: list[str]) -> None:
    """Reject missing, blank, or duplicate CSV column names."""

    if not headers:
        raise CsvParseError("The CSV file does not contain a header row.")
    if any(not header for header in headers):
        raise CsvParseError("CSV column names cannot be blank.")

    normalized_headers = [header.casefold() for header in headers]
    if len(normalized_headers) != len(set(normalized_headers)):
        raise CsvParseError("CSV column names must be unique.")
