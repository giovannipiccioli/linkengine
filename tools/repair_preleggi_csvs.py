"""Repair legacy preleggi references that were mapped to the codice civile.

The utility streams pipe-delimited extraction CSVs so it can handle multi-gigabyte
files without loading them into memory.  It is a dry run unless ``--apply`` is
passed.  Applied rewrites are validated row by row before the original file is
atomically replaced.

From the ``src/utils/linkengine`` directory, the default output trees can be
audited and repaired with::

    python -m tools.repair_preleggi_csvs
    python -m tools.repair_preleggi_csvs --apply
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence


SRC_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATHS = (
    SRC_ROOT / "analysis_bdgt" / "legal_refs_extraction" / "output",
    SRC_ROOT / "analysis_interpelli" / "legal_refs_extraction" / "output",
)

# Match only the NIR identifier for R.D. 262/1942, annex 2.  The optional full
# date supports both linkengine's catalog form and its normalized output form.
OLD_URN_RE = re.compile(
    r"urn:nir:stato:regio\.decreto:1942(?:-03-16)?;262:2(?=~|$)"
)
OLD_ACT_RE = re.compile(r"regio\.decreto:1942(?:-03-16)?;262:2(?=~|$)")

# These are the explicit preleggi forms recognized by the updated alias plus
# the deliberately broad abbreviation supplied for the legacy-data repair.
PRELEGGI_RE = re.compile(
    r"(?:"
    r"\bpreleggi\b|"
    r"\bdisp\.?\s*prel(?:\.|\b)|"
    r"\bdisposizioni\s+preliminari\b|"
    r"\bdisposizioni\s+sulla\s+legge\s+in\s+generale\b"
    r")",
    re.IGNORECASE,
)


@dataclass
class FileResult:
    path: Path
    text_column: str
    rows: int = 0
    old_urn_rows: int = 0
    matched_rows: int = 0
    urn_changes: int = 0
    url_changes: int = 0
    alias_changes: int = 0
    context_only_rows: int = 0
    samples: list[tuple[int, str, str, str]] = field(default_factory=list)
    applied: bool = False


@dataclass(frozen=True)
class CsvSpec:
    encoding: str
    lineterminator: str


def csv_spec(path: Path) -> CsvSpec:
    with path.open("rb") as handle:
        sample = handle.read(64 * 1024)
    encoding = "utf-8-sig" if sample.startswith(b"\xef\xbb\xbf") else "utf-8"
    if b"\r\n" in sample:
        lineterminator = "\r\n"
    elif b"\r" in sample and b"\n" not in sample:
        lineterminator = "\r"
    else:
        lineterminator = "\n"
    return CsvSpec(encoding=encoding, lineterminator=lineterminator)


def csv_files(paths: Sequence[Path]) -> list[Path]:
    found: set[Path] = set()
    for path in paths:
        resolved = path.expanduser().resolve()
        if resolved.is_file():
            if resolved.suffix.lower() != ".csv":
                raise ValueError(f"Not a CSV file: {resolved}")
            found.add(resolved)
        elif resolved.is_dir():
            found.update(item.resolve() for item in resolved.rglob("*.csv"))
        else:
            raise FileNotFoundError(resolved)
    return sorted(found)


def _column_indexes(header: Sequence[str], path: Path) -> tuple[int, int, int | None, int | None]:
    if "urn" not in header:
        raise ValueError(f"{path}: missing required 'urn' column")
    if "text" in header:
        text_column = "text"
    elif "original_text" in header:
        text_column = "original_text"
    else:
        raise ValueError(f"{path}: missing citation text column ('text' or 'original_text')")

    urn_index = header.index("urn")
    text_index = header.index(text_column)
    url_index = header.index("url") if "url" in header else None
    alias_index = header.index("alias") if "alias" in header else None
    return urn_index, text_index, url_index, alias_index


def _replace_annex(value: str) -> str:
    return OLD_ACT_RE.sub(
        lambda match: match.group(0)[:-1] + "1",
        value,
    )


def _matches(row: Sequence[str], urn_index: int, text_index: int) -> bool:
    return bool(OLD_URN_RE.search(row[urn_index]) and PRELEGGI_RE.search(row[text_index]))


def _transform_row(
    row: Sequence[str],
    urn_index: int,
    text_index: int,
    url_index: int | None,
    alias_index: int | None,
) -> tuple[list[str], bool, bool, bool]:
    output = list(row)
    if not _matches(row, urn_index, text_index):
        return output, False, False, False

    old_urn = output[urn_index]
    output[urn_index] = _replace_annex(old_urn)
    urn_changed = output[urn_index] != old_urn

    url_changed = False
    if url_index is not None:
        old_url = output[url_index]
        output[url_index] = _replace_annex(old_url)
        url_changed = output[url_index] != old_url

    alias_changed = False
    if alias_index is not None:
        alias_changed = output[alias_index] != "PRELEGGI"
        output[alias_index] = "PRELEGGI"

    return output, urn_changed, url_changed, alias_changed


def _checked_rows(
    handle,
    path: Path,
) -> tuple[csv.reader, list[str], int, int, int | None, int | None]:
    reader = csv.reader(handle, delimiter="|", quotechar='"')
    try:
        header = next(reader)
    except StopIteration as exc:
        raise ValueError(f"{path}: empty CSV") from exc
    urn_index, text_index, url_index, alias_index = _column_indexes(header, path)
    return reader, header, urn_index, text_index, url_index, alias_index


def scan_file(path: Path, sample_limit: int = 3) -> FileResult:
    spec = csv_spec(path)
    with path.open("r", encoding=spec.encoding, newline="") as handle:
        reader, header, urn_index, text_index, url_index, alias_index = _checked_rows(
            handle, path
        )
        result = FileResult(path=path, text_column=header[text_index])
        context_index = header.index("context") if "context" in header else None

        for row in reader:
            result.rows += 1
            if len(row) != len(header):
                raise ValueError(
                    f"{path}: CSV record ending on physical line {reader.line_num} has "
                    f"{len(row)} fields; expected {len(header)}"
                )
            has_old_urn = bool(OLD_URN_RE.search(row[urn_index]))
            if has_old_urn:
                result.old_urn_rows += 1
            matched = has_old_urn and bool(PRELEGGI_RE.search(row[text_index]))
            if not matched:
                if (
                    has_old_urn
                    and context_index is not None
                    and PRELEGGI_RE.search(row[context_index])
                ):
                    result.context_only_rows += 1
                continue

            result.matched_rows += 1
            transformed, urn_changed, url_changed, alias_changed = _transform_row(
                row, urn_index, text_index, url_index, alias_index
            )
            result.urn_changes += int(urn_changed)
            result.url_changes += int(url_changed)
            result.alias_changes += int(alias_changed)
            if len(result.samples) < sample_limit:
                result.samples.append(
                    (
                        result.rows,
                        row[text_index].replace("\n", "\\n"),
                        row[urn_index],
                        transformed[urn_index],
                    )
                )
    return result


def _validate_temp(source: Path, candidate: Path, expected: FileResult) -> None:
    source_spec = csv_spec(source)
    candidate_spec = csv_spec(candidate)
    with source.open("r", encoding=source_spec.encoding, newline="") as source_handle, candidate.open(
        "r", encoding=candidate_spec.encoding, newline=""
    ) as candidate_handle:
        source_data = _checked_rows(source_handle, source)
        candidate_data = _checked_rows(candidate_handle, candidate)
        source_reader, source_header, urn_index, text_index, url_index, alias_index = source_data
        candidate_reader, candidate_header, *_ = candidate_data
        if source_header != candidate_header:
            raise RuntimeError(f"{source}: header changed during rewrite")

        rows = 0
        matches = 0
        for rows, (before, after) in enumerate(
            _zip_equal(source_reader, candidate_reader, source), start=1
        ):
            if len(before) != len(source_header) or len(after) != len(source_header):
                raise RuntimeError(f"{source}: field count changed at record {rows}")
            expected_row, *_ = _transform_row(
                before, urn_index, text_index, url_index, alias_index
            )
            if _matches(before, urn_index, text_index):
                matches += 1
            if after != expected_row:
                raise RuntimeError(
                    f"{source}: unexpected field change at record {rows}"
                )

        if rows != expected.rows or matches != expected.matched_rows:
            raise RuntimeError(
                f"{source}: validation totals differ "
                f"(rows {rows}/{expected.rows}, matches {matches}/{expected.matched_rows})"
            )


def _zip_equal(left: Iterable[list[str]], right: Iterable[list[str]], path: Path):
    left_iter = iter(left)
    right_iter = iter(right)
    while True:
        try:
            left_row = next(left_iter)
        except StopIteration:
            left_row = None
        try:
            right_row = next(right_iter)
        except StopIteration:
            right_row = None
        if left_row is None and right_row is None:
            return
        if left_row is None or right_row is None:
            raise RuntimeError(f"{path}: row count changed during rewrite")
        yield left_row, right_row


def repair_file(path: Path, sample_limit: int = 3) -> FileResult:
    result = scan_file(path, sample_limit=sample_limit)
    if result.matched_rows == 0:
        return result

    spec = csv_spec(path)
    temporary_path: Path | None = None
    try:
        with path.open("r", encoding=spec.encoding, newline="") as source_handle:
            reader, header, urn_index, text_index, url_index, alias_index = _checked_rows(
                source_handle, path
            )
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding=spec.encoding,
                newline="",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as output_handle:
                temporary_path = Path(output_handle.name)
                writer = csv.writer(
                    output_handle,
                    delimiter="|",
                    quotechar='"',
                    quoting=csv.QUOTE_MINIMAL,
                    lineterminator=spec.lineterminator,
                )
                writer.writerow(header)
                for row in reader:
                    if len(row) != len(header):
                        raise ValueError(
                            f"{path}: CSV record ending on physical line {reader.line_num} has "
                            f"{len(row)} fields; expected {len(header)}"
                        )
                    transformed, *_ = _transform_row(
                        row, urn_index, text_index, url_index, alias_index
                    )
                    writer.writerow(transformed)
                output_handle.flush()
                os.fsync(output_handle.fileno())

        _validate_temp(path, temporary_path, result)
        shutil.copymode(path, temporary_path)
        os.replace(temporary_path, path)
        temporary_path = None
        result.applied = True
        return result
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def print_result(result: FileResult, root: Path, show_samples: bool) -> None:
    try:
        label = result.path.relative_to(root)
    except ValueError:
        label = result.path
    mode = "APPLIED" if result.applied else "AUDIT"
    print(
        f"{mode} {label}: rows={result.rows:,} old_part2={result.old_urn_rows:,} "
        f"matched={result.matched_rows:,} urn={result.urn_changes:,} "
        f"url={result.url_changes:,} alias={result.alias_changes:,} "
        f"context_only_not_changed={result.context_only_rows:,} "
        f"text_column={result.text_column}",
        flush=True,
    )
    if show_samples:
        for row_number, text, before, after in result.samples:
            print(
                f"  row {row_number:,}: {text!r}\n"
                f"    {before}\n"
                f"    -> {after}",
                flush=True,
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="CSV files or directories (defaults to both extraction output trees)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="atomically rewrite and validate files; otherwise perform a dry-run audit",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=3,
        help="number of matching samples to print per file (default: 3)",
    )
    args = parser.parse_args()

    paths = args.paths or list(DEFAULT_PATHS)
    files = csv_files(paths)
    if not files:
        raise SystemExit("No CSV files found")

    total_rows = 0
    total_matches = 0
    total_context_only = 0
    changed_files = 0
    matching_files = 0
    for path in files:
        result = (
            repair_file(path, max(0, args.samples))
            if args.apply
            else scan_file(path, max(0, args.samples))
        )
        print_result(result, SRC_ROOT, show_samples=args.samples > 0)
        total_rows += result.rows
        total_matches += result.matched_rows
        total_context_only += result.context_only_rows
        changed_files += int(result.applied)
        matching_files += int(result.matched_rows > 0)

    action = "Repaired" if args.apply else "Would repair"
    print(
        f"{action} {total_matches:,} rows across {changed_files if args.apply else matching_files} "
        f"of {len(files)} scanned files ({total_rows:,} rows total); "
        f"context-only rows intentionally unchanged: {total_context_only:,}.",
        flush=True,
    )


if __name__ == "__main__":
    main()
