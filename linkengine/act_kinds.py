"""Semantic registry for the Italian legislative act families supported by LinkEngine.

The same record drives free-text recognition, canonical NIR construction and URN rendering.
Corpus spellings are aliases of a semantic kind; generated URNs always use the small,
canonical ``nir_pair``.  The registry is intentionally conservative: unknown dotted NIR
types are not accepted implicitly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


NirPair = Tuple[str, str]


@dataclass(frozen=True)
class ActKind:
    """One semantic family of Italian legislative acts.

    ``engine_pair`` is LinkEngine's compact internal ``(doc-type, authority)`` pair;
    ``nir_pair`` is the canonical NIR authority/type emitted by the library.  ``nir_aliases``
    lists known source spellings with the same meaning.
    """

    code: str
    display: str
    engine_pair: NirPair
    nir_pair: NirPair
    patterns: Tuple[str, ...] = field(default_factory=tuple)
    nir_aliases: Tuple[NirPair, ...] = field(default_factory=tuple)


ACT_KINDS: Tuple[ActKind, ...] = (
    # Historical/specific forms must precede their shorter modern parents in recognition.
    ActKind(
        "DLGS_LGT", "decreto legislativo luogotenenziale", ("DLGS_LGT", ""),
        ("luogotenente", "decreto.legislativo"),
        patterns=(
            r"\bdecreto\s+legislativo\s+luogotenenziale\b",
            r"\bd\.?\s?lgs\.?\s?lgt\.?(?!\w)",
        ),
        nir_aliases=(("stato", "decreto.legislativo.luogotenenziale"),),
    ),
    ActKind(
        "DL_LGT", "decreto-legge luogotenenziale", ("DL_LGT", ""),
        ("luogotenente", "decreto.legge"),
        patterns=(
            r"\bdecreto[-\s]?legge\s+luogotenenziale\b",
            r"\bd\.?\s?l\.?\s?lgt\.?(?!\w)",
        ),
        nir_aliases=(("stato", "decreto.legge.luogotenenziale"),),
    ),
    ActKind(
        "DECR_LGT", "decreto luogotenenziale", ("DECR_LGT", ""),
        ("luogotenente", "decreto"),
        patterns=(
            r"\bdecreto\s+luogotenenziale\b",
            r"\bd\.?\s?lgt\.?(?!\w)",
        ),
        nir_aliases=(("stato", "decreto.luogotenenziale"),),
    ),
    ActKind(
        "DLGS_CPS", "decreto legislativo del Capo provvisorio dello Stato", ("DLGS_CPS", ""),
        ("capo.provvisorio.stato", "decreto.legislativo"),
        patterns=(
            r"\bdecreto\s+legislativo\s+del\s+capo\s+provvisorio\s+dello\s+stato\b",
            r"\bd\.?\s?lgs\.?\s?c\.?\s?p\.?\s?s\.?(?!\w)",
        ),
        nir_aliases=(("stato", "decreto.legislativo.del.capo.provvisorio.dello.stato"),),
    ),
    ActKind(
        "DL_CPS", "decreto-legge del Capo provvisorio dello Stato", ("DL_CPS", ""),
        ("capo.provvisorio.stato", "decreto.legge"),
        patterns=(
            r"\bdecreto[-\s]?legge\s+del\s+capo\s+provvisorio\s+dello\s+stato\b",
            r"\bd\.?\s?l\.?\s?c\.?\s?p\.?\s?s\.?(?!\w)",
        ),
        nir_aliases=(("stato", "decreto.legge.del.capo.provvisorio.dello.stato"),),
    ),
    ActKind(
        "DECR_CPS", "decreto del Capo provvisorio dello Stato", ("DECR_CPS", ""),
        ("capo.provvisorio.stato", "decreto"),
        patterns=(
            r"\bdecreto\s+del\s+capo\s+provvisorio\s+dello\s+stato\b",
            r"\bd\.?\s?c\.?\s?p\.?\s?s\.?(?!\w)",
        ),
        nir_aliases=(("stato", "decreto.del.capo.provvisorio.dello.stato"),),
    ),
    ActKind(
        "DLGS_PRES", "decreto legislativo presidenziale", ("DLGS_PRES", ""),
        ("stato", "decreto.legislativo.presidenziale"),
        patterns=(
            r"\bdecreto\s+legislativo\s+presidenziale\b",
            r"\bd\.?\s?lgs\.?\s?pres\.?(?!\w)",
        ),
    ),
    ActKind(
        "RDLGS", "regio decreto legislativo", ("RDLGS", ""),
        ("stato", "regio.decreto.legislativo"),
        patterns=(
            r"\bregio\s+decreto\s+legislativo\b",
            r"\br\.?\s?d\.?\s?lgs\.?(?!\w)",
        ),
    ),
    ActKind(
        "RDL", "regio decreto-legge", ("RDL", ""),
        ("stato", "regio.decreto.legge"),
        patterns=(
            r"\bregio\s+decreto[-\s]?legge\b",
            r"\br\.?\s?d\.?\s?l\.?(?!\w)",
        ),
    ),
    ActKind(
        "DPCM", "D.P.C.M.", ("DECR", "PRES_CONS_MIN"),
        ("presidente.consiglio.ministri", "decreto"),
        patterns=(
            r"\bdecreto\s+del\s+presidente\s+del\s+consiglio\s+dei\s+ministri\b",
            r"\bd\.?\s?p\.?\s?c\.?\s?m\.?(?!\w)",
        ),
        nir_aliases=(
            ("stato", "decreto.del.presidente.del.consiglio.dei.ministri"),
            ("presidenza.consiglio.ministri", "decreto"),
        ),
    ),
    ActKind(
        "DPR", "D.P.R.", ("DECR", "PRES_REP"),
        ("presidente.repubblica", "decreto"),
        patterns=(
            r"\bdecreto\s+del\s+presidente\s+della\s+repubblica\b",
            r"\bd\.?\s?p\.?\s?r\.?(?!\w)",
        ),
        nir_aliases=(
            ("stato", "decreto.del.presidente.della.repubblica"),
            ("presidenza.repubblica", "decreto.del.presidente.della.repubblica"),
            ("ministero.tesoro", "decreto.del.presidente.della.repubblica"),
        ),
    ),
    ActKind(
        "DLGS", "decreto legislativo", ("DLGS", ""), ("stato", "decreto.legislativo"),
        patterns=(
            r"\bdecreto\s+legislativo\b",
            r"\bdecreto\s+lgs\.?(?!\w)",
            r"\bd\.?\s?l\.?gs\.?(?!\w)",
            r"\bd\.?\s?lgs\.?(?!\w)",
            r"\bd\.?\s?lg?\.?\s?v\.?o?\.?(?!\w)",
            r"\bdec(?:r|reto)?\.?\s*leg(?:isl(?:ativo)?|\.?\s*v\.?o?)\.?(?!\w)",
        ),
    ),
    ActKind(
        "DL", "decreto-legge", ("DL", ""), ("stato", "decreto.legge"),
        patterns=(
            r"\bdecreto(?:[-\s]|\u00ad)?legge\b",
            r"\bdec(?:r|reto)?\.?\s*legge\b",
            r"\bd\.?\s?l\.?(?!gs)(?!\w)",
        ),
    ),
    ActKind(
        "LC", "legge costituzionale", ("LC", ""), ("stato", "legge.costituzionale"),
        patterns=(r"\blegge\s+costituzionale\b",),
    ),
    ActKind(
        "RD", "regio decreto", ("RD", ""), ("stato", "regio.decreto"),
        patterns=(r"\bregio\s+decreto\b", r"\br\.?\s?d\.?(?!\w)"),
    ),
    ActKind(
        "DM", "decreto ministeriale", ("DECR", "MINISTERO"), ("ministero", "decreto"),
        patterns=(
            r"\bdecreto\s+del\s+ministro\s+dell['’]?\s*economia\s+e\s+delle\s+finanze\b",
            r"\bdecreto\s+ministeriale\b",
            r"\bdecreto\s+(?:del\s+)?(?:m\.?e\.?f\.?|mef|m\.?i\.?s\.?e\.?|mise|mit|mims|m\.?i\.?u\.?r\.?|miur)\b",
            r"\bd\.?\s?m\.?(?:\s+(?:m\.?e\.?f\.?|mef|m\.?i\.?s\.?e\.?|mise|mit|mims|"
            r"m\.?i\.?u\.?r\.?|miur))?(?!\w)",
        ),
        nir_aliases=(("stato", "decreto.ministeriale"),),
    ),
    ActKind(
        "ORD_MIN", "ordinanza ministeriale", ("ORD_MIN", "MINISTERO"),
        ("ministero", "ordinanza"),
        patterns=(r"\bordinanza\s+ministeriale\b", r"\bord\.?\s*min\.?(?!\w)"),
    ),
    ActKind(
        "DELIB_INTERMIN", "deliberazione interministeriale", ("DELIB_INTERMIN", ""),
        ("comitato.interministeriale", "deliberazione"),
        patterns=(
            r"\bdeliberazione\s+interministeriale\b",
            r"\bdeliberazione\s+del\s+comitato\s+interministeriale\b",
        ),
    ),
    ActKind(
        "L", "legge", ("L", ""), ("stato", "legge"),
        patterns=(
            r"\bl\.\s*n[.°]*(?=\s*\d)",
            r"\bl\.(?=\s*\d)",
            r"\bl\s+(?=\d{1,5}\s*/\s*\d{2,4}\b)",
            r"\blegg[ei]\b(?!\s+(?:regional|(?:della\s+)?regione))",
        ),
    ),
)


ACT_KIND_BY_CODE: Dict[str, ActKind] = {kind.code: kind for kind in ACT_KINDS}
ACT_KIND_BY_ENGINE_PAIR: Dict[NirPair, ActKind] = {kind.engine_pair: kind for kind in ACT_KINDS}

_ACT_KIND_BY_EXACT_NIR: Dict[NirPair, ActKind] = {}
for _kind in ACT_KINDS:
    for _pair in (_kind.nir_pair,) + _kind.nir_aliases:
        _ACT_KIND_BY_EXACT_NIR[_pair] = _kind


def act_kind_for_nir(authority: str, doctype: str) -> Optional[ActKind]:
    """Return the supported semantic kind for a corpus/citation NIR pair, if any."""
    exact = _ACT_KIND_BY_EXACT_NIR.get((authority, doctype))
    if exact:
        return exact
    authority_tokens = set(authority.split("."))
    if doctype in {"decreto", "decreto.ministeriale"} and \
            authority_tokens.intersection({"ministero", "ministro"}):
        return ACT_KIND_BY_CODE["DM"]
    if doctype == "ordinanza" and authority_tokens.intersection({"ministero", "ministro"}):
        return ACT_KIND_BY_CODE["ORD_MIN"]
    if doctype == "deliberazione" and authority.startswith("comitato.interministeriale"):
        return ACT_KIND_BY_CODE["DELIB_INTERMIN"]
    return None


def canonical_nir_pair(authority: str, doctype: str) -> NirPair:
    """Return the canonical NIR pair for a supported semantic act kind.

    Unknown pairs are returned unchanged.  This makes the registry usable by
    ingestion code without making it guess at unfamiliar source vocabularies.
    """
    kind = act_kind_for_nir(authority, doctype)
    return kind.nir_pair if kind else (authority, doctype)


def display_name_for_nir(authority: str, doctype: str) -> str:
    """Human label for a supported pair; empty for an unknown semantic kind."""
    kind = act_kind_for_nir(authority, doctype)
    return kind.display if kind else ""


# Compatibility/consumer views, all derived from the records above.
EMANANTE_TIPO = {
    kind.engine_pair: kind.nir_pair
    for kind in ACT_KINDS
}
URN_DOCTYPE_NAME = {
    f"{authority}:{doctype}": kind.display
    for kind in ACT_KINDS
    for authority, doctype in ((kind.nir_pair,) + kind.nir_aliases)
}
DOCTYPE_PATTERNS = tuple(
    (pattern, kind.engine_pair[0], kind.engine_pair[1], "nazionale")
    for kind in ACT_KINDS
    for pattern in kind.patterns
)
