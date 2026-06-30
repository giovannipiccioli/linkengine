"""
Core data model for linkengine: the span vocabulary and the typed objects that flow
through the pipeline.

Spans are typed, offset-anchored annotations over the *immutable* input text. The
assembler groups spans into References; the normalizer turns each Reference into a
feature row (a flat dict of recognition fields plus the canonical ``urn``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Entity(str, Enum):
    # partition pieces (ranked; see PARTITION_RANK)
    ALLEGATO = "ALLEGATO"
    CONSIDERANDO = "CONSIDERANDO"  # EU legislative recital
    ARTICLE = "ARTICLE"
    COMMA = "COMMA"
    PARAGRAPH = "PARAGRAPH"
    LETTER = "LETTER"
    NUMERO = "NUMERO"          # numbered item *inside* a partition (not a doc number)
    PUNTO = "PUNTO"            # EU case-law point ("punto 31")
    PERIODO = "PERIODO"        # sentence within a comma ("primo periodo")
    # numerics
    NUMBER = "NUMBER"
    YEAR = "YEAR"
    NUM_YEAR = "NUM_YEAR"      # "600/1973" style: a number bound to a year
    CASE_NUMBER = "CASE_NUMBER"
    RV_NUMBER = "RV_NUMBER"    # Cassazione official maxim number ("Rv. 246838-01")
    DATE = "DATE"
    # act / actor identifiers
    DOCTYPE = "DOCTYPE"        # value = doc-type code (L, DL, DLGS, DECR, ...)
    AUTHORITY = "AUTHORITY"    # value = case-law/legislative authority code
    OTHER_AUTH = "OTHER_AUTH"
    ALIAS = "ALIAS"            # value = legislative alias code (COD_CIV, TUIR, ...)
    EU_ACRONYM = "EU_ACRONYM"  # UE / CE / CEE / CECA
    REGION = "REGION"
    CITY = "CITY"
    SUBJECT = "SUBJECT"        # CIVILE / PENALE
    # glue
    CONNECTOR = "CONNECTOR"    # del/della/dei/n./ai sensi di ... (assembly hints)


# Partition hierarchy (higher = coarser/shallower). comma and paragrafo are siblings
# (national vs EU); numero and punto are siblings (sub-item vs EU-caselaw point).
PARTITION_RANK = {
    Entity.ALLEGATO: 9, Entity.CONSIDERANDO: 8, Entity.ARTICLE: 8,
    Entity.COMMA: 7, Entity.PARAGRAPH: 7, Entity.LETTER: 6,
    Entity.NUMERO: 5, Entity.PUNTO: 5, Entity.PERIODO: 4,
}

# Canonical partition label used when serializing the `partition` field.
PARTITION_LABEL = {
    Entity.ALLEGATO: "allegato", Entity.CONSIDERANDO: "considerando",
    Entity.ARTICLE: "articolo", Entity.COMMA: "comma", Entity.PARAGRAPH: "paragrafo",
    Entity.LETTER: "lettera", Entity.NUMERO: "numero", Entity.PUNTO: "punto",
    Entity.PERIODO: "periodo",
}

MONTHS = {
    "gennaio": "01", "febbraio": "02", "marzo": "03", "aprile": "04", "maggio": "05",
    "giugno": "06", "luglio": "07", "agosto": "08", "settembre": "09", "ottobre": "10",
    "novembre": "11", "dicembre": "12",
}

# The feature-row schema: the recognition fields the engine fills. The canonical ``urn`` is
# appended after normalization. ``empty_row`` seeds every field to "".
FEATURE_FIELDS: List[str] = [
    "id", "ref-type", "ref-scope", "text", "context", "alias", "partition",
    "doc-type", "authority", "ministry", "region", "city", "section", "other-authority",
    "eu-acronym", "number", "year", "full-number", "case-number", "doc-date",
    "rv-number", "url",
]


@dataclass
class Span:
    start: int
    end: int
    entity: Entity
    value: str = ""
    text: str = ""
    attrs: Dict[str, str] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"<{self.entity.value} [{self.start}:{self.end}] {self.value!r} {self.text!r}>"


@dataclass
class Reference:
    """A group of spans forming one citation, with a char span over the source text."""
    spans: List[Span] = field(default_factory=list)
    start: int = 0
    end: int = 0

    def of(self, entity: Entity) -> Optional[Span]:
        for s in self.spans:
            if s.entity == entity:
                return s
        return None

    def all_of(self, entity: Entity) -> List[Span]:
        return [s for s in self.spans if s.entity == entity]

    @property
    def text(self) -> str:
        return self.attrs.get("text", "")

    attrs: Dict[str, str] = field(default_factory=dict)


@dataclass
class ExtractResult:
    rows: List[Dict[str, str]] = field(default_factory=list)   # one feature dict per reference
    references: List[Reference] = field(default_factory=list)
    spans: List[Span] = field(default_factory=list)
    trace: List = field(default_factory=list)                  # [(module_name, [spans...])]


def empty_row() -> Dict[str, str]:
    return {k: "" for k in FEATURE_FIELDS}
