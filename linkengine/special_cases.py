"""Narrow lexical exceptions used by citation recognition.

Structural rules belong in the recognizer, assembler, or classifier that owns them. This
module is only for text forms that need an explicit exception and cannot be expressed as a
normal citation type.
"""
from __future__ import annotations

import re


I = re.IGNORECASE

_PROTOCOL_BEFORE = re.compile(r"prot(?:ocollo)?\.?\s*n?[.°]*\s*$", I)
_PROVVEDIMENTO_BEFORE = re.compile(r"\bprovvediment[oi]\b", I)

_PRASSI_DOCUMENT_BEFORE = re.compile(r"\b(?:not[ae]|provvediment[oi])\s*$", I)
_COMPOSITE_NUMBER_AFTER = re.compile(
    r"\s*-\s*\d{1,6}\s+del\b.{0,160}\bagenzia\s+(?:delle\s+)?entrate\b",
    I | re.DOTALL,
)


def protocol_is_provvedimento_number(text: str, start: int) -> bool:
    """True when prot. n. identifies an explicit administrative provvedimento."""
    return bool(
        _PROTOCOL_BEFORE.search(text[max(0, start - 72):start])
        and _PROVVEDIMENTO_BEFORE.search(text[max(0, start - 150):start])
    )


def is_agenzia_composite_number_prefix(text: str, start: int, end: int) -> bool:
    """True for the office-code prefix in nota n. 954-87316 del ... Agenzia Entrate.

    The document-type and issuer checks intentionally keep this narrower than the common
    n. X-Y del ... form used by judgments, tax notices, and many unrelated documents.
    """
    return bool(
        _PRASSI_DOCUMENT_BEFORE.search(text[max(0, start - 60):start])
        and _COMPOSITE_NUMBER_AFTER.match(text[end:end + 190])
    )
