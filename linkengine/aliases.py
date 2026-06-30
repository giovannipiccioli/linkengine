"""
Legislative aliases — codes, consolidated texts (testi unici) and EU/international acts.

**One record per alias.** Each alias is a single :class:`Alias` in the ordered ``ALIASES``
registry, carrying everything that defines it:

* ``patterns`` — how it is *recognized* in text (full names + abbreviations, e.g. ``c.c.``
  ``c.p.c.`` ``TUIR`` ``T.U.B.`` ``l. fall.``); empty for acts present in the alias
  table but not yet recognized from free text;
* ``nir`` — its ``urn:nir`` *act base* (``authority:doctype:date;number[:annex]``) for national
  acts (the standard ``urn:nir`` base for each code). The date is kept full (YYYY-MM-DD);
  the URN layer trims it to the year;
* ``celex`` — its CELEX id for EU acts that are a single regulation/treaty/charter;
* ``display`` — its human name for ``urn_to_text``;
* ``scope`` — ``"national"`` / ``"eu"`` / ``"intl"``.

To add or edit an alias, change its one record here — the per-field maps consumed elsewhere
(``ALIAS_NIR`` / ``ALIAS_DISPLAY`` / ``ALIAS_CELEX`` / ``EU_ALIASES`` / ``INTL_ALIASES`` /
``ALIAS_PATTERNS``) are *derived* from ``ALIASES`` at import time.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .model import Entity, Span
from .normalize import partition_to_locator

I = re.IGNORECASE


@dataclass(frozen=True)
class Alias:
    """A single legislative alias and everything that defines it (recognition + nir/celex +
    display + scope). See the module docstring."""
    code: str
    scope: str = "national"                       # "national" | "eu" | "intl"
    patterns: Tuple[str, ...] = field(default_factory=tuple)   # regex recognized in text
    nir: str = ""                                 # urn:nir act base (national)
    celex: str = ""                               # CELEX id (eu single act)
    display: str = ""                             # human name for urn_to_text


# ── The registry — one record per alias, recognition order preserved ────────────
# Order matters only for readability: recognition collects *all* matches and resolves overlaps
# by length (see recognizers._nonoverlap), so a longer name always wins over a shorter one
# regardless of position. The grouping (disposizioni d'attuazione, then codici, then testi
# unici, then EU acts) mirrors how a reader scans the text.
ALIASES: List[Alias] = [
    # — disposizioni di attuazione (before the plain codes) —
    Alias("DISP_ATT_COD_PROC_CIV", nir="stato:regio.decreto:1941-08-25;1368:1",
          patterns=(r"disp(?:osizioni)?\.?\s+(?:di\s+)?att(?:uazione)?\.?\s+(?:del\s+)?c\.?\s?p\.?\s?c\.?",)),
    Alias("DISP_ATT_COD_PROC_PEN", nir="stato:decreto.legislativo:1989-07-28;271:1",
          patterns=(r"disp(?:osizioni)?\.?\s+(?:di\s+)?att(?:uazione)?\.?\s+(?:del\s+)?c\.?\s?p\.?\s?p\.?",)),
    Alias("DISP_ATT_COD_CIV", nir="stato:regio.decreto:1942-03-30;318:1",
          patterns=(r"disp(?:osizioni)?\.?\s+(?:di\s+)?att(?:uazione)?\.?\s+(?:del\s+)?c\.?\s?c\.?",)),

    # — codici militari & processo amministrativo (before the plain codice penale / c.p.) —
    Alias("COD_MIL_PACE", nir="stato:relazione.e.regio.decreto:1941-02-20;303:1",
          patterns=(r"cod(?:ice)?\.?\s+pen(?:ale)?\.?\s+mil(?:itare)?\.?\s+(?:di\s+)?pace|\bc\.?p\.?m\.?p\.?\b",)),
    Alias("COD_MIL_GUERRA", nir="stato:relazione.e.regio.decreto:1941-02-20;303:1",
          patterns=(r"cod(?:ice)?\.?\s+pen(?:ale)?\.?\s+mil(?:itare)?\.?\s+(?:di\s+)?guerra|\bc\.?p\.?m\.?g\.?\b",)),
    Alias("COD_PROCESSO_AMM", nir="stato:decreto.legislativo:2010-07-02;104:2",
          display="codice del processo amministrativo",
          patterns=(r"codice\s+(?:del\s+)?processo\s+amministrativo|cod\.?\s*proc\.?\s*amm\.?|\bc\.?\s?p\.?\s?a\.?\b",)),

    # — codici (procedura before the plain code). "cod.proc.civ." allows no spaces between
    #   segments (the dots separate them), so the attached form parses too. —
    Alias("COD_PROC_CIV", nir="stato:regio.decreto:1940-10-28;1443:1",
          display="codice di procedura civile",
          patterns=(r"codice\s+(?:di\s+)?procedura\s+civile|cod\.?\s*proc\.?\s*civ\.?|\bc\.?\s?p\.?\s?c\.?\b",)),
    Alias("COD_PROC_PEN", nir="stato:decreto.del.presidente.della.repubblica:1988-09-22;447",
          display="codice di procedura penale",
          patterns=(r"codice\s+(?:di\s+)?procedura\s+penale|cod\.?\s*proc\.?\s*pen\.?|\bc\.?\s?p\.?\s?p\.?\b",)),
    # COD_CIV also covers the "preleggi" (disposizioni preliminari al codice civile).
    Alias("COD_CIV", nir="stato:regio.decreto:1942-03-16;262:2", display="codice civile",
          patterns=(r"codice\s+civile|cod\.?\s*civ\.?|\bc\.?\s?c\.?\b(?!\.?\s*n\.?\s*l)",
                    r"\bpreleggi\b")),
    Alias("COD_PEN", nir="stato:regio.decreto:1930-10-19;1398:1", display="codice penale",
          patterns=(r"codice\s+penale|cod\.?\s*pen\.?|\bc\.?\s?p\.?\b",)),
    Alias("COD_STRADA", nir="stato:decreto.legislativo:1992-04-30;285", display="codice della strada",
          patterns=(r"codice\s+della\s+strada|cod\.?\s*strada|\bc\.?\s?d\.?\s?s\.?\b",)),
    Alias("COD_CONSUMO", nir="stato:decreto.legislativo:2005-09-06;206", display="codice del consumo",
          patterns=(r"codice\s+del\s+consumo",)),
    Alias("COD_CONTR_PUBBL", nir="stato:decreto.legislativo:2016-04-18;50",
          display="codice dei contratti pubblici",
          patterns=(r"codice\s+dei\s+contratti\s+pubblici|codice\s+degli\s+appalti",)),
    Alias("COD_AMM_DIGIT", nir="stato:decreto.legislativo:2005-03-07;82",
          patterns=(r"codice\s+dell['’]?\s?amministrazione\s+digitale|\bc\.?\s?a\.?\s?d\.?\b",)),
    Alias("COD_PROT_DATI", nir="stato:decreto.legislativo:2003-06-30;196",
          patterns=(r"codice\s+(?:della\s+privacy|in\s+materia\s+di\s+protezione\s+dei\s+dati)",)),
    Alias("COD_CRISI_IMPRESA", nir="stato:decreto.legislativo:2019-01-12;14",
          patterns=(r"codice\s+della\s+crisi(?:\s+d['’]impresa)?",)),
    Alias("COD_PROPR_INDUSTRIALE", nir="stato:decreto.legislativo:2005-02-10;30",
          patterns=(r"codice\s+della\s+propriet[aà]\s+industriale",)),
    Alias("COD_NAVIG", nir="stato:regio.decreto:1942-03-30;327:1", display="codice della navigazione",
          patterns=(r"codice\s+(?:della\s+)?navigazione|cod\.?\s*nav\.?|\bc\.?\s?nav\.?\b",)),
    Alias("COD_ASSICURAZIONI_PRIV", nir="stato:decreto.legislativo:2005-09-07;209",
          patterns=(r"codice\s+delle\s+assicurazioni(?:\s+private)?",)),
    Alias("COD_BENI_CULT", nir="stato:decreto.legislativo:2004-01-22;42", display="codice dei beni culturali",
          patterns=(r"codice\s+dei\s+beni\s+culturali",)),

    # — legge fallimentare, statuti, ordinamento penitenziario —
    Alias("LEGGE_FALL", nir="stato:regio.decreto:1942-03-16;267:1", display="legge fallimentare",
          patterns=(r"legge\s+fallimentare|\bl\.?\s?fall\.?",)),
    Alias("STATUTO_LAVORATORI", nir="stato:legge:1970-05-20;300", display="Statuto dei lavoratori",
          patterns=(r"statuto\s+dei\s+lavoratori",)),
    # "statuto del contribuente" = legge 212/2000. Matches "del contribuente" / "dei diritti del/dei
    # contribuente/i" / bare "contribuente".
    Alias("STATUTO_CONTRIB", nir="stato:legge:2000-07-27;212", display="Statuto del contribuente",
          patterns=(r"statuto\s+(?:del\s+|dei\s+diritti\s+de[il]\s+)?contribuent[ei]",)),
    # Statuti delle regioni a autonomia speciale, approvati con legge costituzionale.
    Alias("STATUTO_REG_SICILIA", nir="stato:legge.costituzionale:1948-02-26;2",
          display="Statuto della Regione Siciliana",
          patterns=(r"statuto(?:\s+speciale)?\s+(?:della\s+)?regione\s+(?:sicilia|siciliana)\b",)),
    Alias("STATUTO_REG_SARDEGNA", nir="stato:legge.costituzionale:1948-02-26;3",
          display="Statuto speciale della Sardegna",
          patterns=(r"statuto(?:\s+speciale)?\s+(?:della\s+)?regione\s+(?:sardegna|sarda)\b",)),
    Alias("STATUTO_REG_VALLE_AOSTA", nir="stato:legge.costituzionale:1948-02-26;4",
          display="Statuto speciale della Valle d'Aosta",
          patterns=(
              r"statuto(?:\s+speciale)?\s+(?:della\s+)?regione(?:\s+autonoma)?\s+"
              r"valle\s+d['’]\s*aosta\b",
              r"statuto\s+speciale\s+(?:della|per\s+la)\s+valle\s+d['’]\s*aosta\b",
          )),
    Alias("STATUTO_REG_TRENTINO_ALTO_ADIGE",
          nir="stato:legge.costituzionale:1948-02-26;5",
          display="Statuto speciale del Trentino-Alto Adige",
          patterns=(
              r"statuto(?:\s+speciale)?\s+(?:della\s+)?regione(?:\s+autonoma)?\s+"
              r"trentino[\s-]+alto\s+adige\b",
              r"statuto\s+speciale\s+(?:del|per\s+il)\s+trentino[\s-]+alto\s+adige\b",
          )),
    Alias("STATUTO_REG_FRIULI_VENEZIA_GIULIA",
          nir="stato:legge.costituzionale:1963-01-31;1",
          display="Statuto speciale del Friuli-Venezia Giulia",
          patterns=(
              r"statuto(?:\s+speciale)?\s+(?:della\s+)?regione(?:\s+autonoma)?\s+"
              r"friuli[\s-]+venezia\s+giulia\b",
              r"statuto\s+speciale\s+(?:del|per\s+il)\s+friuli[\s-]+venezia\s+giulia\b",
          )),
    Alias("ORDIN_PENIT", nir="stato:legge:1975-07-26;354", display="ordinamento penitenziario",
          patterns=(r"ordinamento\s+penitenziario",)),

    # — testi unici (recognized) —
    Alias("TU_IMPOSTE_REDDITO", nir="presidente.repubblica:decreto:1986-12-22;917", display="TUIR",
          patterns=(r"testo\s+unico\s+(?:delle\s+)?imposte\s+sui\s+redditi"
                    r"|\bt\.?\s?u\.?\s+(?:delle\s+)?imposte\s+sui\s+redditi|\bt\.?u\.?i\.?r\.?\b",)),
    Alias("TU_BANCARIO", nir="stato:decreto.legislativo:1993-09-01;385", display="TUB",
          patterns=(r"testo\s+unico\s+bancario|\bt\.?u\.?b\.?\b",)),
    Alias("TU_FINANZE", nir="stato:decreto.legislativo:1998;58", display="TUF",
          patterns=(r"testo\s+unico\s+(?:della\s+|dell['’]?\s?intermediazione\s+)?finanz(?:a|iaria)"
                    r"|\bt\.?u\.?f\.?\b",)),
    Alias("TU_ENTI_LOCALI", nir="stato:decreto.legislativo:2000-08-18;267", display="TUEL",
          patterns=(r"testo\s+unico\s+(?:degli\s+)?enti\s+locali|\bt\.?u\.?e\.?l\.?\b",)),
    Alias("TU_EDILIZIA", nir="presidente.repubblica:decreto:2001-06-06;380", display="Testo Unico Edilizia",
          patterns=(r"testo\s+unico\s+(?:dell['’]?\s?)?edilizia",)),
    Alias("TU_IMMIGRAZIONE", nir="stato:decreto.legislativo:1998-07-25;286", display="Testo Unico Immigrazione",
          patterns=(r"testo\s+unico\s+(?:sull['’]?\s?)?immigrazione",)),
    Alias("TU_IMPOSTA_REGISTRO", nir="stato:regio.decreto:1986-04-26;131", display="Testo Unico del Registro",
          patterns=(r"testo\s+unico\s+(?:dell['’]?\s?imposta\s+di\s+)?registro"
                    r"|\bt\.?\s?u\.?\s+(?:dell['’]?\s?imposta\s+di\s+)?registro\b|\bt\.?u\.?r\.?\b",)),
    Alias("TU_DOGANALE", nir="presidente.repubblica:decreto:1973-01-23;43", display="TULD",
          patterns=(r"testo\s+unico\s+(?:dell[ae]\s+)?legg[ei]\s+doganal[ei]|\bt\.?u\.?l\.?d\.?\b",)),
    # testo unico successioni e donazioni = d.lgs. 31 ottobre 1990, n. 346
    Alias("TU_SUCCESSIONI", nir="stato:decreto.legislativo:1990-10-31;346",
          display="Testo Unico Successioni",
          patterns=(r"(?:testo\s+unico|\bt\.?\s?u\.?)\s+(?:delle\s+)?successioni(?:\s+e\s+donazioni)?",
                    r"\bt\.?u\.?s\.?\b",
                    r"imposta\s+sull[e'’]\s?successioni\s+e\s+donazioni")),
    Alias("TU_AMBIENTE", nir="stato:decreto.legislativo:2006-04-03;152", display="codice dell'ambiente",
          patterns=(r"testo\s+unico\s+ambiental[ei]|codice\s+dell['’]?\s?ambiente|\bt\.?\s?u\.?\s?a\.?\b",)),
    Alias("TU_ACCISE", nir="stato:decreto.legislativo:1995-10-26;504", display="Testo Unico Accise",
          patterns=(r"testo\s+unico\s+(?:delle\s+)?accise",)),
    Alias("TU_STUPEFACENTI", nir="presidente.repubblica:decreto:1990-10-09;309",
          patterns=(r"testo\s+unico\s+(?:degli\s+)?stupefacenti",)),
    Alias("TU_PUBBL_SICUREZZA", nir="stato:regio.decreto:1931-06-18;773:1",
          patterns=(r"\bt\.?u\.?l\.?p\.?s\.?\b",)),

    # — Costituzione. The proper noun is "Cost." or capitalized "Costituzione"; the lowercase
    #   common noun ("costituzione in giudizio", "...di parte civile", "...di società") is NOT
    #   the Constitution — match only the abbreviation or a capital-C full word. —
    Alias("COST", nir="stato:costituzione:1947-12-27", display="Costituzione",
          patterns=(r"(?-i:Costituzione)|\bcost\.",)),

    # — testi unici / codici present in the alias table but not recognized from free text —
    Alias("COD_COM_ELETTR", nir="stato:decreto.legislativo:2003-08-01;259"),
    Alias("COD_NAUTICA_DIPORTO", nir="stato:decreto.legislativo:2005-07-18;171"),
    Alias("COD_ORDINAM_MIL", nir="stato:decreto.legislativo:2010-03-15;66"),
    Alias("COD_PARI_OPPOR", nir="stato:decreto.legislativo:2006-04-11;198"),
    Alias("COD_PROC_PEN_1930", nir="stato:regio.decreto:1930-10-19;1399",
          display="codice di procedura penale 1930"),
    Alias("TU_ACQUE", nir="stato:regio.decreto:1933-12-11;1775:1"),
    Alias("TU_AVVOCATURA_STATO", nir="stato:regio.decreto:1933-10-30;1612:1"),
    Alias("TU_CASELLARIO_GIUDIZ", nir="presidente.repubblica:decreto:2002-11-14;313"),
    Alias("TU_CIRCOLAZ_EU", nir="presidente.repubblica:decreto:2002-01-18;54"),
    Alias("TU_CORTE_CONTI", nir="stato:regio.decreto:1934-07-12;1214:1"),
    Alias("TU_DEBITO_PUBBL", nir="presidente.repubblica:decreto:2003-12-30;398"),
    Alias("TU_DOCUMENTAZIONE_AMM", nir="presidente.repubblica:decreto:2000-12-28;445"),
    Alias("TU_ELEZIONE", nir="stato:decreto.del.presidente.della.repubblica:1960-05-16;570:1"),
    Alias("TU_ESPROPRIAZIONE_PUBBL", nir="presidente.repubblica:decreto:2001-06-08;327"),
    Alias("TU_IMPIEGATI", nir="presidente.repubblica:decreto:1957-03-30;3"),
    Alias("TU_LEGGI_CONS_STATO", nir="stato:regio.decreto:1924-06-26;1054:1"),
    Alias("TU_LEGGI_SANITARIE", nir="stato:regio.decreto:1934-07-27;1265:1"),
    Alias("TU_ORDINAM_MIL", nir="presidente.repubblica:decreto:2010-03-15;90"),
    Alias("TU_PESCA", nir="stato:regio.decreto:1931-10-08;1604:1"),
    Alias("TU_PUBBL_IMPIEGO", nir="stato:decreto.legislativo:2001-03-30;165"),
    Alias("TU_SEQUESTRO", nir="presidente.repubblica:decreto:1950-01-05;180:1"),
    Alias("TU_SOCIETA_PART_PUBBL", nir="stato:decreto.legislativo:2016-08-19;175"),
    Alias("TU_SPESE_GIUST", nir="presidente.repubblica:decreto:2002-05-30;115"),
    Alias("REG_COD_NAVIG", nir="stato:decreto.del.presidente.della.repubblica:1952-02-15;328:1"),

    # — EU treaties / charters / regulations (scope "eu"; CELEX-backed) —
    Alias("TRATTATO_FUNZ_UE", "eu", celex="CELEX:12012E/TXT",          # TFUE (consolidato 2012)
          patterns=(r"trattato\s+sul\s+funzionamento\s+dell['’]?\s?unione\s+europea|\bt\.?f\.?u\.?e\.?\b",)),
    Alias("TRATTATO_UE", "eu", celex="CELEX:12016ME/TXT",             # TUE (consolidato 2016)
          patterns=(r"trattato\s+sull['’]?\s?unione\s+europea|\bt\.?u\.?e\.?\b",)),
    # trattato CEE (Roma 1957) before CE (Maastricht) so "CEE" is not read as "CE".
    Alias("TRATTATO_CEE", "eu", celex="CELEX:11957E/TXT",             # trattato CEE (Roma 1957)
          patterns=(r"trattato\s+(?:c\.?e\.?e\.?|che\s+istituisce\s+la\s+comunit[aà]\s+economica\s+europea)\b",)),
    Alias("TRATTATO_CE", "eu", celex="CELEX:12002E/TXT",              # trattato CE (Maastricht, cons. 2002)
          patterns=(r"trattato\s+(?:c\.?e\.?|che\s+istituisce\s+la\s+comunit[aà]\s+europea)\b",)),
    Alias("CARTA_DIR_FOND_UE", "eu", celex="CELEX:12012P/TXT",        # Carta dei diritti fondamentali UE
          patterns=(r"carta\s+dei\s+diritti\s+fondamentali|\bc\.?d\.?f\.?u\.?e\.?\b",)),
    Alias("GDPR", "eu", celex="CELEX:32016R0679",                    # reg. (UE) 2016/679
          patterns=(r"\b(?:gdpr|rgpd)\b",)),
    Alias("COD_DOGANALE_COMUN", "eu", celex="CELEX:31992R2913",       # codice doganale comunitario (CEE 2913/92)
          patterns=(r"codice\s+doganale\s+comunitario|\bc\.?d\.?c\.?\b",)),
    Alias("COD_DOGANALE_UNIONE", "eu", celex="CELEX:32013R0952",      # codice doganale dell'Unione (UE 952/2013)
          patterns=(r"codice\s+doganale\s+dell['’]?\s?unione(?:\s+europea)?|\bc\.?d\.?u\.?\b",)),
    # Convenzione di Bruxelles 1968 (giurisdizione ed esecuzione, versione consolidata 1998).
    Alias("CONV_BRUXELLES", "eu", celex="CELEX:41998A0126", display="Convenzione di Bruxelles",
          patterns=(r"convenzione\s+di\s+bruxelles",)),

    # — special: the URN is a literal token coinciding with the alias (no nir/celex) —
    # CEDU (international) and the EU Common Customs Tariff (comunitario; its "voci"/"capitoli"
    # are not URN-able, so the URN is just the alias token).
    Alias("CONV_EU_DIR_UOMO", "intl",
          patterns=(r"convenzione\s+europea\s+dei\s+diritti\s+dell['’]?\s?uomo|\bc\.?e\.?d\.?u\.?\b",)),
    Alias("TARIFFA_DOGANALE_COM", "eu", display="tariffa doganale comune",
          patterns=(r"tariffa\s+doganale\s+comune",)),
]

# aliases that are a complete reference on their own (no cited partition/number required) and
# whose URN is just the alias token.
SELF_VALID_ALIASES = frozenset({
    "STATUTO_CONTRIB",
    "STATUTO_REG_SICILIA",
    "STATUTO_REG_SARDEGNA",
    "STATUTO_REG_VALLE_AOSTA",
    "STATUTO_REG_TRENTINO_ALTO_ADIGE",
    "STATUTO_REG_FRIULI_VENEZIA_GIULIA",
    "TARIFFA_DOGANALE_COM",
})


# ── Derived per-field maps (consumed elsewhere; do not edit — edit ALIASES above) ──
ALIAS_NIR = {a.code: a.nir for a in ALIASES if a.nir}
ALIAS_DISPLAY = {a.code: a.display for a in ALIASES if a.display}
ALIAS_CELEX = {a.code: a.celex for a in ALIASES if a.celex}
EU_ALIASES = frozenset(a.code for a in ALIASES if a.scope == "eu")
INTL_ALIASES = frozenset(a.code for a in ALIASES if a.scope == "intl")
ALIAS_PATTERNS = [(p, a.code) for a in ALIASES for p in a.patterns]

_ALIAS_COMPILED = [(re.compile(p, I), v) for p, v in ALIAS_PATTERNS]

# Bare "CE" as the EC Treaty, only after an article within the treaty's actual range. The upper
# bound blocks common OCR damage where "c.c." becomes "ce" ("art. 2303 ce").
_CE_TRATTATO = re.compile(
    r"\bart(?:icol[oi]|\.)?\s*(\d{1,3})(?!\d)[^.;]{0,45}?[\s,]+(CE)\b", I)


def recognize_aliases(text: str, nonoverlap) -> List[Span]:
    spans = []
    for pat, value in _ALIAS_COMPILED:
        for m in pat.finditer(text):
            spans.append(Span(m.start(), m.end(), Entity.ALIAS, value, m.group(0)))
    for m in _CE_TRATTATO.finditer(text):
        if int(m.group(1)) <= 314:
            spans.append(Span(m.start(2), m.end(2), Entity.ALIAS, "TRATTATO_CE", m.group(2)))
    return nonoverlap(spans)


def alias_nir(alias: str, partition_field: str = "") -> Optional[str]:
    """Build the ``urn:nir`` for a national alias act (+ partition locator). Returns None for
    unknown or EU/international aliases. Date is left full; the URN layer trims it to year."""
    base = ALIAS_NIR.get(alias)
    if not base:
        return None
    urn = "urn:nir:" + base
    loc = partition_to_locator(partition_field)
    if loc:
        urn += "~" + loc
    return urn
