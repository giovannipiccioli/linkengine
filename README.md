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
  | tax-authority practice | `Circolare AdE n. 25/E/2020` | `PRAX:AE:CIRC:2020:25/E` |

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
- **Configurable context** — a deciding court for self-references (`questa Corte`), a default
  region for unqualified regional laws, and how to read a bare `regolamento`.

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
urn_to_text("CELEX:32016R0679")          # 'regolamento 2016/679/CE'

# 3) see what was recognized, in context
annotate_html("Si vedano gli artt. 15-18 DPR 600/73.")
#  -> the text with each article wrapped in <span class="lkn-ref" data-urn=… …>…</span>
```

### Configuring context

```python
# self-references resolve to the document's own court
LinkEngine(default_authority="CORTE_CASS").extract("questa Corte, sent. n. 50/2019").rows[0]["urn"]
#  -> 'ECLI:IT:CASS:2019:50CIV'

# a regional law cited without a region gets the document's region
LinkEngine(default_region="Campania").extract("art. 5 della legge regionale n. 4 del 2007").rows[0]["urn"]
#  -> 'urn:nir:regione.campania:legge:2007;4~art5'

# a bare "regolamento N/AAAA": national (default) vs EU
LinkEngine(default_regolamento_scope="comunitario").extract("il regolamento n. 123/2018").rows[0]["urn"]
#  -> 'CELEX:32018R0123'
```

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
 │  assembler            group spans into references (proximity + right-act binding,
 ▼                       multi-number / range splitting, segmentation)
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
| `recognizers.py` | regex recognizers (dates, numbers, doctypes, courts, …) → spans |
| `partitions.py` | partition recognition + range/list segmentation |
| `assembler.py` | group spans into references (binding, splitting, segmentation) |
| `engine.py` | `LinkEngine` — runs the pipeline and fills the recognition fields |
| `urn.py` | `build_urn(row)` and the standalone `urn_to_text(urn)` renderer |
| `catalog.py` | the knowledge base: courts (ECLI prefix / geo / name), doc-type names, alias display names |
| `aliases.py` | one record per legislative alias (recognition + nir/celex + display + scope) |
| `conventions.py`, `budget_laws.py` | parametrized law lookups (tax treaties; annual budget laws) |
| `geo.py` | provinces / regions / comuni ↔ codes (for ECLI geography) |
| `normalize.py` | URN-NIR / CELEX construction and validation |
| `html.py` | `annotate_html` / `render_html_document` |
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

```bash
pytest                          # unit tests + the gold gates
python -m tests.goldeval -v     # the gold scores, with any misses
```

---

## Example notebook

[`examples/quickstart.ipynb`](examples/quickstart.ipynb) is a commented, runnable tour of the
library — parsing, fields, segmentation, identifiers, aliases, configuration and HTML output.

---

## Inspiration

linkengine was inspired by, and originally bootstrapped against, the **Linkoln** project for
legal-citation detection at the Italian Senate. If you use this library in academic work,
please also acknowledge that project:

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
