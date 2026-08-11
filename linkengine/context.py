"""Validated per-document metadata used to resolve context-dependent citations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .catalog import COURTS
from .geo import city_code, region_code, region_urn
from .normalize import MAX_YEAR, MIN_YEAR


@dataclass(frozen=True)
class DocumentContext:
    """Metadata about the document currently being processed.

    ``authority`` is one of the stable codes in :mod:`linkengine.catalog`. ``city`` and
    ``region`` accept human-readable names or their canonical ECLI codes. ``region`` also
    supplies the default for unqualified regional laws unless ``regional_law_region`` is
    explicitly provided (an empty string disables that fallback).

    The context is deliberately applied only to explicit self-references such as "questa
    Corte". A bare "sentenza n. 123/2020" remains unresolved. ``chamber`` is the one
    exception, and it is a considered one — see below.

    ``chamber`` ("CIV" | "PEN") is the Cassazione branch of THIS document. Italian citation
    practice routinely omits it ("Cass. n. 13808/2025", "Sez. 1, n. 41738"), yet `snciv` and
    `snpen` number independently, so those citations name two different real decisions and
    nothing in the citation itself can separate them. Absent a signal the engine reads them
    as civile, which is right for ~98.8% of the corpus but wrong for essentially every
    citation inside a penal judgment. Setting ``chamber="PEN"`` supplies the missing branch
    for Cassazione citations that state none. It is an assumption, not a fact — measured at
    roughly 50:1 in its favour (see ``_apply_context_chamber`` in engine.py) — so it fills
    silence only: a citation that names its own chamber always wins, and ``chamber="CIV"``
    is accepted but changes nothing, civile being the fallback already.
    """

    authority: str = ""
    city: str = ""
    region: str = ""
    regional_law_region: Optional[str] = None
    document_year: Optional[int] = None
    chamber: str = ""

    def __post_init__(self):
        authority = str(self.authority or "").strip()
        if authority and authority not in COURTS:
            allowed = ", ".join(sorted(COURTS))
            raise ValueError(f"unknown document authority {authority!r}; expected one of: {allowed}")

        city = ""
        if self.city:
            city = city_code(self.city) or ""
            if not city:
                raise ValueError(f"unknown document city {self.city!r}")

        region = ""
        if self.region:
            region = region_code(self.region) or ""
            if not region:
                raise ValueError(f"unknown document region {self.region!r}")

        law_region_source = self.region if self.regional_law_region is None \
            else self.regional_law_region
        law_region = ""
        if law_region_source:
            law_region = region_urn(law_region_source) or ""
            if not law_region:
                raise ValueError(f"unknown regional-law region {law_region_source!r}")

        document_year = None
        if self.document_year not in (None, ""):
            try:
                document_year = int(self.document_year)
            except (TypeError, ValueError):
                raise ValueError(f"invalid document year {self.document_year!r}") from None
            if not MIN_YEAR <= document_year <= MAX_YEAR:
                raise ValueError(f"invalid document year {self.document_year!r}")

        chamber = str(self.chamber or "").strip().upper()
        if chamber and chamber not in ("CIV", "PEN"):
            raise ValueError(f"unknown document chamber {self.chamber!r}; expected 'CIV' or 'PEN'")

        object.__setattr__(self, "chamber", chamber)
        object.__setattr__(self, "authority", authority)
        object.__setattr__(self, "city", city)
        object.__setattr__(self, "region", region)
        object.__setattr__(self, "regional_law_region", law_region)
        object.__setattr__(self, "document_year", document_year)
