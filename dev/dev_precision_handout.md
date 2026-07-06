# linkengine precision — handout for the next session

You are continuing a **precision-hardening** effort on `linkengine`, a pure-Python recognizer of
Italian legal citations (URN-NIR / ECLI / CELEX / PRAX). The goal of this phase: **fewer false
positives, correct act↔partition pairing, clean citation-series splitting, tight text anchors** —
even at the cost of some recall. The cardinal rule the user set:

> **Better to miss a partition than to assign a wrong one. Get the *acts* right first.**

---

## 0. Orientation (read this first)

- **Package**: `src/utils/linkengine/linkengine/` (pip-installed editable as `from linkengine import …`).
- **Env / how to run** (the env is `ml`; filter the harmless numpy/JVM import noise):
  ```bash
  cd src/utils/linkengine
  /opt/anaconda3/envs/ml/bin/python -m pytest -q          # unit tests — MUST stay green
  /opt/anaconda3/envs/ml/bin/python -m tests.goldeval     # the hand-verified gold gates
  PYTHONPATH=. /opt/anaconda3/envs/ml/bin/python dev/dev_precision_triage.py [filter]
  ```
- **The gold gates are the contract.** Current baseline that must NOT regress (as of 2026-07-05):
  `pytest` 195 passed · gold **manual 258/258 · partitions 31/31 · precision F1=1.000 (141 excerpts)
  · fields 303/303**. After *every* change run pytest + goldeval. If gold drops, you broke a
  verified behavior — fix or revert before moving on.
- **`dev/dev_precision_triage.py`** holds ~48 real-document examples (each with a note on what's wrong).
  It is the working scratchpad for this effort (NOT a gate). Cases are referenced below as `[NN]`.
- **When you fix a case, lock it in**: add a row to `tests/gold/gold_precision.csv`
  (`id|authority|note|expected_urns|text`; empty `expected_urns` = a false-positive guard) and/or
  `tests/gold/gold_fields.jsonl`. This is how we stop regressions.

### Architecture in one paragraph
`engine.extract(text)` runs recognizers (`recognizers.py`, `partitions.py`) → typed `Span`s →
`assembler.assemble(spans, text)` groups them into `Reference`s → `engine._fill_fields` fills the
feature row → `urn.build_urn(row)` builds the identifier. The **assembler** is where almost all the
remaining problems live.

### What was already redesigned this phase (do NOT redo)
- **Partition→act pairing** was rewritten (`assembler._article_groups` / `_pair_group` /
  `_pair_partitions`). Model: cut partitions into **act-bounded runs**, resolve backward "del…"
  links, split into **article-groups**, pair each group to an act by precedence
  **right-direct → right-list → left-direct → left-list → nearest-fallback**. A bare `e` joins a
  shared list ("art. 8 e art. 32 … del d.lgs. 286"); a genitive `dell'` breaks it ("e dell'art. 360
  … del c.p.c."). This fixed the cross-act garbling ([10],[11],[12],[23],[31],[47]).
- **Number→act binding** prefers the nearest *preceding* doctype the number follows
  ("d.l. … n. 168, … legge … n. 197"), but not across a court or another act. Fixed [40].
- **Caselaw series**: a court can't bind to a SENT/ORD anchor across another court; an act-internal
  number isn't stolen by a nearby court; date-bridging won't cross a closer court. Fixed [08],[24],[30].
- **Structural precision rules** (earlier): ricorso/R.G. dockets ignored; alias ⇒ no doc number;
  authority↔doctype compatibility (AdE ≠ sentenza); procedural dates (depositata/pubblicata/…) don't
  bind; unresolved date-only refs dropped (DECR exempt). See memory `precision-hardening`.

---

## 1. The main problems to work on (prioritized)

### P1 — Tight text anchors + stray date binding  ⟵ highest value, cross-cutting
The `text` anchor (the highlighted span) routinely **swallows neighbouring prose and dates**, and a
nearby date wrongly becomes the act's `doc-date`. The URN is usually correct; the *anchor* and
`doc-date` are wrong. Two coupled sub-problems:

**(a) Leading/trailing dates bind to an act that already has its own year.**
- `[14]` `31/1/2022 ai sensi dell'art.8 L.890/1982` → `doc-date=2022-01-31` (law is **1982**); anchor starts at the date.
- `[04]` `A partire dal 15 maggio 1998 … legge n. 146 del 1998` → date pulled into the anchor + doc-date.
- `[16]` `data 8 settembre 2023 … D.M. n. 701 del 1994` → doc-date 2023 (decree is **1994**).
- `[15]` `…L.890/1992). Il 20/1/2022` → trailing date binds; anchor also starts at an unrelated `n.15/A2-2020`.
- *Desired*: a DATE should bind as `doc-date` only when the act has **no year of its own** (no
  NUM_YEAR), and only when adjacent/genitive-connected — otherwise leave it free and out of the anchor.
- *Where*: the DATE branch of the floating loop in `assembler.assemble` (bind a DATE to an act only
  if the act lacks a year); `recognize_dates` already tags procedural dates `role="proc"` — extend
  that idea.

**(b) Anchor run-on past clause/sentence boundaries.**
- `[22]` `…previdenza.".Secondo Corte di Cassazione sentenza n. 27341/2024` — anchor eats the prior sentence.
- `[38]` `legge … n. 136; rilevato che entro il 31 dicembre 2020` — anchor runs past the `;`.
- `[03]` `…cartella n. 097 … codice della strada anno 2016` — anchor spans the whole cartella number.
- `[21]` `interpello n. 954-383/2008. Tuttavia … risposta` — run-on (and the number is read `383`, not `954-383`).
- *Desired*: the anchor should be the minimal citation span — trim leading/trailing tokens that are
  not part of the act/partition (verbs, "Secondo", text after `;`/`.`).
- *Where*: `assembler._assign_text_context` (it sets `text`/`context` from the span extent — make it
  trim to the recognized spans rather than the raw character range; clip at sentence/`;` boundaries).

This whole area is the biggest remaining win and touches the most cases. A small, well-tested change
to `_assign_text_context` + the date-binding rule would close ~8 cases.

### P2 — `_propagate_acts` resurrects articles whose act was dropped  ⟵ small, concrete, do early
- `[06]` `art. 16 del d.lgs. 46/99 … (artt. da 45 a 90) del d.p.r. 602 cit.` →
  `artt. 45–90` wrongly emitted as **d.lgs. 46** articles.
- *Root cause* (confirmed): the pairing **correctly** binds `45–90` to `d.p.r. 602` (right-direct),
  but `d.p.r. 602` carries **no number** ("602 cit." has no "n."/year), so that reference fails
  `_valid` and is dropped. `_propagate_acts` then sees `art. 45`/`art. 90` as *orphans* and
  re-attaches them to the nearest preceding numbered act, `d.lgs. 46/99`. So a dropped act leaks its
  partitions onto an unrelated one.
- *Fix*: `_pair_partitions` already returns the set of **attached** span ids. Thread that through so
  `_propagate_acts` treats attached articles as non-orphan even when their host ref was dropped
  (i.e. they should be *missed*, not propagated). Per the cardinal rule.
- *Bonus*: a bare doctype number with no "n."/year ("d.p.r. 602") is not recognized as a NUMBER at
  all (see `recognizers._NUMBER`, which requires an "n." prefix). Recognizing `DOCTYPE <bare-number>`
  would let `[06]`'s d.p.r. 602 resolve — but be careful of false positives.

### P3 — Caselaw "emessa da / pronunciata da" points *backward*
- `[09]` `sentenza n. 124/2021 emessa dalla CTP RIMINI … e Sentenza n. 629/2025` → the CTP binds to
  the **2nd** sentenza (629); it should bind to the **1st** (124, the one it was "emessa da").
- *Desired*: an authority introduced by `emessa/pronunciata/resa/depositata da(lla)` attaches to the
  pronouncement **before** it, overriding nearest-distance.
- *Where*: authority binding in `assembler.assemble` (the SENT/ORD ↔ authority logic) — add an
  "agent phrase points left" rule, analogous to the partition right/left precedence.

### P4 — Bare number as an article after a conjunction
- `[43]` `…cod. proc. civ., e 54, comma 3, del d.l. … 83` → `54` is not read as `art. 54`, so d.l. 83
  gets an orphan `comma-3`.
- `[25]` `artt. 6, secondo comma, 49 e 51 t.u.i.r.` → `art. 49` is missing (bare `49` between a comma
  and `51`).
- *Desired*: inside/after a partition list, a bare number that fits the pattern is an article.
- *Where*: `partitions.py` value-list expansion / `engine._bare_code_articles`. Risky for false
  positives — gate tightly and protect with gold.

### P5 — Recognition gaps (independent of pairing)
- `[01]` `…sentenza … emessa dalla Corte di Giustizia Tributaria di I grado di Roma` — the court **is**
  recognized (CTP/CGT-I, Roma) but sits **71 chars** from its sentenza, 1 over `MAX_GAP=70`, so it
  doesn't bind → ∅. Consider: an authority reached by a clean agent phrase ("emessa dalla …") should
  bind regardless of distance (ties into P3), rather than bumping `MAX_GAP` globally.
- `[07]` `…della S.C. (Sez. 5, Ordinanza n. 22108…)` — `S.C.` (Suprema Corte) not recognized.
  **Deliberately skipped**: "S.C." collides with *società cooperativa*. Only add with strong context
  guards (e.g. followed by "Sez."/"sentenza"/"ordinanza") or skip.

### P6 — Messy series edge (low priority, rare)
- `[29]` `la cassazione della sentenza (Cass. … n. 18202, Cass. … 2009, n. 18421; …)` — now yields 4
  refs (was 5 garbled), 3 fully correct, but the leading **generic** "cassazione della sentenza"
  (here "cassazione" = the act of quashing, not a court) plus the SENT anchor steal the first date,
  so `18202` gets the 2nd court's year. Niche; only chase if P1–P3 are done.

### P7 — Minor
- `[47]` is otherwise correct but emits one spurious `…art4-…-lete`: the `e` in "lettera f), **e**
  l'articolo 16" is read as *lettera e*. Tighten the LETTER continuation guard in
  `partitions._emit_list` (an `e` followed by `l'<word>` is the conjunction, not a letter value).

---

## 2. Cardinal constraints & gotchas
- **Never regress the gold.** Run `pytest -q` and `python -m tests.goldeval` after every edit. The
  precision set is an *exact-set* match — a single spurious or missing URN fails it.
- **Acts > partitions.** When pairing is ambiguous, drop the partition (emit the bare act) rather
  than guess. The pairing functions return `None` for "unpaired" on purpose.
- **Prefer small, local rules with a clear linguistic justification** over widening windows/gaps —
  the previous heuristic failed because it was purely distance-based.
- The assembler is offset-driven and the input text is immutable; reuse `_gap`, `_semicolon_between`,
  `_GEN_R`/`_PUNCT`/`_LISTSEP` connectors, and `segment`/`_resolve_backward` rather than re-deriving.
- Filter import noise in shell output with:
  `grep -v -i "numpy\|pybind\|downgrade\|_ARRAY_API\|jpype\|jnius\|loading\|Loaded\|^A module"`.

## 3. Suggested order of attack
1. **P2** (small, isolated, clearly correct — thread `attached` into `_propagate_acts`).
2. **P1** (highest value; do `_assign_text_context` trimming and the date-binding rule together,
   gold-guarded — adds the most user-visible quality).
3. **P3 + P5/[01]** (agent-phrase "emessa da" points left and binds beyond `MAX_GAP`).
4. **P4 / P7 / P6** as time allows.

Add each win to `gold_precision.csv` / `gold_fields.jsonl` as you go.
