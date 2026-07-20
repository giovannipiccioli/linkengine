Self-contained full-document benchmark corpus.

These text files are small samples copied from the user's local judgment corpora so benchmark
and partial full-document tests do not depend on external paths.

- `admin_tar_sicilia_2021_2023.txt`: administrative-justice TAR Sicilia decision.
- `admin_tar_lazio_2026_2731.txt`: administrative-justice TAR Lazio order.
- `admin_consiglio_stato_2021_2023.txt`: Consiglio di Stato administrative-justice decision.
- `admin_tar_toscana_2026_1122.txt`: TAR Toscana judgment converted from the
  administrative-justice XML/HTML source by preserving the visible `h:div` paragraphs;
  includes c.p.a., privacy-code, and GDPR partition lists (span-gold annotated).
- `admin_tar_catania_2026_368.txt`: TAR Catania judgment converted from the
  administrative-justice XML/HTML source, with c.p.a., burial-police regulation,
  administrative-procedure, Constitution, and mixed c.p.a./c.p.c. costs references
  (span-gold annotated).
- `admin_consiglio_stato_2026_255.txt`: Consiglio di Stato advisory opinion converted
  from the administrative-justice XML/HTML source, with public-contract legislation,
  administrative-procedure law, and unqualified regional-law references
  (span-gold annotated).
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
- `bdgt_sentenza_z11_548_2025.txt`: BDGT appellate tax judgment on sports-sponsorship
  deductions, with repeated statute partitions, Cassazione series, and Agenzia practice
  references (span-gold annotated).
- `bdgt_sentenza_v40_7014_2025.txt`: compact BDGT judgment on collection-agent standing
  and notification defects, with c.p.c., D.P.R. 600/1973, and Cassazione references
  (span-gold annotated).
- `bdgt_sentenza_v92_525_2025.txt`: longer BDGT inventory-accounting judgment with
  repeated first-instance anchors, paired article/comma lists, and a recent Cassazione
  order (span-gold annotated).
- `bdgt_sentenza_v10_2303_2026.txt`: BDGT judgment on prescription and COVID-era
  collection suspensions, combining decree-law and conversion-law references with
  Cassazione and Sezioni Unite decisions (span-gold annotated).
- `bdgt_sentenza_v46_885_2026.txt`: BDGT judgment on prescription and notification,
  with civil-code, c.p.c., tax-procedure, collection, and taxpayer-statute references
  (span-gold annotated).
- `bdgt_sentenza_z46_788_2026.txt`: BDGT appellate judgment on automated tax
  assessments and the specificity of grounds, with joined D.P.R. provisions and a
  varied Cassazione citation series (span-gold annotated).
- `cass_2018_12769_civ.txt`: Cassazione 2018 civil judgment with Corte costituzionale,
  old-style CGUE, and OCR-style `I.` law citations.
- `cass_2018_32458_pen.txt`: Cassazione 2018 criminal judgment with Rv. citations.
- `cass_2018_17793_tax_civ.txt`: Cassazione 2018 tax civil order on IRAP.
- `cass_2018_25504_tax_civ.txt`: Cassazione 2018 tax civil judgment on condono and
  procedural appeal grounds.
- `cass_2025_30680_civ.txt`: recent Cassazione civil decision on litigation costs, with
  c.p.c. partitions and a compact Constitutional/Cassazione citation series
  (span-gold annotated).
- `cass_2025_20045_civ.txt`: recent Cassazione employment decision on local-police
  classification, with appellate-decision anchors, c.p.c., public-employment law,
  Constitution, and court-fee provisions (span-gold annotated).
- `corte_conti_2016_220_sgven.txt`: Corte dei conti regional judgment.
- `corte_conti_2016_45_sgbas.txt`: Corte dei conti regional judgment.
- `corte_conti_2016_682_app3.txt`: Corte dei conti appellate judgment.
- `corte_conti_2024_36_app3.txt`: Corte dei conti appellate judgment with slash-heavy heading.
- `corte_cost_2010_368.txt`: Corte costituzionale judgment.
- `corte_cost_2020_281.txt`: Corte costituzionale judgment with regional-law and EU-law references.
- `corte_cost_2024_204.txt`: Corte costituzionale judgment with tax-justice organization references.
- `cgt1_bologna_2024_538.txt`: first-grade tax-court (CGT/CTP Bologna) judgment on R&D tax
  credits, with periodo partitions and a joined Sezioni Unite citation series.
- `cgt2_lombardia_2024_1229.txt`: second-grade tax-court (CGT/CTR Lombardia) appeal on
  COVID payment-term suspensions, dense in decreto-legge and conversion-law references.
- `cgue_62024cc0043_it.txt`: Italian CGUE Advocate General opinion with EU-law references.
- `cgue_62024cj0367_it.txt`: Italian CGUE judgment with Telenor case references and EU
  regulation anchors.
- `cgue_62025to0278_it.txt`: Italian General Court interim-measures order with TFUE
  partition lists and Court/General Court case-law anchors (span-gold annotated).
- `cgue_62014co0480_it.txt`: Italian Court of Justice order on gambling concessions,
  containing repeated TFUE citations and joined CJEU case references
  (span-gold annotated).
- `cerdef_ctr_veneto_2024_460.txt`: CERDEF tax judgment on advertising tax, mixing
  legacy CTR/modern CGT decisions, Cassazione orders, and legislation
  (span-gold annotated).
- `cerdef_ctr_toscana_2024_769.txt`: CERDEF tax judgment on the unified court fee for
  administrative-law additional grounds, with historical tax-court decision formats
  and Cassazione series (span-gold annotated).
- `cerdef_cass_2024_24701_civ.txt`: CERDEF Cassazione decision on first-home tax relief,
  combining tariff references, conversion legislation, c.p.c., and mixed Cassazione
  citation styles (span-gold annotated).
- `law_10_2020_body_tissue.txt`: national legislation text.
- `law_199_2025_budget.txt`: large national budget-law text.
- `law_dl_326_1987_spettacoli.txt`: national decree-law text with tariff-reference traps.
- `law_dpr_917_1986_tuir.txt`: legislation text for D.P.R. 917/1986 (TUIR).
- `law_dl_76_2020_art_34.txt`: article-level text from the deeply nested Normattiva
  corpus, covering CAD cross-references, conversion legislation, and GDPR
  (span-gold annotated).
- `law_dl_19_2020_art_2.txt`: article-level emergency-law text with conversion
  legislation, public-health powers, and a sequence of `21-bis`/`ter`/`quater`
  administrative-procedure partitions (span-gold annotated).
- `law_dl_18_2020_art_26.txt`: article-level COVID-19 sick-leave and quarantine text,
  exercising repeated letter lists, conversion legislation, and disability-law
  references (span-gold annotated).
- `massima_cass_2020_10019_civ.txt`: Cassazione civil massima (headnote) citing c.c. articles.
- `massima_cass_2020_10024_civ.txt`: Cassazione civil massima (headnote) citing c.c. articles.
- `prassi_ae_circolare_2020_18.txt`: Agenzia Entrate circolare (Credito d'imposta Vacanze)
  with DPCM, TUIR-alias, and AE provvedimento references.
- `prassi_ae_interpello_2025_26.txt`: Agenzia Entrate interpello.
- `prassi_ae_interpello_2025_10.txt`: Agenzia Entrate interpello with TUIR
  article 67 aliases and prassi resolution references.
- `prassi_ae_interpello_2026_103.txt`: recent Agenzia Entrate interpello with soft-hyphen
  OCR/normalization artifacts, Latin article suffixes, conversion legislation, TUIR,
  and a circular series (span-gold annotated).
- `prassi_ae_interpello_2026_129.txt`: Agenzia Entrate interpello on the EU
  interest-and-royalties regime, with directives, TUIR, cooperative-company provisions,
  soft hyphens, and practice references (span-gold annotated).
- `prassi_ae_interpello_2026_108.txt`: Agenzia Entrate interpello on first-home relief
  for collabent buildings, with a Cassazione series, ministerial decree, TUR provisions,
  and an earlier interpello reference (span-gold annotated).
- `prassi_ae_circolare_2001_22.txt`: historical Agenzia Entrate circular on the income
  treatment of listed property, mixing TAR, Consiglio di Stato, Cassazione, TUIR, and
  tax-procedure references (span-gold annotated).
- `prassi_minfin_circolare_1986_77.txt`: historical Ministry of Finance administrative
  practice from CERDEF, with legacy date styles and repeated statute partitions
  (span-gold annotated).
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

A document marked `span-gold annotated` has every resolved citation occurrence emitted by
the engine—repetitions and list/range expansions included—reviewed against its surrounding
source text and recorded in `tests/gold/full_document_spans.jsonl`. The exact occurrence and
anchor tests make additions/removals, changed normalization, and broadened/narrowed anchors
visible in future revisions.
