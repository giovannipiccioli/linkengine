# linkengine

**Recognize, parse and normalize Italian legal citations into stable identifiers.**

`linkengine` reads free Italian legal text and turns every citation it finds — a law, a
decree, a court decision, an EU act, a tax-authority circular — into a canonical machine
identifier (**URN-NIR**, **ECLI**, **CELEX** or **PRAX**), together with the recognition
fields it extracted along the way.

```python
from linkengine import LinkEngine

engine = LinkEngine()
for ref in engine.extract("Visto l'art. 2697 c.c. e la Cass. n. 100/2020, si applica il D.L. n. 34/2020.").rows:
    print(ref["text"], "->", ref["urn"])

# art. 2697 c.c   -> urn:nir:stato:regio.decreto:1942;262:2~art2697
# Cass. n. 100/2020 -> ECLI:IT:CASS:2020:100CIV
# D.L. n. 34/2020 -> urn:nir:stato:decreto.legge:2020;34
```

It is **pure Python, zero runtime dependencies** (standard library only), and self-contained:
all reference data — courts, document types, regions, the ~8 000 Italian comuni, legislative
aliases — is baked in, so no network or external service is needed.

---

## Features

- **Four identifier schemes**, chosen automatically per reference:
  | kind | example citation | identifier |
  |------|------------------|------------|
  | national / regional legislation | `art. 19 del d.lgs. 546/1992` | `urn:nir:stato:decreto.legislativo:1992;546~art19` |
  | case law (Italian courts) | `Cass. civ. n. 29036/2021` | `ECLI:IT:CASS:2021:29036CIV` |
  | EU acts & CJEU case law | `direttiva 2006/112/CE`, `causa C-123/20` | `CELEX:32006L0112`, `CELEX:62020CJ0123` |
  | tax-authority practice | `Circolare AdE n. 25/E/2020` | `PRAX:AE:CIRC:2020:25` |

- **Segmentation** — a sentence with several citations is split into one reference each, and
  ranges/lists are expanded (`artt. 15-18 DPR 600/73` → four articles; `cause riunite C-1/20 e
  C-2/20` → a single joined-case CELEX).
- **Partitions** — articles, commi, paragrafi, lettere, numeri and CJEU punti are parsed and
  appended to the identifier (`~art14-comma4-letb-num1`).
- **Aliases & abbreviations** — codes and consolidated texts by full name *and* abbreviation
  (`codice civile`/`c.c.`, `c.p.c.`, `TUIR`, `GDPR`, `Cost.`, …), tax treaties
  (`Convenzione Italia-Francia`), and annual budget laws (`legge finanziaria 2008`,
  `legge di bilancio 2023`).
- **`urn_to_text`** — the inverse map: a canonical identifier back to a readable citation
  (`ECLI:IT:CASS:2020:1234CIV` → `"Cassazione civile n. 1234/2020"`).
- **HTML annotation** — re-emit the input with each recognized reference wrapped in a tag
  carrying its fields, so you can *see* what was picked up.
- **Anchors** — `reference_anchors` gives the character offsets underneath that rendering, so a
  caller producing something other than HTML (JSON spans, `<a>` elements, a text editor's
  highlights) locates each citation in the source without searching for it again.
- **Configurable context** — a deciding court for self-references (`questa Corte`), a default
  region for unqualified regional laws, and how to read a bare `regolamento`.
- **Normativa mode** — inside a known legislative unit, resolve otherwise-bare internal
  partitions (`articolo 15`, `comma 2`, `presente articolo`) and conservatively follow a named
  amended act through common replacement and insertion clauses.

---

## Install

```bash
pip install -e .            # from a clone of this repository
# or, for development with the test extras:
pip install -e ".[test]"
```

`linkengine` requires Python ≥ 3.8 and has no third-party runtime dependencies.

---

## Quick start

```python
from linkengine import LinkEngine, urn_to_text, annotate_html

engine = LinkEngine()

# 1) extract — one feature dict per recognized reference, each with a canonical `urn`
result = engine.extract("art. 43, comma 1, del d.P.R. n. 600 del 1973")
row = result.rows[0]
row["urn"]        # 'urn:nir:presidente.repubblica:decreto:1973;600~art43-comma1'
row["doc-type"], row["number"], row["year"], row["partition"]
#               ('DECR', '600', '1973', 'articolo-43_comma-1')

# 2) render an identifier back to text
urn_to_text("CELEX:32016R0679")          # 'regolamento (UE) 679/2016'
urn_to_text("PRAX:DIF:DIR:2012:2")       # 'direttiva Dipartimento delle Finanze n. 2/2012'
urn_to_text("DEL:COG274:2014:34")        # 'delibera del Comune di Palestrina n. 34/2014'

# 3) see what was recognized, in context
annotate_html("Si vedano gli artt. 15-18 DPR 600/73.")
#  -> the text with each article wrapped in <span class="lkn-ref" data-urn=… …>…</span>
```

### Extracting legislation (`normativa` mode)

The default mode stays conservative: a bare `articolo 15` is not a citation in ordinary legal
prose. When processing one known structural unit of legislation, pass its canonical unit
identifier:

```python
text = "Si applicano l'articolo 84, comma 2, e il comma 3 del medesimo articolo 84."
result = engine.extract(
    text,
    mode="normativa",
    current_unit_urn=(
        "urn:nir:presidente.repubblica:decreto:1986-12-22;917~art8"
    ),
)
[row["urn"] for row in result.rows]
# ['urn:nir:presidente.repubblica:decreto:1986-12-22;917~art84-comma2',
#  'urn:nir:presidente.repubblica:decreto:1986-12-22;917~art84-comma3']
```

The input is an ordinary string and requires no particular source format or preprocessing. Use
the mode on one structural unit at a time. Explicit citations follow exactly the same rules as
in standard mode, while the current act is a fallback for partition spans ordinary assembly left
unclaimed. Structural `Art. N` headings are not citations. National units use their exact NIR,
including the full promulgation date; EU units use a canonical CELEX locator such as
`CELEX:32016R0679~art17`.

Common *novelle* are scoped to their explicitly named target. In the example below, neither
bare reference belongs to the decree currently being processed:

```python
text = (
    "Al decreto legislativo 19 giugno 1997, n. 218, sono apportate le seguenti "
    "modificazioni: all'articolo 5 il comma 1 è sostituito dal seguente: "
    "«1. Nei casi di cui all'articolo 6 si applica il comma 2.»"
)
result = engine.extract(
    text,
    mode="normativa",
    current_unit_urn="urn:nir:stato:decreto.legislativo:2024;13~art1",
)
[row["urn"] for row in result.rows]
# ['urn:nir:stato:decreto.legislativo:1997;218',
#  'urn:nir:stato:decreto.legislativo:1997;218~art5-comma1',
#  'urn:nir:stato:decreto.legislativo:1997;218~art6-comma2']
```

This is deliberately a scope resolver, not a general legislative-amendment parser. It handles
only a named target, nearby amendment wording, numbered blocks and balanced quotation marks.
When an excerpt omits the target act or ownership is genuinely ambiguous, the incomplete
reference is left unresolved instead of being linked to the wrong act. Complete citations,
including those inside replacement text, stay on the ordinary extraction path.

### Highlighting references in HTML

`annotate_html` re-emits the **original text** with every recognized citation highlighted (styled
like a link). The visible text is unchanged; the extracted fields live only in `data-*` attributes
(inspect them in DevTools or read them programmatically) — nothing is shown inline.

One function, two outputs, selected by the `page` flag:

```python
from linkengine import LinkEngine, annotate_html

text = open("sentenza.txt").read()

# inline fragment — embed it inside your own page/template
annotate_html(text)

# complete standalone document — write it straight to a file and open in a browser
with open("sentenza.html", "w") as f:
    f.write(annotate_html(text, page=True))
```

Pass `only_with_urn=True` to highlight only the citations that resolved to a `urn`. To reuse an
extraction (or a configured engine), pass the result in: `annotate_html(text, engine.extract(text))`.

### Locating citations in the source (`reference_anchors`)

HTML is one way to present what was recognized; the offsets underneath it are reusable.
`reference_anchors` returns `[(start, end, [rows…]), …]` in document order, where `text[start:end]`
is the citation surface and the rows carry its fields. Anchors never overlap, so they can be
walked in one pass to rebuild the text with markup of your own:

```python
from linkengine import LinkEngine, reference_anchors

text = "Si applica l'articolo 15, comma 1, lettere d), e), del d.lgs. 546/1992."

for start, end, rows in reference_anchors(text, only_with_urn=True):
    print(start, end, repr(text[start:end]), rows[0]["urn"])
# 13 45 'articolo 15, comma 1, lettere d)' ...:1992;546~art15-comma1-letd
# 47 70 'e), del d.lgs. 546/1992'          ...:1992;546~art15-comma1-lete
```

Each recognized partition keeps its own anchor and its own identifier, down to the letter — an
enumeration is *not* collapsed. Surfaces are not uniform, as above: the first item of a list
carries the article and comma, the last carries the act that identifies the whole list. What is
guaranteed is that anchors are exact, ordered and non-overlapping, and that no reference is
dropped or folded into its neighbour. Presentation decisions — whether a list of lettere deserves
one link or five, what granularity a target opens at — belong to the caller, not here.

Same options as `annotate_html`: `only_with_urn=True` for resolved citations only, and a
precomputed `result` to reuse an extraction or a configured engine —
`reference_anchors(text, engine.extract(text, mode="normativa", current_unit_urn=urn))`.

### Configuring context

```python
from linkengine import DocumentContext, LinkEngine

engine = LinkEngine()

# Document metadata is supplied per extraction, so one engine can process mixed courts.
roma = DocumentContext(
    authority="CORTE_GIUST_TRIBUT_1", city="Roma", region="Lazio", document_year=2022)
engine.extract("questa Corte, sent. n. 50/2019", context=roma).rows[0]["urn"]
#  -> 'ECLI:IT:CGT1RM:2019:50'

lombardia = DocumentContext(authority="CORTE_GIUST_TRIBUT_2", region="Lombardia")
engine.extract("questa Corte, sent. n. 51/2019", context=lombardia).rows[0]["urn"]
#  -> 'ECLI:IT:CGT2LOM:2019:51'

# The document region also resolves an unqualified regional law.
engine.extract(
    "art. 5 della legge regionale n. 4 del 2007", context=roma
).rows[0]["urn"]
#  -> 'urn:nir:regione.lazio:legge:2007;4~art5'

# Constructor defaults and direct per-call overrides remain available.
LinkEngine(default_authority="CORTE_CASS").extract(
    "questa Corte, sent. n. 50/2019"
).rows[0]["urn"]
#  -> 'ECLI:IT:CASS:2019:50CIV'
engine.extract(
    "questa Corte, sent. n. 50/2019", default_authority="CORTE_CASS"
).rows[0]["urn"]
#  -> 'ECLI:IT:CASS:2019:50CIV'

# Cassazione: the civil/penal branch, when the citation does not state it
cass_pen = DocumentContext(authority="CORTE_CASS", chamber="PEN")
engine.extract("Sez. 1, n. 41738 del 19/10/2011", context=cass_pen).rows[0]["urn"]
#  -> 'ECLI:IT:CASS:2011:41738PEN'      (without the context: ...41738CIV)
engine.extract("Cass. civ. n. 41738/2011", context=cass_pen).rows[0]["urn"]
#  -> 'ECLI:IT:CASS:2011:41738CIV'      the citation names its branch: context does not apply

# a bare "regolamento N/AAAA": national (default) vs EU
LinkEngine(default_regolamento_scope="comunitario").extract("il regolamento n. 123/2018").rows[0]["urn"]
#  -> 'CELEX:32018R0123'

# OCR accommodations are on by default; disable them for strict literal parsing
LinkEngine(ocr_accommodations=False).extract("artt. 7 I. 212/00").rows
#  -> []
```

`DocumentContext.authority` uses the stable codes in `linkengine.catalog.COURTS`, such as
`CORTE_CASS`, `CORTE_COST`, `CORTE_GIUST_TRIBUT_1`, `CORTE_GIUST_TRIBUT_2`,
`COMM_TRIBUT_PROV`, `COMM_TRIBUT_REG`, and `TRIB_AMM_REG`. It is intentionally not a free-text
court parser. `city` accepts an Italian
comune/province name (`Reggio Calabria`) or its ECLI code (`RC`); `region` accepts a region name,
its three-letter ECLI code (`LOM`), or its URN segment (`lombardia`, `emilia.romagna`). Unknown
values raise `ValueError`.

Modern CGT authorities emit the distinct ECLI court components `CGT1` and `CGT2`; historical
`COMM_TRIBUT_PROV` and `COMM_TRIBUT_REG` references retain `CTP` and `CTR`.

#### `cc_section` — the Corte dei conti section

The Corte dei conti decides through some fifty benches that number independently, and its
ECLI carries the deciding one as a suffix on the number — `ECLI:IT:CONT:2023:89SGCAL`. So
number and year alone name no decision, and a citation that states no section stays
unresolved with its recognition fields filled, rather than receiving an identifier that
resolves to nothing.

`cc_section` supplies the section of the document doing the citing, so its self-references
resolve — about a fifth of what a Corte dei conti decision cites is its own prior work:

```python
cc = DocumentContext(authority="CORTE_CONTI", cc_section="SGCAL")
engine.extract("questa Sezione n. 527/2009", context=cc).rows[0]["urn"]
#  -> 'ECLI:IT:CONT:2009:527SGCAL'
```

Values are the codes in `linkengine.catalog.CORTE_CONTI_SECTIONS`; an unknown one raises
`ValueError`. Like every other self-reference, it fills silence only: a citation that names
its own section always wins.

Every geographic part of a section code is the standard code from `geo.py` — the
three-letter region (`SGCAL`, `SRCLOM`, `SSRRCOSAR`), or the province targa for a section
that sits in a seat rather than a region (`SGTN`, `SGBZ`, `SRCTN`, `SRCBZ`). The Court's own
archive is not consistent about this, so these identifiers are linkengine's rather than the
portal's; the payoff is that knowing a region means knowing its section code.

#### `chamber` — the Cassazione civil/penal branch

`snciv` and `snpen` number their decisions independently, so `Cass. n. 13808/2025` names two
real and different decisions. Italian citation practice routinely omits the branch
(`Sez. 1, n. 41738`), and nothing in the citation can recover it — with no signal the engine
reads it as `CIV`, right for the overwhelming majority of citations but wrong for nearly every
one inside a penal judgment.

`chamber="PEN"` supplies the missing branch from the document doing the citing. It is an
assumption, deliberately made, and bounded by three rules:

- **it fills silence only** — `Cass. civ.`, `sez. trib.`, `sez. lavoro` and `Cass. pen.` all
  state their branch and always win;
- **only `PEN` is ever supplied** — `CIV` is already the fallback, so `chamber="CIV"` is
  accepted and changes no output;
- **no context, no assumption** — omit it and behaviour is unchanged.

Accordingly a *numbered* chamber carries no branch of its own: `sez. V` yields section `5`
(unstated), and `5CIV` only when the text says `civ`/`trib`. Measured on 150 penal judgments,
the context resolves 95.8% of their Cassazione citations to the penal twin; the residual risk
is a penal judgment citing a genuinely civil decision, which the corpus puts near zero.

Context is otherwise used conservatively: it resolves explicit self-references such as `questa
Corte` and unqualified regional laws, but does not turn every bare `Sentenza n. 123/2020` into a
decision of the current court. `document_year` is optional; when supplied, a citation from a later year remains
an unresolved candidate instead of receiving an impossible identifier. Set `regional_law_region`
when the regional-law fallback should differ from the deciding court's region.

The Corte dei conti resolves its section from the citation, in whatever order it arrives —
`Sez. III App.`, `Prima Sezione Centrale d'Appello` and `Terza Sezione giurisdizionale
centrale d'appello` are read as sections, and so are `Sez. contr. Lombardia`, `Sezioni
riunite` and `Sez. Autonomie`, which name the court on their own. Its controllo channel
pronounces by `deliberazione` and `parere`, and their procedural type is part of the
identifier: `deliberazione n. 102/2023/SRCPIE/PAR` -> `ECLI:IT:CONT:2023:102SRCPIE-PAR`.
The type is read out of the citation's slash chain whichever way round it is written
(`9/SEZAUT/2009/INPR`, `130/PRSE/2012`, `LOMBARDIA/164/2019/PAR`), and a controllo citation
that omits it stays unresolved. The rubrics that decorate a *giurisdizionale* citation
(`n. 7/2007/QM`, `n. 11/2023/RGC`, `n. 653/2013-A`) are not part of the identifier and are
dropped.

For the second-grade tax courts of Trentino-Alto Adige, include `city="Trento"` or
`city="Bolzano"` in the context. Their ECLIs use the autonomous-province components `CGT2TN`
and `CGT2BZ`; a context naming only the region is intentionally insufficient.

### Inspecting the pipeline

```python
res = engine.extract("art. 43 del d.P.R. n. 600/1973", debug=True)
res.references        # the assembled references, with character offsets over the source
res.trace             # the spans each recognizer produced (debug=True)
```

---

## How it works

The engine keeps the input text **immutable** and accumulates a typed **span set** over it
(character offsets are first-class — ideal for anchoring), then assembles spans into references
and builds each reference's identifier directly from its fields.

```
text
 │  recognizers/         dates · partitions · numbers · doctypes · authorities/courts ·
 ▼                       aliases · conventions · budget laws · regional laws  → typed spans
spans
 │  assembler            build typed citation frames, assign slot/partition ownership,
 ▼                       then branch and validate finalized references
references
 │  engine._fill_fields  recognition fields (ref-type, authority, doc-type, number, year,
 ▼                       partition, region/city, section, alias, …)
feature rows
 │  urn.build_urn        canonical identifier built directly from the fields
 ▼
rows with `urn`
```

### Module map (`linkengine/`)

| module | responsibility |
|--------|----------------|
| `model.py` | the span vocabulary (`Entity`, `Span`, `Reference`, `ExtractResult`) and the feature-row schema |
| `context.py` | validated per-document court and geographic metadata |
| `normativa.py` | validated current-unit NIR/CELEX context and internal locator resolution |
| `novelle.py` | conservative amendment-scope classification for normativa-only candidates |
| `recognizers.py` | regex recognizers (dates, numbers, doctypes, courts, …) → spans |
| `special_cases.py` | narrow, named lexical exceptions; structural policies do not belong here |
| `partitions.py` | partition recognition + range/list segmentation |
| `assembler.py` | group spans into references (binding, splitting, segmentation) |
| `engine.py` | `LinkEngine` — runs the pipeline and fills the recognition fields |
| `urn.py` | `build_urn(row)` and the standalone `urn_to_text(urn)` renderer |
| `catalog.py` | the knowledge base: courts (ECLI prefix / geo / name), doc-type names, alias display names |
| `aliases.py` | one record per legislative alias (recognition + nir/celex + display + scope) |
| `conventions.py`, `budget_laws.py` | parametrized law lookups (tax treaties; annual budget laws) |
| `geo.py` | provinces / regions / comuni ↔ codes (for ECLI geography) |
| `normalize.py` | URN-NIR / CELEX construction and validation |
| `html.py` | `reference_anchors(text)` — where each citation sits in the source; `annotate_html(text, page=…)` — the same, rendered as highlighted HTML |
| `runner.py` | `run_linkengine_string(text)` → pipe-separated CSV of the rows |

Adding coverage is localized: a new court goes in `catalog.py`, an alias in `aliases.py`, a
recognition pattern in `recognizers.py`.

---

## Testing & evaluation

The behavior is pinned by **hand-verified gold sets** (`tests/gold/`), scored by
`tests/goldeval.py` (self-contained — uses only the package):

- `gold_manual.csv` — recall over hand-checked URNs across all reference kinds;
- `gold_partitions.csv` — deep article/comma/lettera/numero partition chains;
- `gold_precision.csv` — full-sentence excerpts scored as an exact set (false positives count);
- `gold_fields.jsonl` — per citation: the expected segmentation **and** every recognition field.
- `gold_normativa.jsonl` — 73 sourced excerpts covering 70 distinct legislative units and 65
  acts (famous statutes plus ordinary acts, with the random samples selected using fixed seeds),
  spanning 1940–2025, 45 distinct years, seven act types, and five issuing authorities. A few
  unsupported constructions remain as measured limitations; the gate protects broad accuracy
  without requiring every pattern to be parsed.
- `gold_normativa_eu.jsonl` — 32 sourced excerpts covering 31 EU legislative units and 29 acts,
  including well-known and fixed-seed ordinary regulations, directives, and decisions from
  1958–2025. Complete external citations are also checked for exact equality with standard mode.
- `gold_corte_conti_docs.jsonl` — 13 whole Corte dei conti decisions (regional and central
  giurisdizionale, appello Sicilia, Sezioni riunite, regional and central controllo, Sezione
  delle Autonomie), with every citation of the Court read out of them by hand and checked
  against the Court's archive. Scored as an evaluation — precision and recall over the
  identifiers, gated below the current score — because recall is bounded by how these
  documents cite, not by the parser alone.
- `gold_normativa_novelle.jsonl` — 33 real amendment clauses and editorial notes from 14 famous
  and ordinary Italian legislative units, across 22 patterns and seven source years. Supported
  cases are exact regression gates; 12 named limitation cases preserve the semantic result and
  currently document where the intentionally small scope resolver stops.

```bash
pytest                          # unit tests + the gold gates
python -m tests.goldeval -v     # the gold scores, with any misses
python -m tests.bench_full_docs  # throughput over full documents and amendment units
```

---

## Example notebook

[`examples/quickstart.ipynb`](examples/quickstart.ipynb) is a commented, runnable tour of the
library — parsing, fields, segmentation, identifiers, aliases, context, normativa mode and HTML
output.

---



## Cite

If you use linkengine in academic work, technical reports, datasets, benchmarks, or other research outputs, please cite the specific version you used.

Recommended citation pattern:

Piccioli, Giovanni. linkengine: legal citation recognition and normalization for Italian legal documents. Version 1.0.0. https://github.com/giovannipiccioli/linkengine

```bibtex
@software{linkengine_2026,
  author       = {Piccioli, Giovanni},
  title        = {linkengine: legal citation recognition and normalization for Italian legal documents},
  year         = {2026},
  version      = {1.0.0},
  url          = {https://github.com/giovannipiccioli/linkengine},
  note         = {Python library}
}
```
If your BibTeX style does not support @software, use @misc instead.

---
## Inspiration

linkengine was inspired by, and originally bootstrapped against, the **Linkoln** library which is available at https://linkoln.gitlab.io/. If you use this library in academic work, please also acknowledge that project:

```bibtex
@article{linkoln,
  title={Improving public access to legislation through legal citations detection: the linkoln project at the Italian senate},
  author={Bacci, L. and Agnoloni, T. and Marchetti, C. and Battistoni, R.},
  journal={Knowledge of the Law in the Big Data Age},
  volume={317},
  pages={149},
  year={2019},
  publisher={SAGE Publications Limited}
}
```

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).
