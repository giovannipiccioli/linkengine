# Giustizia amministrativa — recognition and ECLI normalization

**Implemented.** This is the plan the change was built from, kept for the evidence in §1, §4
and §5. It shipped as written; the only additions were found by running it:

- **`decisione` and `parere` had to reach their court.** Both seed an act frame, so the
  authority was refused entry — the same pairing the Corte dei conti needed. The two
  constants are now one table, `catalog.COURT_EXTRA_DOCTYPES`.
- **"per la/il" leads the geography** more often than not in the full court name
  ("Tribunale Amministrativo Regionale per la Sicilia"), and `_geo_after` does not skip it.

Measured after the change, over the same fourteen documents: **30 of 30 citations found,
precision 0.968** (recall 1.000). Two citations the hand annotation had missed were found by
the engine, verified against the archive and added to the gold.

At corpus scale — 272 identifiers built from all 106 sampled decisions and looked up in the
2.8 M-entry archive — **85.3 % are exactly right, 11.8 % carry the wrong type** and 2.9 % name
a decision the archive does not hold. Nearly all of the type errors are a *sentenza breve*
read as an ordinary sentenza, which a citation saying only "sentenza" cannot distinguish;
`ADMIN_DOCTYPE_QUALIFIED` picks up the qualifiers that are spelled out ("sentenza breve", "in
forma semplificata", "ordinanza collegiale"). **No identifier names a different real
decision**: the court, the year and the number are never guessed, so a wrong type is a
reference that resolves to nothing rather than to somebody else's ruling.

Evidence: the 2 863 244-row scraped archive in
`data/raw/giustizia_amministrativa/<year>/metadata_<year>.csv` (21 years, 2006–2026), whose
`ecli` column is the Council's own identifier; plus 106 decisions sampled from 2015, 2019 and
2023 across every court code and converted from HTML to text.

---

## 1. What the identifier has to look like

```
ECLI:IT:<COURT>:<year>:<number><TYPE>
```

| decision | ECLI |
|---|---|
| TAR Lombardia, sez. staccata di Brescia, sentenza 459/2023 | `ECLI:IT:TARBS:2023:459SENT` |
| Consiglio di Stato, sez. VII, sentenza 855/2023 | `ECLI:IT:CDS:2023:855SENT` |
| CGARS, sentenza 296/2023 | `ECLI:IT:CGARS:2023:296SENT` |
| TRGA Trento, sentenza 198/2023 | `ECLI:IT:TRGATN:2023:198SENT` |
| TAR Lazio, ordinanza cautelare 4246/2023 | `ECLI:IT:TARLAZ:2023:4246OCAU` |

Three facts drive everything:

1. **The court component is the SEAT, not the region.** `TARNA` (Napoli), `TARBS` (Brescia),
   `TARCT` (Catania) — not `TARCAM`, `TARLOM`, `TARSIC`, which do not exist. Eight regions
   have two seats and they are the largest ones, so this is not an edge case.
2. **The type suffix is load-bearing.** Each document type numbers independently, so
   41.5 % of court+year+number triples carry more than one type — number and year alone name
   no decision. This is the Cassazione CIV/PEN situation, four families wide.
3. **The section is not in the identifier.** `sez. VII`, `Sezione Terza`, `ad. plen.` stay
   recognition fields. Simpler than the Corte dei conti, where the section *is* the identity.

---

## 2. Where the library stands (measured)

```
T.A.R. Lazio, Roma, sez. II, sentenza n. 20031/2023 -> ECLI:IT:TARLAZ:2023:20031   (no type)
TAR Lombardia, Brescia, sez. I, n. 250/2021         -> ECLI:IT:TARLOM:2021:250     (no such court)
T.A.R. Campania, Napoli, sez. VIII, n. 1234/2022    -> ECLI:IT:TARCAM:2022:1234    (no such court)
Consiglio di Stato, sez. IV, n. 700/2023            -> ECLI:IT:CONSSTATO:2023:700  (no such court)
C.G.A.R.S., sentenza n. 100/2021                    -> nothing
T.R.G.A. Bolzano, n. 12/2020                        -> nothing
Cons. Stato, parere n. 1234/2021                    -> nothing
```

Scored over the fourteen annotated documents: **precision 0.000, recall 0.000 on 28
citations**. The engine *finds* these citations — authority, number, year and section are all
filled — and then builds an identifier that resolves to nothing. Every administrative ECLI
the library emits today is wrong.

---

## 3. The change, file by file

Smaller than the Corte dei conti change: no new resolver, because the section is not part of
the identifier. It is three tables and two suffix rules.

### 3.1 `catalog.py`

* `COURTS["CONS_STATO"]["ecli"]`: `"CONSSTATO"` → `"CDS"`.
* `COURTS["TRIB_AMM_REG"]["geo"]`: `"region"` → `"city"`. The geo carried is the seat.
* Two new authorities: `CGARS` (Consiglio di giustizia amministrativa per la Regione
  Siciliana, `ecli: "CGARS"`, no geo) and `TRIB_REG_GIUST_AMM` (`TRGA`, geo `city`, for the
  two autonomous provinces).
* `TAR_SEAT` — the §4 table, seat code → ECLI component, and the region → capital-seat
  default under it.
* `ADMIN_DOCTYPE` — the §4 type table.

### 3.2 `recognizers.py`

The TAR pattern already asks for a region (`want="region"`). It has to ask for **either**, and
prefer the seat:

* `TAR <Regione>` → the region's capital seat (`TAR Sicilia` → `TARPA`);
* `TAR <Regione>, <Seat>` / `TAR <Regione> — <Seat>` / `TAR <Regione> sezione staccata di
  <Seat>` → the named seat (`TARCT`); all three orders occur, and the third is the commonest;
* `TAR <Seat>` alone → that seat (`TAR Brescia` → `TARBS`, `Tar Catania` → `TARCT`).

This is `_geo_after(..., "either")`, which already exists and is what the CTP/CTR pair uses —
the only new part is mapping the result through `TAR_SEAT`.

Two new authority patterns: `consiglio di giustizia amministrativa` / `C.G.A.` / `C.G.A.R.S.`
→ `CGARS`, and `tribunale regionale di giustizia amministrativa` / `T.R.G.A.` → `TRGA` with a
Trento/Bolzano seat. Bolzano decisions are sometimes in German — out of scope, and cheap to
leave so: the German text still names the court in Italian in its own header block.

### 3.3 `urn.py`

`_court_ecli` appends the type suffix for the three administrative authorities, from the
row's own `doc-type`, the way the Cassazione appends CIV/PEN. Everything else is untouched.

---

## 4. The tables

**Court component.** Eleven regions have one TAR and use the region code; eight have two seats
and use province targas — except Lazio, whose seat keeps `TARLAZ`. A table, not a rule:

| region | seat (default) | detached section |
|---|---|---|
| Lazio | `TARLAZ` Roma | `TARLT` Latina |
| Lombardia | `TARMI` Milano | `TARBS` Brescia |
| Campania | `TARNA` Napoli | `TARSA` Salerno |
| Sicilia | `TARPA` Palermo | `TARCT` Catania |
| Puglia | `TARBA` Bari | `TARLE` Lecce |
| Calabria | `TARCZ` Catanzaro | `TARRC` Reggio Calabria |
| Abruzzo | `TARAQ` L'Aquila | `TARPE` Pescara |
| Emilia-Romagna | `TARBO` Bologna | `TARPR` Parma |
| Toscana `TARTOS` · Veneto `TARVEN` · Piemonte `TARPIE` · Liguria `TARLIG` · Marche `TARMAR` · Sardegna `TARSAR` · Molise `TARMOL` · Basilicata `TARBAS` · Umbria `TARUMB` · Friuli-V.G. `TARFVG` · Valle d'Aosta `TARVDA` | | |

Plus `CDS` (Consiglio di Stato), `CGARS`, and `TRGATN` / `TRGABZ` — the Trentino tribunals are
a separate court, not a TAR.

**Type component**, with the share each takes when a citation names only its family:

| citation says | code | share | others in the family |
|---|---|---|---|
| sentenza | `SENT` | 85.7 % | `SENB` sentenza breve 13.7 %, `DISS` dispositivo 0.6 % |
| ordinanza | `OCAU` | 75.8 % | `OCOL` collegiale 22.4 %, `OPRE` presidenziale 1.8 % |
| decreto | `DDEC` | 87.7 % | `DCAU` 6.2 %, `DPRE` 4.4 %, `DCOL` 1.2 %, `DING` |
| parere | `PDEF` | 71.0 % | `PINTE` interlocutorio 16.3 %, `PARE` 12.7 % |

`sentenza breve` is normally spelled out when it is one, and should map to `SENB` — the CGARS
document in the corpus does exactly that, and the archive confirms the decision is `SENB`.

---

## 5. What this will and will not get

Measured over 149 administrative citations in the 106 sampled decisions:

| | share |
|---|---|
| TAR: seat named, alone or with the region | 44 % |
| TAR: region only → the capital-seat default decides | 38 % |
| TAR: neither ("il Tar", "questo T.A.R.") | 18 % → `DocumentContext` |
| a doc-type word stands next to the number | 53 % |

### Decisions to make explicitly

* **No type word → `SENT`.** Legal prose cites sentenze; of the citations in the sample that
  do name a type, 78 % say sentenza. This is an assumption of the same kind as the Cassazione
  CIV default, and should be documented the same way rather than hidden.
* **Region only → the capital seat.** A *sezione staccata* is always named when it decided, so
  the bare region means the seat. The corpus confirms it: the CGARS decision cites the same
  ruling twice, once as "TAR Sicilia (Sezione Terza) n. 2028/2022" and once as "Tar Sicilia –
  Palermo … n. 2028", and the archive has it under `TARPA`.
* **Ordinanze and decreti carry a real error rate** (24 % and 12 % of the unambiguous cases go
  to a different code). Worth accepting for `OCAU`/`DDEC`, worth revisiting if these turn out
  to be cited often.

### Out of scope

* German-language Bolzano decisions.
* `GPAT` (gratuito patrocinio) and other non-citable types.
* The RG number. `ricorso numero di registro generale 4913/2018`, `N. 09292/2020 REG.RIC.` and
  `sull'appello (n. 1884/2021)` are docket numbers, not decisions — the existing
  `FORBIDDEN_URNS` guard for `admin_consiglio_stato_2021_2023.txt` already pins this, and the
  new corpus adds three more instances of the trap.

---

## 6. Tests (already in the tree)

* `tests/gold/gold_giustizia_amm_docs.jsonl` — **26 whole decisions, 100 citations**, every TAR
  / Consiglio di Stato / CGARS ruling cited in each, read by hand and checked one by one
  against the 2.8 M-entry archive. Twenty-six verified by lookup; the two pre-2006 ones are
  correct by construction, the archive starting at 2006.
* Six of the fourteen cite nothing and are there for precision: their RG numbers,
  *deliberazioni comunali* and article numbers must not become decisions.
* Coverage: `CDS` (sentenza, ordinanza collegiale, adunanza plenaria), `TARLAZ`, `TARNA`,
  `TARSA`, `TARBS`, `TARCT`, `TARPA`, `CGARS`, `TRGATN`, and `SENT`/`SENB`/`OCAU`/`OCOL`.
* `goldeval.score_giustizia_amm_docs` scores it; `test_giustizia_amministrativa_document_gold`
  runs it with the floors at zero, which is where the engine is. **Raise the floors as the
  work lands** — that is what the test is for.

Migration due with the change: 15 `CONSSTATO` and `TARLOM`/`TARSIC`/`TARCAM`-style
expectations across `gold_manual.csv`, `gold_fields.jsonl`, `gold_precision.csv`,
`test_full_documents.py` and `full_document_spans.jsonl`.

---

## 6b. How other courts cite these decisions

Checked by mining 400 administrative decisions and 60 Corte dei conti decisions from 2023, on
top of the 106 already sampled.

* **Administrative courts essentially never cite the Corte dei conti.** Five of 400 documents
  mention the Court at all, and the one that pairs it with a number is "registrato alla Corte
  dei Conti il 25.1.2010" — the registration of a decree, not a citation.
* **The Corte dei conti does cite them, in exactly the same forms** the administrative courts
  use for themselves: `Cons. Stato, Sez. III n.8663/2022`, `TAR Lombardia, Sez. staccata
  Brescia, n. 401/2020`, `TAR Veneto, n. 1116/2022`. No court-specific dialect, so no separate
  recognition path is needed — the same patterns serve both directions. The only new surface
  was `Sez. staccata Brescia` without the "di", which the seat lead already accepts.
* Those citations almost never name a document type, which is what the sentenza default is for.

One bug surfaced from this direction and was fixed: in `Cons. Stato, Sez. II, n. 1244/2020, e
Sez. IV, n. 1471/2006` the second bare section defected to the Cassazione, because the first
one — dropped as an implicit Cassazione reading — was then counted as Cassazione *context* for
the second. An implicit reading can no longer license the next one. The fault was general and
pre-existing, reproducing identically with C.T.R. and Corte dei conti lists, and it produced a
real but unrelated ruling rather than a dead link.

## 7. Order of work

1. `catalog.py` tables + `CONSSTATO`→`CDS`, and the gold migration. Self-contained.
2. `urn.py` type suffix — turns `doc-type` into the identifier's last component.
3. `recognizers.py` seat resolution for the TAR.
4. `CGARS` and `TRGA` as authorities.
5. Raise the floors in `test_giustizia_amministrativa_document_gold`.

Steps 1–2 alone should take the document evaluation from 0.000 to roughly the share of
citations that name the Consiglio di Stato — about half the corpus.
