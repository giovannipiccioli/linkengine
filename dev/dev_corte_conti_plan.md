# Corte dei conti — recognition and ECLI normalization

**Implemented.** This is the plan the change was built from, kept for the evidence in §1, §4
and §5. What shipped differs from it in four places:

- **Every geographic component is the standard `geo.py` code** — the three-letter region
  code, or the province targa for a section that sits in a seat. So `SRCEMR` not the
  archive's `SRCERO`, `SGTN`/`SGBZ`/`SRCTN`/`SRCBZ` not `SGTAT`/`SGTAB`/`SRCTAA`/`SCBOLZ`,
  and `SSRRCOTAA`/`SSRRCOSAR`/`SSRRCOSIC`/`CONSSIC` not `SSRRTN`/`SSRRSA`/`SSRRSC`/`SSRRSP`.
  These identifiers are therefore ours, not the portal's; the payoff is that knowing a
  region means knowing its section code. Single override point:
  `catalog._corte_conti_regional` and the explicit block under it.
- **`decisione` joined `deliberazione`/`parere`** as a doc-type the Corte dei conti may
  pair with: "decisione n. 7/2007/QM delle Sezioni Riunite" is a pronouncement, not an EU act.
- **A bare ordinal must qualify a "sezione"** to name an appeal section, or "Corte dei conti
  3 marzo 2020" and "Corte dei conti, i giudici …" each invent one (`gold_precision` CC6).
- **`SGSEZ`, `SSRR` and `DEL`-as-a-section stayed out**, as planned.

Measured after the change, over the same 144-document sample: 983 Corte dei conti references
recognized, 661 (67%) resolved to a full identifier, and **460 of 463 exact (99.4%)** on the
section-years the archive covers densely. The unresolved remainder is dominated by controllo
citations that genuinely omit the deliberation type (246) and by citations that name no
section at all (76, mostly self-references that `DocumentContext.cc_section` resolves).

Thirteen whole decisions are annotated in `tests/gold/gold_corte_conti_docs.jsonl` —
every citation of the Court in each, read by hand and checked against the archive. Current
score: **precision 0.980, recall 0.875** over 56 citations. The seven misses are four
documents whose own number sits too far from the section that decided it, one list whose
items are expanded from the first item's court, one bench named only as "la locale Sezione
territoriale", and one unqualified "Sezioni riunite".

One known wrong output, recorded in `tests/gold/full_document_spans.jsonl`: the second item
of a number list inherits the first item's court instead of the one that follows it
("ordinanze n. 5 … della Sezione Terza centrale e n. 25 … della Sezione Prima centrale").
That is a general segmentation limitation — it reproduces identically with C.T.R. and
Tribunale, before and after this change — not a Corte dei conti one.

Evidence base: the 207 785-row scraped archive in
`data/raw/corte_conti/<year>/corte_conti_<year>.csv` (36 years, 1991–2026), plus 144 PDFs
sampled from 2012 / 2018 / 2023 / 2025 across every section family and converted to text
(~5.4 M characters). Prototype and measurement scripts live in the session scratchpad
(`proto.py`, `harness3.py`, `census.py`, `selftest.py`); they are throwaway.

---

## 1. What the identifier has to look like

The archive filenames come from the portal's own `Content-Disposition` header
(`filename_from_response` in `scrape_corte_conti.ipynb`), so they are the Corte dei conti's
official ECLIs, not a local construction. Shape:

```
ECLI:IT:CONT:<year>:<number><SECTION>              giurisdizionale
ECLI:IT:CONT:<year>:<number><SECTION>-<TYPE>       controllo
```

| example file | ECLI | reading |
|---|---|---|
| `ECLI_IT_CONT_2023_89SGCAL.pdf` | `ECLI:IT:CONT:2023:89SGCAL` | sentenza, Sez. giurisdizionale Calabria |
| `ECLI_IT_CONT_2023_525APP3.pdf` | `ECLI:IT:CONT:2023:525APP3` | Terza Sezione centrale d'appello |
| `ECLI_IT_CONT_2023_11SSR.pdf` | `ECLI:IT:CONT:2023:11SSR` | Sezioni riunite in sede giurisdizionale |
| `ECLI_IT_CONT_2023_102SRCPIE-PAR.pdf` | `ECLI:IT:CONT:2023:102SRCPIE-PAR` | deliberazione, Sez. controllo Piemonte, parere |
| `ECLI_IT_CONT_2023_5SEZAUT-INPR.pdf` | `ECLI:IT:CONT:2023:5SEZAUT-INPR` | Sezione delle Autonomie, programma di controllo |

Three consequences that drive the whole design:

1. **The court code is `CONT`, not `CCONTI`.** Today `catalog.COURTS["CORTE_CONTI"]["ecli"]`
   is `"CCONTI"`, which no Corte dei conti document carries. This is a breaking change to
   four gold files (below).
2. **The section is a suffix on the number**, exactly like the Cassazione's `CIV`/`PEN`
   (`urn._cass_chamber_suffix`). It is *not* an ECLI geo component, so
   `COURTS["CORTE_CONTI"]["geo"]` stays `None` and `_court_ecli`'s geo machinery is untouched.
3. **Sentenze and ordinanze share one number series per section** — the giurisdizionale ECLI
   carries no doc-type marker (`MARCHE/SENTENZA/9/2023` and the ordinanze rows in the archive
   both land in the same series). The controllo suffix (`-PAR`, `-PRSE`, …) is a *procedural
   type*, not a doc-type: every controllo document is a `deliberazione`.

Rubrics that decorate a giurisdizionale citation — `n. 7/2007/QM`, `n. 11/2023/RGC`,
`n. 653/2013-A`, `SENT. N. 67/2023/M` — are **not** in the ECLI and must be dropped. The
controllo type in the same slash position **must** be kept. The section family decides which.

---

## 2. Where the library stands today (measured)

```
Corte dei conti, Sez. III App., n. 172/2022            -> ECLI:IT:CCONTI:2022:172   (section field '3')
Corte dei conti, Sez. Giur. Abruzzo, sentenza n. 91/2020 -> ECLI:IT:CCONTI:2020:91  (no section)
Sezione Prima Centrale sent. n. 151/2021               -> no reference
Corte dei conti, Sez. contr. Lombardia, delib. n. 60/2021 -> ref-type=legislation, no urn
deliberazione n. 102/2023/SRCPIE/PAR                   -> ref-type=legislation, no urn
SS.RR. n. 1/QM/2021                                    -> nothing
```

So: only the bare `Corte dei conti n. N/AAAA` form resolves, to a court code that does not
exist, with no section. Everything with a section name and the whole controllo channel are
unrecognized. The `delib.` failure has a specific cause worth naming: `DEL` is not in
`assembler.CASELAW_DOCTYPE`, so a `deliberazione` anchor seeds an *act* frame and the
`CORTE_CONTI` authority span is refused entry (`assembler.py:314-316`).

---

## 3. The change, file by file

Five edits, each in the module the README already assigns the responsibility to. No new
module, no schema change: the ECLI component rides in the existing `section` feature field,
which is already free-form (`'3'`, `'trib'`, `'5CIV'`).

### 3.1 `catalog.py` — the knowledge base

* `COURTS["CORTE_CONTI"]["ecli"]`: `"CCONTI"` → `"CONT"`.
* Add `CORTE_CONTI_SECTIONS`: the code → display-name table of §4. One dict, ~50 entries,
  the single source of truth for both `urn.build_urn` and `urn.urn_to_text` — the same shape
  `COURTS` already has.
* Add `"DEL"` and `"PARERE"` to the doc-types a court may issue. `COURT_DOCTYPES` is
  currently declared and unused; either wire it up or delete it, but the live gate is
  `assembler.CASELAW_DOCTYPE`.

### 3.2 `recognizers.py` — `_corte_conti_resolve(text, pos)`

Modeled on `_cgt_resolve`, which already does exactly this job for the CGT (parse what
follows the court keyword, return the authority plus the ECLI-bearing attributes and the new
end offset). Returns `(section_code, end)`; attaches as `attrs["section"]`.

It also has to fire when the section phrase appears **without** the court keyword — half of
real citations name only `Sezione Prima Centrale`, `Sez. contr. Lombardia`, `SS.RR.`,
`Sez. Autonomie`. Those phrases are unambiguous, so they enter `_COURT_PATTERNS` as their own
`CORTE_CONTI` entries with `want="corteconti"`, the way `sezioni unite`/`SS.UU.` already
enter as `CORTE_CASS`. Recognition order matters: `sezioni riunite` must be tried before the
generic `\bsez` fallbacks, and after `sezioni unite`.

Resolution order inside `_corte_conti_resolve` (first match wins):

| # | trigger | code |
|---|---|---|
| 1 | `sezioni riunite` / `SS.RR.` + `in sede di controllo` | `SSRRCO` |
| 1 | …+ `consultiva` / `deliberante` | `CONS` / `DEL` |
| 1 | …+ `per la regione siciliana` / `Trentino` / `Sardegna` | `SSRRSC` / `SSRRTN` / `SSRRSA` |
| 1 | …otherwise, doc-type `sentenza`/`decisione`/`ordinanza` | `SSR` |
| 1 | …otherwise, doc-type `deliberazione`/`parere`/`pronuncia` | `SSRRCO` |
| 2 | `sezione delle autonomie` / `sez. autonomie` | `SEZAUT` |
| 3 | `sez. (centrale) di controllo sulla gestione` | `SCCGAS` |
| 3 | `sez. (centrale) di controllo di legittimità` | `SCCLEG` |
| 3 | `sez. del controllo sugli enti` | `SCE` |
| 3 | `collegio del controllo concomitante` | `CCC` |
| 3 | `sez. controllo affari europei/comunitari e internazionali` | `SCAEI` (`SACEI` before 2023) |
| 4 | `sez. (regionale) (di) controllo (per la) <REGIONE>` | `SRC<REG>` |
| 5 | ordinal + `sez. … appello` / `sez. … centrale` (`Sez. III App.`, `Prima Sezione Centrale`, `Sez. I centrale`, `III Sez.`) | `APP1/2/3` |
| 5 | …+ `Sicilia` (`Sez. App. Sicilia`, `Sez. giurisdizionale d'appello per la Regione Siciliana`) | `APPSIC` |
| 6 | `sez. (giurisdizionale) (per la regione) <REGIONE>` | `SG<REG>` |
| 7 | bare ordinal `Sez. III` in a `Corte dei conti` frame | `APP1/2/3` |

Two special cases, both real and both cheap:

* **Trentino-Alto Adige splits by seat**, and differently on the two sides: giurisdizionale
  `SGTAT` (Trento) / `SGTAB` (Bolzano); controllo `SRCTAA` (Trento) / `SCBOLZ` (Bolzano).
  Read `Trento`/`Bolzano`/`Bozen` in the trailing 60 chars, default Trento.
* **Emilia-Romagna is `SGEMR` giurisdizionale but `SRCERO` controllo.** The other 19 regions
  reuse `geo.REGION_CODE_TO_NAME` unchanged, so the two tables are `{"EMR": "SRCERO", …}`
  overrides on top of a `"SRC"+code` / `"SG"+code` default — not two hand-written lists.

### 3.3 `recognizers.py` — the deliberation slash chain

Controllo deliberations are cited as a slash chain whose **token order is not stable**. All
of these are real, from the sample:

```
n. 102/2023/SRCPIE/PAR      n. 332/2012/SRCPIE/PRSE     Lombardia/187/2012/PAR
n. 9/SEZAUT/2009/INPR       n. 10/AUT/2012/INPR         n. 3/2014/SEZAUT
n. 130/PRSE/2012            n. 35/PRSE/2011             n. 23/SSRRCO/PARI/23
n. 12/SSRRCO/AUD/18         n. 16/SSRRCO/QMIG/2022      SCCLEG/2/2023/PREV
```

So do not write one regex per shape. Split on `/` and **classify each token independently**:

* `19xx`/`20xx` → year; a bare 2-digit token where the year slot is still empty → year;
* a token in the section table (or `AUT` → `SEZAUT`) → section;
* a token in the type table → type;
* a region name → controllo section (`Lombardia` → `SRCLOM`);
* the first remaining ≤4-digit integer → number;
* a giurisdizionale rubric (`QM`, `RGC`, `EL`, `RIS`, `DELC`, `A`, `M`) → discard.

This is ~25 lines and covers every observed ordering. It belongs next to the existing
tax-court `NNN/SEZ/YYYY` recognizer (`recognizers.py:357-374`), which already parses a
three-part slash form into `{number, year, section}` — same idea, larger alphabet.

One genuine ambiguity to encode: **`SSR`, `CONS` and `DEL` are both section codes and type
codes** (`ECLI:IT:CONT:2012:13SRCSAR-SSR` — `SSR` there is the *type*). Resolve by slot: if
the chain already carries a controllo section, the ambiguous token is the type.

### 3.4 `assembler.py` — let a deliberazione be a pronouncement

`CASELAW_DOCTYPE = {"SENT", "ORD"}` → admit `DEL` and `PARERE` **when a Corte dei conti
authority or section is in the frame**, mirroring the existing `LOCAL_AUTH_DOCTYPE =
{"COMUNE": {"DEL"}}` pairing. A bare `delibera n. 60/2021` must stay a local act; only the
Corte dei conti pairing flips it. Without this the whole controllo channel — 43 % of the
archive — cannot assemble.

### 3.5 `urn.py` — build and render

* `_court_ecli`: where the Cassazione appends `_cass_chamber_suffix(row)`, Corte dei conti
  appends `row["section"]` when it is a known section code. Same line, same mechanism.
* Return `None` (unresolved) when a controllo section has no type code — an
  `ECLI:IT:CONT:2010:15SEZAUT` without `-INPR` is not a real identifier and would resolve to
  nothing. This follows the library's existing rule: leave the incomplete reference
  unresolved rather than emit a wrong one.
* `_ecli_to_text`: split the number on the section code and render
  `ECLI:IT:CONT:2023:102SRCPIE-PAR` → *"Corte dei conti, Sezione regionale di controllo per
  il Piemonte, deliberazione n. 102/2023"*, from the §4 table.

### 3.6 `context.py` — self-references

22 % of the Corte dei conti citations in the sample name no section because they are
self-references: `questa Sezione n. 527/2009`, `questa stessa Sezione (v. sent. n. 180/2012)`,
`questa Sezione Giurisdizionale n. 306/2021`. `THIS_COURT` already resolves these against
`DocumentContext`; it just has nowhere to read a Corte dei conti section from. Add one
validated field — `DocumentContext(authority="CORTE_CONTI", cc_section="SGCAL")`, validated
against the §4 table like `city`/`region` are — and the existing mechanism does the rest.
This is the single highest-yield item after the section resolver.

---

## 4. The tables (from the archive, not from prose)

**Giurisdizionale** — `SG` + the `geo.py` region code, so the 21 regional codes are
generated, not listed. Exceptions and non-regional codes:

| code | docs | years | section |
|---|---|---|---|
| `APP1` / `APP2` / `APP3` | 4 812 / 11 213 / 13 189 | 2000–2026 | Prima / Seconda / Terza Sezione centrale d'appello |
| `APPSIC` | 3 615 | 2010–2026 | Sezione d'appello per la Regione Siciliana |
| `SSR` | 469 | 2010–2026 | Sezioni riunite in sede giurisdizionale |
| `SGTAT` / `SGTAB` | 624 / 1 196 | 2003–2026 | Trentino-Alto Adige, sede di Trento / Bolzano |

**Controllo** — `SRC` + region code, with `EMR→SRCERO` and Bolzano `→SCBOLZ`. Non-regional:

| code | docs | years | section |
|---|---|---|---|
| `SCE` | 2 407 | 2008–2026 | Sezione del controllo sugli enti |
| `SCCGAS` | 797 | 2008–2026 | Sezione centrale di controllo sulla gestione delle amministrazioni dello Stato |
| `SSRRCO` | 626 | 1998–2026 | Sezioni riunite in sede di controllo |
| `SEZAUT` | 548 | 2009–2026 | Sezione delle Autonomie |
| `SCCLEG` | 319 | 2009–2026 | Sezione centrale di controllo di legittimità |
| `SACEI` → `SCAEI` | 253 / 33 | 2011–2023 / 2023–2026 | Sezione di controllo affari europei e internazionali (renamed) |
| `CCC` | 212 | 2022–2026 | Collegio del controllo concomitante |
| `SSRRSP` / `SSRRSC` / `SSRRTN` / `SSRRSA` / `CONS` / `DEL` | 284 / 90 / 72 / 30 / 88 / 32 | — | Sezioni riunite, regional and consultive seats |

**Type codes** — 48 distinct, 39 with ≥20 uses. The head covers almost everything:
`PRSE` 25 168 · `PRSP` 13 007 · `PAR` 10 970 · `VSG` 6 081 · `FRG` 3 897 · `PRNO` 3 604 ·
`REG` 2 377 · `RGES` 2 263 · `VSGO` 2 060 · `PASP` 1 765 · `CSE` 1 744 · `INPR` 1 487 ·
`GEST` 1 427 · `PRSS` 1 389 · `PREV` 1 202 · `VSGC` 1 014 · `PARI` 987 · `VSGF` 798 ·
`SUCC` · `RQ` · `QMIG` · `CCR` · `DEL` · `OICERT` · `CCN` · `PNRR` · `SSR` · `AUD` · `DORG` ·
`CONS` · `IADC` · `DASS` · `COMP` · `RSUE` · `REF` · `PRS` · `FUEFC` · `AFC` · `CEPAR`.
Take the whole list — it is a flat set, and an unknown token simply fails to classify.

---

## 5. What this will and will not get

Measured on the sampled corpus (600 Corte dei conti citations found by the prototype):

| | share |
|---|---|
| giurisdizionale — full ECLI reachable | 47 % |
| controllo — full ECLI reachable (type present in the citation) | 28 % |
| controllo — type code absent, left unresolved | 2 % |
| section unnamed (self-reference `questa Sezione`, …) | 22 % → resolved by §3.6 |

Prototype accuracy, scored against the archive and restricted to the section-years the
archive covers densely (≥85 % of the number range present, so absence is evidence):
**24/24 exact**. On the full unrestricted set the archive-hit rate is 87 %, but every
inspected miss was an archive gap, not a wrong identifier — the local archive is a *sample*
for older years (Sez. Lombardia 2005: 81 of 816 decisions; Sez. Autonomie: ~27 %). This is
why the gate below must be a hand-checked gold set, not an archive lookup.

### Deliberately out of scope

* **`SGSEZ`** (10 328 docs, 1991–2020) — a generic archive code standing in for every
  regional giurisdizionale section, used for ~10 % of pre-2021 decisions and never for any
  after. Nothing in a citation produces it; the named `SG<REG>` code is the right output and
  a fraction of old archive rows simply file it differently.
* **`SSRR`** (48 docs, 2013–2020) — an archive inconsistency, the same "Sezioni riunite" as
  `SSR`, with 6 same-year/same-number collisions in 36 years. Always emit `SSR`.
* **Recovering a missing controllo type code.** `Sezione controllo Lombardia n. 78/2015`
  cannot yield one. Leave unresolved (~2 % of citations).
* **Legacy deliberation type codes** such as `n. 11/CONTR/12`.
* **`SCCS` / `UCCS`** (3 and 2 documents). Add them to the table since it costs a line each,
  but no recognition patterns.

---

## 6. Tests

The existing gold-set machinery carries this; no new harness.

* `tests/gold/gold_manual.csv` — replace the two `CCONTI` rows and add ~25 citations, one per
  recognition rule in §3.2, drawn from the sampled documents with their archive ECLI as gold.
* `tests/gold/gold_fields.jsonl` — the one `CCONTI` row plus ~10 new ones pinning the field
  split (`authority` / `section` / `doc-type` / `number` / `year`), including the cases where
  `section` and `doc-type` disagree with the naive reading: `n. 7/2007/QM` → `SSR` with the
  rubric dropped, `n. 13/2012/SSR` → `SRCSAR-SSR` with `SSR` as the type.
* `tests/gold/gold_precision.csv` — the false-positive risks: `delibera n. 60/2021` of a
  comune must stay a local act; `L. n. 228 del 2012` next to `sezioni riunite` must stay a
  legge; `Sez. III` in a Cassazione document must stay Cassazione.
* `tests/test_full_documents.py` and `tests/gold/full_document_spans.jsonl` — 8 + 2 `CCONTI`
  expectations to migrate to `CONT` plus the section suffix.

Add 3–4 full Corte dei conti documents to `tests/benchmark_docs` (one regional sentenza, one
central appeal, one regional controllo parere, one Sezione delle Autonomie deliberazione) so
the throughput bench and the span gold cover the shapes.

---

## 7. Order of work

1. `catalog.py` tables + `CCONTI`→`CONT` and the gold migration. Self-contained; the whole
   suite stays green after it.
2. `_corte_conti_resolve` + the new `_COURT_PATTERNS` entries — giurisdizionale only. This is
   the 47 % slice and needs no assembler change.
3. `urn.py` suffix + `urn_to_text`.
4. `assembler.py` `DEL`/`PARERE` pairing + the slash-chain classifier — unlocks controllo.
5. `DocumentContext.cc_section`.

Steps 1–3 are independently shippable and already double what the library recognizes today.
