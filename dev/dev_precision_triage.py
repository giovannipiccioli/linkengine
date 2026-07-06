"""Dev triage harness for the precision-hardening pass (NOT shipped / not a gold gate).

Each case is (text, note). We print, per case, the references the engine currently produces:
the anchored `text`, the `urn` (or '∅'), and the salient fields. Use this to see current
behaviour and to verify fixes interactively. Run:

    PYTHONPATH=. python dev/dev_precision_triage.py [substring-filter]   (from the repo root)
"""
import sys
from linkengine import LinkEngine

CASES = [
    ("sentenza n. 11362/2023 del 07.06.2023 e depositata il 26.09.2023, emessa dalla Corte di Giustizia Tributaria di I grado di Roma",
     "authority CGT-I Roma not recognized; deposito date 26.09 must not bind; anchor too long"),
    ("la Suprema Corte con l'ordinanza n. 27639/2024",
     "'la Suprema Corte' -> Cassazione (THIS_COURT only w/ default); ordinanza n. 27639/2024"),
    ("in riferimento alla cartella n. 097 2019 0219012708000 atteso che riguarda infrazioni al codice della strada anno 2016",
     "anchor too long: should be just 'codice della strada'"),
    ("A partire dal 15 maggio 1998, data di entrata in vigore dell'art. 20 della legge n. 146 del 1998",
     "anchor too long: date 15 maggio 1998 should not be in the anchor"),
    ("poiche' non ricompreso nell'elencazione di cui all'art. 19 d.lgs. 546/92. Difatti ... ex art. 50 co. 2 DPR 602/73. La mancata eliminazione ... art. 19 cit.",
     "art. 19 should bind 546/92 not DPR 602/73; window too wide"),
    ("L'art. 16 del d.lgs. 46/99 ha sostituito l'intero Titolo II (artt. da 45 a 90) del d.p.r. 602 cit.",
     "artt 45-90 wrongly paired with 46/99 (should be d.p.r. 602)"),
    ("della Sezione tributaria della S.C. (Sez. 5, Ordinanza n. 22108 del 5/08/2024)",
     "authority S.C. not recognized"),
    ("cui fa espresso riferimento l'art. 19, comma 1, lett. e, del d.lgs. 31 dicembre 1992, n. 546, vedansi: Cass., Sez. Un., 31 marzo 2008, n. 8279;",
     "split at 2008 | n.8279 instead of one Cass ref 31 marzo 2008 n.8279"),
    ("pronuncia sentenza n. 124/2021 emessa dalla Commissione Tributaria Provinciale RIMINI sez. 2 e Sentenza n. 629/2025",
     "authority bound to 2nd sentenza wrongly"),
    ("per violazione dell'art. 13 comma 2 del DL 201/2011 e dell'art. 2 comma 1 lett. b del Dec. Leg.vo 504/1992,",
     "art 13 wrongly coupled with 2nd ref"),
    ("Violazione dell'art. 2 comma 1 lett. b del Dec. Leg.vo 504/1992, nonche' dell'art. 13 comma 2 del Dec. Legge 201/2011,",
     "art2 comma1 not part of ref; misattributed lett b"),
    ("Dec. Leg.vo 99/2004 a L. 296/2006 art. 1 comma 162, nonche' della L. 212/2000 (art. 7)",
     "Dec. Leg.vo not recognized; incorrect split"),
    ("23.3.2018. Va infine evidenziato che la regione E.R. con provvedimento 27.6.2022",
     "false positive: provvedimento 27.6.2022 should not be a citation"),
    ("31/1/2022 ai sensi dell'art.8 L.890/1982.",
     "leading date should not bind to reference"),
    ("licenza individuale speciale n.15/A2-2020 ex art.1 L.890/1992). Il 20/1/2022",
     "initial n.15/A2-2020 and trailing date should not bind"),
    ("data 8 settembre 2023, tramite la procedura informatica di cui al D.M. n. 701 del 1994 (\"Docfa\").",
     "date 8 settembre 2023 should not bind to D.M. 701/1994"),
    ("La Corte rappresentava, con riferimento al ricorso n. 315777/2024 presentato",
     "ricorso number must be ignored"),
    ("provvedimenti ritualmente notificati alla parte ricorrente in data 10/02/2025",
     "false positive: not a citation"),
    ("data dal 13 giugno 2006. Tuttavia, non risultando prodotto il provvedimento di sgravio",
     "false positive"),
    ("condannare l'Agenzia delle Entrate al rimborso IRPEF pari a euro 4.847,00 ... Sentenza n. 1470/2025 Depositato il 31/03/2025",
     "sentenza wrongly from Agenzia delle Entrate (AdE cannot emit sentenza)"),
    ("all'interpello n. 954-383/2008. Tuttavia, fa presente che con risposta n. 425/2023",
     "weird split before last number/year"),
    ("cassa o fondo di previdenza.\".Secondo Corte di Cassazione sentenza n. 27341 / 2024",
     "irrelevant initial part included in anchor"),
    ("ex art. 360 comma 1, n. 3, c.p.c., del D.L.vo n. 25 del 2008, art. 35 bis, commi 9, 10 e 11, come introdotti dalle disposizioni del D.L. n. 13 del 2017, art. 6, lett. g),",
     "comma 11 misattributed to 2nd citation"),
    ("dalla Commissione tributaria provinciale di Arezzo. 2. La Commissione tributaria regionale della Toscana, con la sentenza n. 763/16, pronunciata in data 24 marzo 2016 e pubblicata in data 21 aprile 2016, accoglieva",
     "CTP Arezzo wrongly included in the CTR sentenza ref"),
    ("artt. 6, secondo comma, 49 e 51 t.u.i.r.,", "missing art. 49 (may be too hard)"),
    ("previste dall'art. 1223 cod. civ. sono la r.g. n. 26388/2016",
     "a number wrongly assigned to cod. civ.; r.g. must be ignored"),
    ("enti a risoluzione del rapporto di lavoro v. Cass. 06/09/2013, n. 20482; Cass. 11/03/2003, n. 3582).",
     "messy partitioning"),
    ("avverso la sentenza n. 2990/2019 della CORTE D'APPELLO di MILANO, depositata il 04/07/2019 R.G.N. 2656/2018;",
     "trying to bind too much; R.G.N. 2656/2018 must be ignored"),
    ("la cassazione della sentenza (Cass. 3 luglio 2008, n. 18202, Cass. 19 agosto 2009, n. 18421; Cass. 22 settembre 2014, n. 19959; Cass. 23 gennaio 2019, n. 1845)",
     "messy split of 4 Cass citations"),
    ("richiesto dall'art. 111 Cost., comma 6 (Cass. 7 aprile 2017, n. 9105; Cass. 5 agosto 2019, n. 20921; Cass. 30 giugno 2020, n. 13248);",
     "messy split with missed cassazione"),
    ("D.Lgs. n. 251 del 2007, art. 3, del D.Lgs. n. 25 del 2008, art. 8 e art. 32, comma 3, del D.Lgs. n. 286 del 1998, art. 5, comma 6,",
     "art 8 misattributed to first ref; list of partitions only on one side"),
    ("artt. 2,10,29 e 30 Cost., dell'art. 8 CEDU,", "art. 8 wrongly attributed to COST"),
    ("avverso la sentenza del 11/11/2021 del GIP TRIBUNALE di PARMA", "binding too much stuff"),
    ("26/05/2022 ORDINANZA sul ricorso n. 22001-2021", "ricorso number must be ignored"),
    ("questa Corte (Sez. U n. 08241 del Ric. 2021 n. 22001)", "ricorso number must be ignored"),
    ("M3 - ad. 21-04-2022 -3- P.Q.M. Accoglie il ricorso, cassa la sentenza", "all false positive"),
    ("sentenza della Commissione tributaria regionale dell'Emilia Romagna n. 786/09/2018",
     "region Emilia-Romagna not recognized"),
    ("a legge 17 dicembre 2018, n. 136; rilevato che entro il 31 dicembre 2020",
     "binding useless part after citation"),
    ("23/05/2022 ORDINANZA sul ricorso iscritto al n. 26388/2016 R.G.", "R.G. -> ignore number"),
    ("d.l. 31 agosto 2016, n.168, conv. in legge 25 ottobre 2016, n.197,",
     "wrong split: number attributed to second law"),
    ("art.36, comma 2, n.4), d. lgs. 31/12/1992, n.546", "partition n.4 mistaken for doc number"),
    ("l'art.360, comma 1, n. 3 cod. proc. civ., in relazione all'art.6, comma 5, del d.lgs. 18/12/1997, n.472.",
     "messy split and numbers"),
    ("l'art.360, 1 comma, n.5, cod. proc. civ., e 54, comma 3, del d.l. 22/06/2012, n. 83,",
     "wrong split"),
    ("del 2 febbraio 2022 (in prosieguo: la \"decisione del 2 febbraio 2022\")",
     "no citation should be created"),
    ("Il 10 novembre 2021 la BCE ha inviato alla ricorrente un progetto di decisione",
     "false positive"),
    ("l'articolo 16, paragrafo 2, lettera d), del regolamento n. 1024/2013",
     "regolamento recognized as nazionale; maybe default EU or flag"),
    ("l'articolo 266 TFUE nonche' l'articolo 4, paragrafo 1, lettera f), e l'articolo 16, paragrafo 1, lettera c), e paragrafo 2, lettere d) e j), del regolamento n. 1024/2013.",
     "wrong binding of partitions to the two acts"),
    ("dalla BCE il 31 marzo 2021, e accrescendo formalmente la sua motivazione",
     "false positive"),
    ("impugna la sentenza emessa dalla Corte di Giustizia Tributaria di Primo grado di Modena n. XX/3/2024 del 10 gennaio 2024",
     "anonymized docket 'n. XX/3/2024' (CERDEF-style redaction): year stolen as the number -> spurious ECLI:IT:CGT1MO:2024:2024; should stay unresolved"),
    ("v. a titolo esemplificativo, Cass. 12.6.2024 n. 16285; Corte di giust. di primo grado di Milano 930/6/2024",
     "recall: 'Corte di giust. di primo grado di Milano 930/6/2024' (num/sez/year, no 'n.') not recognized -> missing ECLI:IT:CGT1MI:2024:930"),
]


def main():
    flt = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    eng = LinkEngine()
    for i, (text, note) in enumerate(CASES, 1):
        if flt and flt not in text.lower() and flt not in note.lower():
            continue
        rows = eng.extract(text).rows
        print(f"\n[{i:02d}] {note}")
        print(f"     TEXT: {text}")
        if not rows:
            print("     (no references)")
        for r in rows:
            urn = r.get("urn") or "∅"
            extra = {k: r[k] for k in ("doc-type", "authority", "other-authority", "alias",
                                       "number", "year", "partition", "doc-date", "case-number")
                     if r.get(k)}
            print(f"     - {r.get('text','')!r:50} {urn}")
            print(f"       {extra}")


if __name__ == "__main__":
    main()
