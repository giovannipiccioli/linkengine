"""Context and identifier resolution for opt-in legislation (``normativa``) extraction.

Ordinary legal prose must not turn every bare ``articolo`` or ``comma`` into a citation.
Normative texts are different: inside one known structural unit, an otherwise unclaimed
partition normally points to the act currently being read.  This module holds that explicit
context and performs the small, deterministic locator merge; recognition and ordinary
citation assembly remain in their existing modules.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, Iterable, List, Optional, Tuple

from .act_kinds import act_kind_for_nir
from .model import Entity, PARTITION_LABEL, PARTITION_RANK, Span
from .normalize import partition_to_locator


STANDARD_MODE = "standard"
NORMATIVA_MODE = "normativa"
MODES = {STANDARD_MODE, NORMATIVA_MODE}
INTERNAL_ATTR = "normativa-internal"
ATTACHED_ATTR = "normativa-attached"
CURRENT_ATTR = "normativa-current"

_NIR_UNIT = re.compile(
    r"^(urn:nir:([^:;~]+):([^:;~]+):(\d{4}(?:-\d{2}-\d{2})?);([^~]+))"
    r"~([a-z0-9][a-z0-9-]*)$",
    re.I,
)
_CELEX_UNIT = re.compile(
    r"^(CELEX:3\d{4}([A-Z])[A-Z0-9()/-]+)~([a-z0-9][a-z0-9-]*)$",
    re.I,
)
_RELATIVE = re.compile(r"\bpresente\s+(articolo|comma)\b", re.I)

_CELEX_DOCTYPE = {"R": "REG", "L": "DIR", "D": "DECIS", "H": "RACC"}

_LOCATOR_RANK = {
    "all": 9,
    "cons": 8,
    "art": 8,
    "comma": 7,
    "num": 5,
    "let": 6,
    "punto": 5,
    "periodo": 4,
}
_LOCATOR_PREFIXES = tuple(sorted(_LOCATOR_RANK, key=len, reverse=True))


def _locator_tokens(locator: str) -> List[Tuple[str, int]]:
    tokens: List[Tuple[str, int]] = []
    for token in locator.split("-"):
        prefix = next((p for p in _LOCATOR_PREFIXES if token.startswith(p)), "")
        if prefix and len(token) > len(prefix):
            tokens.append((token, _LOCATOR_RANK[prefix]))
    return tokens


def _value_for(tokens: Iterable[Tuple[str, int]], prefix: str) -> str:
    for token, _ in tokens:
        if token.startswith(prefix) and len(token) > len(prefix):
            return token[len(prefix):]
    return ""


def target_urn_for(act_base: str, current_locator: str, spans: Iterable[Span]) -> str:
    """Resolve a partition path against an arbitrary legislative act and local locator.

    ``NormativaContext`` uses this for the act supplied by the caller.  Novella handling uses
    the same function with the already-recognized amended act and the article selected by the
    amendment.  Keeping identifier merging here prevents the scope classifier from learning
    anything about NIR or CELEX syntax.
    """
    scheme = "celex" if act_base.upper().startswith("CELEX:") else "nir"
    current_tokens = tuple(_locator_tokens((current_locator or "").lower()))
    effective = []
    for span in spans:
        if span.entity not in PARTITION_RANK:
            continue
        value = span.value
        if span.attrs.get("normativa-relative"):
            prefix = "art" if span.entity == Entity.ARTICLE else "comma"
            value = _value_for(current_tokens, prefix)
        if value:
            effective.append((span.entity, value))
    effective.sort(key=lambda part: -PARTITION_RANK[part[0]])
    if not effective:
        return ""

    entity, value = effective[0]
    if entity == Entity.ALLEGATO:
        annex_locator = partition_to_locator(f"{PARTITION_LABEL[entity]}-{value}")
        if scheme == "celex":
            return f"{act_base}~{annex_locator}" if annex_locator else ""
        annex = annex_locator[3:] if annex_locator.startswith("all") else ""
        prefix, payload = act_base.rsplit(";", 1)
        act_root = prefix + ";" + payload.split(":", 1)[0]
        return f"{act_root}:{annex}" if annex else ""

    if entity == Entity.CONSIDERANDO:
        if scheme != "celex":
            return ""
        recital = partition_to_locator(f"{PARTITION_LABEL[entity]}-{value}")
        return f"{act_base}~{recital}" if recital else ""

    first_rank = PARTITION_RANK[entity]
    current_prefix = [(token, rank) for token, rank in current_tokens if rank > first_rank]
    if entity != Entity.ARTICLE:
        if not any(token.startswith("art") for token, _ in current_prefix):
            return ""
        if first_rank < PARTITION_RANK[Entity.COMMA] and not any(
                PARTITION_RANK[Entity.ARTICLE] > rank > first_rank
                for _, rank in current_prefix):
            return ""

    field = "_".join(
        f"{PARTITION_LABEL[part_entity]}-{part_value}"
        for part_entity, part_value in effective)
    candidate = partition_to_locator(field)
    if not candidate:
        return ""
    locator = "-".join([token for token, _ in current_prefix] + candidate.split("-"))
    return act_base + "~" + locator


@dataclass(frozen=True)
class NormativaContext:
    """The canonical act identity and structural locator of the unit being processed."""

    current_unit_urn: str
    scheme: str
    act_base: str
    act_root: str
    authority_nir: str
    doctype_nir: str
    date: str
    number: str
    current_locator: str
    current_tokens: Tuple[Tuple[str, int], ...]

    @classmethod
    def from_urn(cls, value: str) -> "NormativaContext":
        urn = str(value or "").strip()
        match = _NIR_UNIT.fullmatch(urn)
        if match:
            act_base, authority, doctype, date, payload, locator = match.groups()
            number = payload.split(":", 1)[0]
            if not number:
                raise ValueError("current_unit_urn must contain an act number")
            scheme = "nir"
            act_root = act_base.rsplit(";", 1)[0] + ";" + number
        else:
            match = _CELEX_UNIT.fullmatch(urn)
            if not match:
                raise ValueError(
                    "current_unit_urn must be a canonical NIR or CELEX unit identifier, "
                    "for example 'urn:nir:stato:legge:2020-02-01;10~art3' or "
                    "'CELEX:32016R0679~art17'")
            act_base, celex_doctype, locator = match.groups()
            celex = act_base[len("CELEX:"):]
            authority = ""
            doctype = celex_doctype.upper()
            date = celex[1:5]
            raw_number = celex[6:]
            number = (raw_number.lstrip("0") or "0") if raw_number.isdigit() else raw_number
            scheme = "celex"
            act_root = act_base
        tokens = tuple(_locator_tokens(locator.lower()))
        if not tokens or not any(rank >= PARTITION_RANK[Entity.ARTICLE] for _, rank in tokens):
            raise ValueError("current_unit_urn must identify an article, recital, or annex unit")
        return cls(
            current_unit_urn=urn,
            scheme=scheme,
            act_base=act_base,
            act_root=act_root,
            authority_nir=authority.lower(),
            doctype_nir=doctype.lower(),
            date=date,
            number=number,
            current_locator=locator.lower(),
            current_tokens=tokens,
        )

    @property
    def current_article(self) -> str:
        return _value_for(self.current_tokens, "art")

    @property
    def current_comma(self) -> str:
        return _value_for(self.current_tokens, "comma")

    def recognize_relative_partitions(self, text: str) -> List[Span]:
        """Recognize deictic self-locators whose numeric value comes from the unit URN."""
        spans: List[Span] = []
        for match in _RELATIVE.finditer(text):
            label = match.group(1).lower()
            entity = Entity.ARTICLE if label == "articolo" else Entity.COMMA
            value = self.current_article if entity == Entity.ARTICLE else self.current_comma
            if value:
                spans.append(Span(match.start(), match.end(), entity, value, match.group(0),
                                  {"normativa-relative": "1"}))
        return spans

    def seed_row(self, row: Dict[str, str]) -> None:
        """Fill the act identity fields that a partition-only internal reference omits."""
        row["ref-type"] = "legislation"
        row["number"] = self.number
        row["year"] = self.date[:4]
        if self.scheme == "celex":
            row["ref-scope"] = "comunitario"
            row["doc-type"] = _CELEX_DOCTYPE.get(self.doctype_nir.upper(), "")
            return
        if len(self.date) == 10:
            row["doc-date"] = self.date

        if self.authority_nir.startswith("regione.") and self.doctype_nir == "legge":
            row["doc-type"] = "L"
            row["region"] = self.authority_nir[len("regione."):]
            row["ref-scope"] = "regionale"
            return

        row["ref-scope"] = "nazionale"
        kind = act_kind_for_nir(self.authority_nir, self.doctype_nir)
        if kind:
            row["doc-type"], row["authority"] = kind.engine_pair

    def target_urn(self, spans: Iterable[Span]) -> str:
        """Merge a recognized partition path into the current act's exact identifier base.

        Article references replace the current article.  A bare comma inherits that article.
        Still-deeper bare partitions require a sub-article parent in the supplied unit URN;
        this avoids inventing a comma for an isolated ``lettera b)`` in an article body.
        """
        return target_urn_for(self.act_base, self.current_locator, spans)


def validate_mode(mode: str, current_unit_urn: Optional[str]) -> Optional[NormativaContext]:
    """Validate the public extraction mode and build its optional unit context."""
    normalized = str(mode or STANDARD_MODE).strip().lower()
    if normalized not in MODES:
        allowed = ", ".join(sorted(MODES))
        raise ValueError(f"unknown extraction mode {mode!r}; expected one of: {allowed}")
    if normalized == NORMATIVA_MODE:
        return NormativaContext.from_urn(current_unit_urn or "")
    if current_unit_urn not in (None, ""):
        raise ValueError("current_unit_urn is only valid when mode='normativa'")
    return None
