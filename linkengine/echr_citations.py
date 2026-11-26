"""
Corte EDU citations written with the names of the parties.

    Corte EDU, Grande Camera, sentenza 23 febbraio 2017, de Tommaso c. Italia
    Corte europea dei diritti dell'uomo, sentenza 6 novembre 2003, Pantano contro Italia
    sentenze 19 febbraio 1998, Dalia c. Francia; 9 ottobre 2003, Slivenko c. Lettonia
    Zhou contro Italia, 21 gennaio 2014
    Sommer c. Germania, n. 73607/13, par. 48, 27 aprile 2017
    Kafkaris/Cipro [GC]                                   (the EU courts' slash)

The anchor is ``<applicant> <connector> <State>``: a connector (c., c/, contro, v., vs, /)
followed by a state name is rare enough in prose to start from. The applicant is read
leftwards (capitalised words, initials, particles, a parenthetical, a list "A, B e C"), the
date from either side, the court words from the window before. Excluded: CJEU citations
(a C- number, "Corte di giustizia", "Commissione c. ..."), and a state against a state with
no court named ("l'aggressione della Russia contro l'Ucraina").

This module only *finds* the citation and its parts. What it denotes is decided by
``echr.Index.resolve``; ``engine`` turns each result into a feature row.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from .echr import STATE_ALT, fold, parties_field, state_code

I = re.I

# ── pieces ────────────────────────────────────────────────────────────────────
MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "décembre": 12,
    "decembre": 12,
    "gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6, "lug": 7, "ago": 8,
    "set": 9, "sett": 9, "ott": 10, "nov": 11, "dic": 12,
}
MONTH_ALT = "|".join(sorted(map(re.escape, MONTHS), key=len, reverse=True))

_STATE = rf"(?:(?:la\s+|l['’]\s?|lo\s+|the\s+)?(?:{STATE_ALT}))"
# "c.", "contro", "v.", ... and the EU-court slash: "Kafkaris/Cipro"
_CONN = r"(?:(?<![\w])(?:(?-i:c\.|c/|v\.)|contro|vs\.?|versus)|(?<=[\w.\]])\s?/\s?)"
#: "<connector> <State>[ e <State>]"
RESP_RE = re.compile(
    rf"(?P<conn>{_CONN})\s*(?P<resp>{_STATE}(?:\s*(?:,|e|ed|and|et)\s+{_STATE})*)(?![\w])",
    I)

_DATE_NUM = r"\d{1,2}[./]\d{1,2}[./](?:\d{4}|\d{2})(?!\d)"
_DATE_TXT = rf"(?:1\s?[°º]|1\s?o(?=\s+(?:{MONTH_ALT}))|\d{{1,2}})\s*(?:{MONTH_ALT})\.?\s+(?:del\s+)?\d{{4}}"
_DATE_MY = rf"(?:{MONTH_ALT})\s+\d{{4}}"
DATE_RE = re.compile(rf"(?P<d>{_DATE_NUM}|{_DATE_TXT}|{_DATE_MY})", I)
_DATE_PREFIX = (r"(?:(?:(?:resa|emessa|pronunciata|decisa|adottata|depositata)\s+)?"
                r"(?:del|dell['’]|in\s+data(?:\s+del)?|il|del\s+giorno)\s+)?")

CUE_RE = re.compile(
    r"\bcorte\s+(?:europea\s+dei\s+diritti\s+(?:dell['’]?\s?uomo|umani)|e\.?\s?d\.?\s?u\.?|di\s+strasburgo)"
    r"|\bc\.?\s?e\.?\s?d\.?\s?u\.?\b(?!\s*,?\s*art)|\bstrasburgo\b|\bgrande\s+camera\b|\bgrand\s+chamber\b"
    r"|\bcorte\s+e\.?d\.?u\.?\b|\bgiudici\s+di\s+strasburgo\b|\b(?:sentenz|decision)\w*\s+(?:della\s+)?corte\s+europea\b"
    r"|\bcorte\s+europea\b(?!\s+di\s+giustizia)", I)
_CJEU_NEAR = re.compile(
    r"\b[CT]\s?[-‑–]\s?\d{1,4}/\d{2,4}\b|\bcorte\s+di\s+giustizia\b|\bc\.?g\.?u\.?e\.?\b|\bcgce\b"
    r"|\bcorte\s+giust\.|\bconclusioni\s+dell['’]avvocato|\bavvocato\s+generale\b|\bcausa\s+C", I)
# an admissibility decision or a Commission report. "decisione" alone is NOT a signal: Italian
# prose calls a judgment "la decisione 17 settembre 2009 ... nel caso Scoppola".
_DECISION = re.compile(
    r"\((?:dec|déc|dee|dec\.|déc\.)\)|\(dec\.?\)|decision[ei]\s+(?:sulla\s+|di\s+)?(?:ricevibilit|irricevibilit|"
    r"della\s+commissione)|commissione\s+europea\s+dei\s+diritti|\bdec\.\s+comm", I)
_LEAD = re.compile(
    r"(?<![\w])(?:corte\s+europea\s+dei\s+diritti\s+dell['’]?\s?uomo|corte\s+e\.?d\.?u\.?|c\.?e\.?d\.?u\.?)"
    r"(?:\s*,?\s*(?:grande\s+camera|(?:prima|seconda|terza|quarta|quinta)\s+sezione|sezione\s+(?:prima|seconda|terza|quarta|quinta|[ivx]{1,3}|\d)|sez\.\s*[ivx\d]+|GC))?"
    r"(?:\s*,?\s*(?:sentenz[ae]|decision[ei]|sent\.))?(?:\s*,?\s*(?:del(?:l['’])?|in\s+data(?:\s+del)?)\s+)?[\s,]*$", re.I)
_CONNECTOR = re.compile(r"c\.|c/|contro|v\.|vs\.?|versus|/", re.I)
_COMMISSION = re.compile(r"^(?:la\s+)?commission[ei]\b|^cons(?:iglio)?\b|^parlamento\b", I)

# ── scanning the applicant leftwards ─────────────────────────────────────────
_LEAD_PARTICLES = {"de", "van", "von", "der", "den", "ter", "ten", "du", "des", "el", "al",
                   "bin", "ibn", "zur", "zu", "dos", "das", "do", "d'", "l'", "mac"}
_INNER = {"e", "ed", "and", "et", "&", "di", "del", "della", "dei", "degli", "delle", "da",
          "dal", "dalla", "la", "le", "lo", "il", "i", "gli", "of", "the", "für", "und", "y",
          "de", "van", "von", "der", "den", "ter", "ten", "du", "des", "el", "al", "bin", "ibn",
          "zur", "zu", "dos", "das", "do", "ve", "sul", "sulla", "in", "su", "per", "con",
          "altri", "altre", "altro", "others", "autres", "ed altri", "ed altre", "al."}
_AND_OTHERS = {"altri", "altre", "altro", "others", "autres", "al.", "a."}
_BLOCK = {"affaire", "case", "arret", "arrêt", "edu", "cedu", "corte", "camera", "chambre", "sezione", "sez", "sez.", "strasburgo",
          "gc", "[gc]", "(gc)", "caso", "causa", "sentenza", "sentenze", "sent.", "decisione",
          "decisioni", "ordinanza", "pronuncia", "pronunce", "vedi", "cfr", "cfr.", "cit",
          "cit.", "convenzione", "tribunale", "ricorso", "ric.", "appl.", "n.", "nn.", "n°",
          "ad", "anche", "cioè", "ovvero", "ed.", "pag.", "par.", "paragrafo", "paragrafi",
          "§", "pp.", "p.", "ibidem", "ibid.", "supra", "infra", "europea", "uomo", "diritti"}
_STARTERS = {"secondo", "come", "vedi", "cfr", "nel", "nella", "nei", "nelle", "con", "per",
             "anche", "ancora", "infine", "inoltre", "così", "si", "ex", "dalla", "dal", "sulla",
             "sul", "caso", "causa", "v.", "cit.", "quindi", "dunque", "ove", "ossia", "oltre",
             "ricordata", "citata", "richiamata", "tra", "fra"}
_TOKEN = re.compile(r"\S+")


def _is_name_token(tok: str) -> bool:
    core = tok.strip("“”\"«»‘’'.,;:()[]")
    return bool(core) and (core[0].isupper() or bool(re.match(r"\d{1,2}[^\W\d_]", core)))


def scan_applicant(text: str, conn_start: int, limit: int = 220):
    """The applicant block that ends right before the connector: (start, end) or None."""
    lo = max(0, conn_start - limit)
    toks = [(lo + m.start(), lo + m.end(), m.group()) for m in _TOKEN.finditer(text[lo:conn_start])]
    kept = []
    i = len(toks) - 1
    while i >= 0 and len(kept) < 14:
        s, e, tok = toks[i]
        low = tok.lower().strip("“”\"«»‘’'.,;:()[]")
        bare = tok.strip("“”\"«»‘’'()[]")
        # a token that closes a previous phrase ends the name, unless it is a single initial
        if not bare:
            break                        # a lone bracket or quote
        # a parenthetical inside the name: "Othman (Abu Qatada)", "Gebremedhin [Gaberamadhien]"
        if tok[-1] in ")]" and len(bare) > 2:
            opener = "(" if tok[-1] == ")" else "["
            for back in range(i, max(-1, i - 7), -1):
                if opener in toks[back][2]:
                    for j in range(i, back - 1, -1):
                        kept.append(toks[j])
                    i = back - 1
                    break
            else:
                break
            continue
        # a small number inside a name: "Centro Europa 7 S.r.l."
        if (tok.isdigit() and len(tok) <= 2 and kept and i > 0
                and _is_name_token(toks[i - 1][2]) and toks[i - 1][2][-1] not in ",;:."
                and toks[i - 1][2].lower() not in _BLOCK):
            kept.append((s, e, tok))
            i -= 1
            continue
        if kept and tok[-1] in ";:)]" and not (len(bare.rstrip(",.")) <= 2 and bare[0].isupper()):
            break
        if tok[-1] == ",":
            # a comma ends the name, except inside a list of applicants that ends with
            # "e"/"and" ("A, B e C", "Abdulaziz, Cabales e Balkandali")
            in_list = any(t.lower().strip(",") in {"e", "ed", "and", "et", "&"} for _, _, t in kept) \
                and _is_name_token(tok) and low not in _BLOCK
            if not (in_list or (kept and re.fullmatch(r"[A-Z]\.?,", bare))):
                break
        # "Grande Camera" is the bench, "Grande Stevens" a name
        nxt = toks[i + 1][2].lower().strip(",.;:()[]") if i + 1 < len(toks) else ""
        if low == "grande" and nxt not in ("camera", "chambre"):
            kept.append((s, e, tok))
            i -= 1
            continue
        if low in _BLOCK or (state_code(low) and not kept):
            break
        if kept and state_code(low) and i > 0 and _CONNECTOR.fullmatch(toks[i - 1][2].strip(",")):
            break                        # the previous party's respondent: "contro Austria e Löffelmann"
        if tok == "a." and i > 0 and toks[i - 1][2].lower() == "e":
            kept.append((s, e, tok))               # "Grande Stevens e a. c. Italia"
            i -= 1
            continue
        if _is_name_token(tok) or low in _INNER:
            kept.append((s, e, tok))
            if tok[0] in "([“«\"" and _is_name_token(tok):
                break                    # an opening bracket ends the name
            i -= 1
            continue
        break
    kept.reverse()
    # trim what is not part of a name on the left: connectors, article-like particles,
    # sentence starters ("Secondo Pantano c. Italia")
    while kept:
        raw0 = kept[0][2].strip("“”\"«»‘’'.,;:()[]")
        low = raw0.lower()
        if low in _STARTERS or (low in _INNER and low not in _LEAD_PARTICLES and raw0[:1].islower()) \
                or low in _BLOCK:
            kept.pop(0)
        else:
            break
    while kept and kept[-1][2].lower().strip(",;") in _INNER and \
            kept[-1][2].lower().strip(",;") not in _AND_OTHERS:
        kept.pop()
    if not kept or not any(c.isalpha() for _, _, t in kept for c in t):
        return None
    return kept[0][0], kept[-1][1]


# ── the citation record ──────────────────────────────────────────────────────
@dataclass
class EchrCitation:
    """One Strasbourg citation written with the names of the parties."""
    start: int
    end: int
    surface: str
    applicant: str
    respondents: List[str]
    ordinal: int = 0
    date: str = ""                   # YYYY-MM-DD, YYYY-MM or YYYY
    appnos: List[str] = field(default_factory=list)
    cue: str = ""                    # court named: near | far | ""
    chamber: str = ""                # GC | SEC | ""
    decision: bool = False           # said to be an admissibility decision / Commission report
    confidence: str = ""             # strong | medium | weak
    parties: str = ""                # the lookup key, "de-tommaso:ITA"


def parse_date(raw: str) -> str:
    """'23 febbraio 2017' -> '2017-02-23'; 'marzo 2006' -> '2006-03'; '' when it is not a date."""
    raw = raw.strip()
    m = re.fullmatch(r"(\d{1,2})[./](\d{1,2})[./](\d{4}|\d{2})", raw)
    if m:
        d, mo, y = int(m[1]), int(m[2]), int(m[3])
        if y < 100:                       # Strasbourg starts in 1959: 60-99 -> 19xx, 00-26 -> 20xx
            y = 1900 + y if y >= 60 else (2000 + y if y <= 26 else 0)
            if not y:
                return ""
        return f"{y:04d}-{mo:02d}-{d:02d}" if 1 <= mo <= 12 and 1 <= d <= 31 else ""
    m = re.fullmatch(rf"(?:(1\s?[°ºo]|\d{{1,2}})\s*)?({MONTH_ALT})\.?\s+(?:del\s+)?(\d{{4}})", raw, I)
    if m:
        mo = MONTHS[fold(m[2]).replace(".", "")] if fold(m[2]) in MONTHS else MONTHS.get(m[2].lower())
        y = int(m[3])
        if m[1]:
            return f"{y:04d}-{mo:02d}-{int(re.sub(r'[^0-9]', '', m[1])):02d}"
        return f"{y:04d}-{mo:02d}"
    return ""


_ORDINAL_AFTER = re.compile(
    r"^\s*,?\s*(?:\(\s*(?:n\.?|n°|nº|no\.?|nr\.?|nn\.)\s*([1-9]\d?)\s*\)"
    r"|(?:n\.?|n°|nº|no\.?|nr\.?)\s*([1-9])(?![\d/]|\.\d|\s*[,)]?\s*(?:par|§|p\.)))", I)
_APPNO = r"\d{1,5}\s*/\s*\d{2}(?!\d)"
_APPNO_DEL = re.compile(r"(?:ricors[oi]|ric\.|appl\.?)\s*(?:nn?\.|n°|nº)?\s*(\d{1,5})\s+del\s+(\d{4})", I)
_APP_WORD = r"(?:ricors[oi]|ric\.|appl\.?|application|requ[êe]te|domanda|istanza|r\.\s?g\.)"
_APPNO_AFTER = re.compile(
    rf"^\s*(?:\[\s*GC\s*\]\s*)?,?\s*(?:\(\s*d[ée][ce]?\.?\s*\)\s*,?\s*)?(?:\(?\s*{_APP_WORD}\s*)?(?:nn?\.|n°|nº|no\.)?\s*"
    rf"(?P<n>{_APPNO}(?:\s*(?:,|e|ed|and|;)\s*{_APPNO})*)", I)
_APPNO_BEFORE = re.compile(
    rf"{_APP_WORD}\s*(?:nn?\.|n°|nº|no\.)?\s*(?P<n>{_APPNO}(?:\s*(?:,|e|ed)\s*{_APPNO})*)\s*[,;:]?\s*(?:cause?\s+)?\)?\s*[,;:]?\s*$", I)


def find_citations(text: str) -> List[EchrCitation]:
    """Every citation of the shape ``<party> c. <State>`` in ``text``, with the date, ordinal,
    application number and court words around it."""
    out: List[EchrCitation] = []
    last_end = -1
    for m in RESP_RE.finditer(text):
        if m.start() < last_end:
            continue
        scan = scan_applicant(text, m.start())
        if not scan:
            continue
        a_start, a_end = scan
        applicant = text[a_start:a_end].strip()
        resp_codes = []
        for part in re.split(r"\s*(?:,|\be\b|\bed\b|\band\b|\bet\b)\s*", m["resp"], flags=I):
            code = state_code(part)
            if code and code not in resp_codes:
                resp_codes.append(code)
        if not resp_codes:
            continue
        pre = text[max(0, a_start - 260, last_end):a_start]
        end = m.end()

        # ordinal "(n. 2)" and application numbers right after the state
        ordinal = 0
        om = _ORDINAL_AFTER.match(text[end:end + 25])
        if om:
            ordinal = int(om[1] or om[2])
            end += om.end()
        appnos: List[str] = []
        am = _APPNO_AFTER.match(text[end:end + 90])
        if am:
            appnos = [re.sub(r"\s", "", a) for a in re.findall(_APPNO, am["n"])]
            end += am.end()
        bm = _APPNO_BEFORE.search(pre)
        if bm and not appnos:
            appnos = [re.sub(r"\s", "", a) for a in re.findall(_APPNO, bm["n"])]
        if not appnos:                                   # "ricorso n. 20153 del 2004"
            for dm_ in _APPNO_DEL.finditer(pre[-90:] + " " + text[end:end + 40]):
                appnos.append(f"{int(dm_[1])}/{dm_[2][2:]}")

        # date: immediately before the name (nearest first), else after the state
        date = ""
        start = a_start
        pre_win = pre[-130:]
        best = None
        for dm in DATE_RE.finditer(pre_win):
            best = dm
        if best:
            between = pre_win[best.end():]
            # an application number between the date and the name does not separate them
            between = re.sub(rf"\(?\s*{_APP_WORD}\s*(?:nn?\.|n°|nº|no\.)?\s*{_APPNO}(?:\s*(?:,|e|ed)\s*{_APPNO})*\s*[,;]?\s*",
                             " ", between, flags=I)
            if (len(between) <= 95 and not re.search(r"[;()\[\]]|\d{2,}", between)
                    and not re.match(r"\s*(?:e|ed|nonch[eé]|ovvero|oltre)\s", between, I)
                    and not RESP_RE.search(between)
                    and not re.search(r"\b(?:che|nonché|mentre|poiché|perché)\b", between, I)):
                date = parse_date(best["d"])
                start = a_start - (len(pre_win) - best.start())
        if not date:
            dm = re.match(rf"^\s*[,(]?\s*{_DATE_PREFIX}{DATE_RE.pattern}", text[end:end + 60], I)
            if dm:
                tail = text[end + dm.end():end + dm.end() + 110]
                next_party = RESP_RE.search(tail)
                # "Xc. Italia del 20 aprile 2010, Y c. ..." the date is attached by "del": it is
                # X's. After a bare comma it may as well be the left date of the next party.
                attached = (not text[end:end + dm.end()].lstrip().startswith(",") and
                            not text[end:end + dm.end()].lstrip().startswith("(,")) or \
                    bool(re.match(r"\s*(?:e|ed|nonch[eé]|ovvero)\s", tail, I))
                if attached or not (next_party and not re.search(r"[.;)]", tail[:next_party.start()])):
                    date = parse_date(dm["d"])
                    end += dm.end()
                    if text[end:end + 1] == ")":
                        end += 1
        if not date:
            ym = re.match(r"^\s*(?:\[GC\]\s*|\(GC\)\s*)?,\s*((?:19[5-9]|20[0-2])\d)\s*(?=[,;)]|\s*$|\s+(?:par|§|p\.))", text[end:end + 30])
            if ym:
                date = ym.group(1)
                end += ym.end(1)
        # cue words before the party / date window
        win = text[max(0, start - 150):start]
        far = text[max(0, start - 600):start]
        cue = "near" if CUE_RE.search(win) else ("far" if CUE_RE.search(far) else "")
        chamber = "GC" if re.search(r"grande\s+camera|\bGC\b|grand\s+chamber", win + text[end:end + 8], I) else (
            "SEC" if re.search(r"\bsez(?:ione|\.)|\b(?:prima|seconda|terza|quarta|quinta)\s+sezione", win, I) else "")
        decision = bool(_DECISION.search(text[max(0, start - 60):start] + text[start:end + 40]))
        cjeu = bool(_CJEU_NEAR.search(text[max(0, start - 70):end + 70])) or bool(
            _COMMISSION.match(fold(applicant)))
        if cjeu:
            last_end = end
            continue
        # a state against a state is the war, not Strasbourg, unless the court is named
        if state_code(applicant) and not cue:
            continue
        # the court words that lead straight into it belong to the citation
        lead = _LEAD.search(text[max(0, start - 140):start])
        if lead:
            start = max(0, start - 140) + lead.start()
            cue = "near"
        parties = parties_field(applicant, resp_codes, ordinal)
        if not parties:
            continue
        strong = bool(cue == "near" and (date or appnos)) or bool(date and appnos)
        conf = "strong" if strong else ("medium" if cue or date or appnos else "weak")
        out.append(EchrCitation(start, end, text[start:end], applicant, resp_codes, ordinal, date,
                                appnos, cue, chamber, decision, conf, parties))
        last_end = end
    return out
