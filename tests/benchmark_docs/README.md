Self-contained full-document benchmark corpus.

These text files are small samples copied from the user's local judgment corpora so benchmark
and partial full-document tests do not depend on external paths.

- `admin_tar_sicilia_2021_2023.txt`: administrative-justice TAR Sicilia decision.
- `admin_tar_lazio_2026_2731.txt`: administrative-justice TAR Lazio order.
- `admin_consiglio_stato_2021_2023.txt`: Consiglio di Stato administrative-justice decision.
- `bdgt_sentenza_z46_8121_2022.txt`: tax judgment from BDGT text normalization.
- `bdgt_sentenza_v28_898_2022.txt`: tax judgment with heading/prose false-positive risks.
- `bdgt_sentenza_u01_106_2022.txt`: BDGT tax judgment on deceased-taxpayer
  notifications with D.P.R. 600/1973, c.p.c., and Cassazione citation series.
- `bdgt_sentenza_u01_110_2022.txt`: BDGT tax judgment with compact D.L. references
  and an unresolved heading/procedural-date false-positive risk.
- `bdgt_sentenza_u59_465_2022.txt`: BDGT tax judgment on shareholder-income
  presumptions, settlement/accertamento references, and Cassazione citation series.
- `bdgt_sentenza_z01_745_2022.txt`: BDGT tax judgment on reclamation-consortium
  contributions with regional-law and tax-court references.
- `bdgt_sentenza_z55_3804_2022.txt`: BDGT tax judgment on appealability and procedural
  tax acts with Sezioni Unite references.
- `cass_2018_12769_civ.txt`: Cassazione 2018 civil judgment with Corte costituzionale,
  old-style CGUE, and OCR-style `I.` law citations.
- `cass_2018_32458_pen.txt`: Cassazione 2018 criminal judgment with Rv. citations.
- `cass_2018_17793_tax_civ.txt`: Cassazione 2018 tax civil order on IRAP.
- `cass_2018_25504_tax_civ.txt`: Cassazione 2018 tax civil judgment on condono and
  procedural appeal grounds.
- `corte_conti_2016_220_sgven.txt`: Corte dei conti regional judgment.
- `corte_conti_2016_45_sgbas.txt`: Corte dei conti regional judgment.
- `corte_conti_2016_682_app3.txt`: Corte dei conti appellate judgment.
- `corte_conti_2024_36_app3.txt`: Corte dei conti appellate judgment with slash-heavy heading.
- `corte_cost_2010_368.txt`: Corte costituzionale judgment.
- `corte_cost_2020_281.txt`: Corte costituzionale judgment with regional-law and EU-law references.
- `corte_cost_2024_204.txt`: Corte costituzionale judgment with tax-justice organization references.
- `cgue_62024cc0043_it.txt`: Italian CGUE Advocate General opinion with EU-law references.
- `cgue_62024cj0367_it.txt`: Italian CGUE judgment with Telenor case references and EU
  regulation anchors.
- `law_10_2020_body_tissue.txt`: national legislation text.
- `law_199_2025_budget.txt`: large national budget-law text.
- `law_dl_326_1987_spettacoli.txt`: national decree-law text with tariff-reference traps.
- `law_dpr_917_1986_tuir.txt`: legislation text for D.P.R. 917/1986 (TUIR).
- `prassi_ae_interpello_2025_26.txt`: Agenzia Entrate interpello.
- `prassi_ae_interpello_2025_10.txt`: Agenzia Entrate interpello with TUIR
  article 67 aliases and prassi resolution references.
- `prassi_ae_risoluzione_2017_146.txt`: Agenzia Entrate resolution with prassi references.
- `prassi_ae_risoluzione_2025_13.txt`: Agenzia Entrate resolution with Cassazione and alias references.
- `prassi_dogane_circolare_2017_8.txt`: Agenzia Dogane circolare with accise references.
- `tribunale_roma_contratti_2024_15396.txt`: Tribunale di Roma civil judgment.
- `tribunale_roma_lavoro_2016_5495.txt`: Tribunale di Roma labour judgment.

Run the benchmark with:

```bash
python -m tests.bench_full_docs
```

Generate pre-annotations and inspect span-gold coverage with:

```bash
python -m tools.full_doc_annotator candidates bdgt_sentenza_z55_3804_2022.txt \
  --jsonl /tmp/candidates.jsonl --html /tmp/candidates.html
python -m tools.full_doc_annotator coverage
python -m tools.full_doc_annotator metrics --verbose
```
