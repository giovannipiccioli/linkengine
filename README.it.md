# linkengine

*[English version](README.md)*

**Riconosce, analizza e normalizza le citazioni giuridiche italiane in identificativi stabili.**

`linkengine` legge testo giuridico italiano libero e trasforma ogni citazione che vi trova — una
legge, un decreto, una pronuncia giurisdizionale, un atto dell'Unione europea, una circolare
dell'amministrazione finanziaria — in un identificativo canonico leggibile dalla macchina
(**URN-NIR**, **ECLI**, **CELEX** o **PRAX**), insieme ai campi di riconoscimento estratti lungo
il percorso.

```python
from linkengine import LinkEngine

engine = LinkEngine()
for ref in engine.extract("Visto l'art. 2697 c.c. e la Cass. n. 100/2020, si applica il D.L. n. 34/2020.").rows:
    print(ref["text"], "->", ref["urn"])

# art. 2697 c.c   -> urn:nir:stato:regio.decreto:1942;262:2~art2697
# Cass. n. 100/2020 -> ECLI:IT:CASS:2020:100CIV
# D.L. n. 34/2020 -> urn:nir:stato:decreto.legge:2020;34
```

È **Python puro, senza dipendenze a runtime** (solo libreria standard) e autosufficiente: tutti i
dati di riferimento — autorità giudiziarie, tipi di atto, regioni, gli ~8 000 comuni italiani, gli
alias normativi — sono incorporati, quindi non serve alcuna rete né alcun servizio esterno.

---

## Funzionalità

- **Quattro schemi di identificazione**, scelti automaticamente per ciascun riferimento:
  | tipo | esempio di citazione | identificativo |
  |------|----------------------|----------------|
  | normativa nazionale / regionale | `art. 19 del d.lgs. 546/1992` | `urn:nir:stato:decreto.legislativo:1992;546~art19` |
  | giurisprudenza (autorità italiane) | `Cass. civ. n. 29036/2021` | `ECLI:IT:CASS:2021:29036CIV` |
  | atti UE e giurisprudenza della Corte di giustizia | `direttiva 2006/112/CE`, `causa C-123/20` | `CELEX:32006L0112`, `CELEX:62020CJ0123` |
  | prassi dell'amministrazione finanziaria | `Circolare AdE n. 25/E/2020` | `PRAX:AE:CIRC:2020:25` |

- **Segmentazione** — un periodo con più citazioni viene suddiviso in un riferimento per ciascuna,
  ed elenchi e intervalli vengono espansi (`artt. 15-18 DPR 600/73` → quattro articoli; `cause
  riunite C-1/20 e C-2/20` → un unico CELEX di cause riunite).
- **Partizioni** — articoli, commi, paragrafi, lettere, numeri e punti delle pronunce della Corte
  di giustizia vengono analizzati e accodati all'identificativo (`~art14-comma4-letb-num1`).
- **Alias e abbreviazioni** — codici e testi unici sia per denominazione estesa *sia* per
  abbreviazione (`codice civile`/`c.c.`, `c.p.c.`, `TUIR`, `GDPR`, `Cost.`, …), convenzioni contro
  le doppie imposizioni (`Convenzione Italia-Francia`) e leggi finanziarie e di bilancio annuali
  (`legge finanziaria 2008`, `legge di bilancio 2023`).
- **`urn_to_text`** — la mappa inversa: da un identificativo canonico a una citazione leggibile
  (`ECLI:IT:CASS:2020:1234CIV` → `"Cassazione civile n. 1234/2020"`).
- **Annotazione HTML** — restituisce il testo di partenza con ogni riferimento riconosciuto
  racchiuso in un tag che ne riporta i campi, così da *vedere* che cosa è stato colto.
- **Ancoraggi** — `reference_anchors` fornisce gli offset di carattere che stanno sotto quella
  resa, così un chiamante che produca qualcosa di diverso dall'HTML (span JSON, elementi `<a>`,
  evidenziazioni in un editor di testo) individua ogni citazione nel testo di origine senza doverla
  cercare di nuovo.
- **Contesto configurabile** — l'autorità giudicante per le autocitazioni (`questa Corte`), una
  regione predefinita per le leggi regionali non qualificate e come leggere un `regolamento` non
  altrimenti specificato.
- **Modalità normativa** — all'interno di un'unità normativa nota, risolve partizioni interne
  altrimenti prive di riferimento (`articolo 15`, `comma 2`, `presente articolo`) e segue in modo
  prudente un atto novellato espressamente nominato attraverso le formule più ricorrenti di
  sostituzione e inserimento.

---

## Convenzioni contro le doppie imposizioni

Una convenzione nominata identifica l'allegato della legge di ratifica che contiene il
testo italiano. L'allegato compare anche quando non è citato un articolo:

| Citazione | URN |
|---|---|
| `Convenzione Italia-Francia, art. 15` | `urn:nir:stato:legge:1992;20:1~art15` |
| `Convenzione Italia-India, art. 15` | `urn:nir:stato:legge:1995;319:2~art15` |
| `Convenzione Italia-Giappone` | `urn:nir:stato:legge:1972;855:1` |
| `Convenzione Italia-Cina` | `urn:nir:stato:legge:2024;182:1` |
| `Convenzione Italia-Cina del 1986` | `urn:nir:stato:legge:1989;376:1` |

La verifica su Normattiva del 26 ottobre 2026 copre 30 convenzioni. Il testo italiano di
[India](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1995-07-14;319:2~art1),
[Grecia](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1989-12-30;445:2~art1) e
[Cecoslovacchia](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1983-05-02;303:2~art1)
(anche sotto i nomi dei due Stati successori) usa `:2`. Per le altre convenzioni mappate si
usa `:1`; per quelle non verificate è un'assunzione predefinita, non una verifica della fonte.
I Paesi senza legge di ratifica nella tabella restano senza URN.

Per il Giappone la Convenzione è quella della legge **855/1972**. Il protocollo qualificato
come del **1980/1981**, o ratificato dalla legge **413/1981**, mantiene un'identità separata.
Per la Cina il riferimento senza data è il nuovo accordo del **2019**, legge **182/2024**.
Le date del **1986/1989** e i richiami alla legge **376/1989** collegati al nome della
convenzione selezionano l'accordo storico. Non si deduce la versione dall'anno della sentenza
o dal periodo d'imposta. Il vecchio testo cinese è grafico su Normattiva: un identificativo
di articolo non garantisce che il relativo testo sia disponibile nel corpus.

Le leggi citate direttamente (ad esempio `art. 1 della legge 20/1992`) conservano i propri
identificativi senza allegato implicito. Queste regole riguardano le nuove estrazioni:
LinkEngine non migra il corpus né i riferimenti già indicizzati.

---

## Installazione

```bash
pip install -e .            # da un clone di questo repository
# oppure, per lo sviluppo con gli extra di test:
pip install -e ".[test]"
```

`linkengine` richiede Python ≥ 3.8 e non ha dipendenze di terze parti a runtime.

---

## Avvio rapido

```python
from linkengine import LinkEngine, urn_to_text, annotate_html

engine = LinkEngine()

# 1) extract — un dizionario di campi per ciascun riferimento riconosciuto, con il suo `urn` canonico
result = engine.extract("art. 43, comma 1, del d.P.R. n. 600 del 1973")
row = result.rows[0]
row["urn"]        # 'urn:nir:presidente.repubblica:decreto:1973;600~art43-comma1'
row["doc-type"], row["number"], row["year"], row["partition"]
#               ('DECR', '600', '1973', 'articolo-43_comma-1')

# 2) rendere un identificativo di nuovo in forma testuale
urn_to_text("CELEX:32016R0679")          # 'regolamento (UE) 679/2016'
urn_to_text("PRAX:DIF:DIR:2012:2")       # 'direttiva Dipartimento delle Finanze n. 2/2012'
urn_to_text("DEL:COG274:2014:34")        # 'delibera del Comune di Palestrina n. 34/2014'

# 3) vedere che cosa è stato riconosciuto, nel contesto
annotate_html("Si vedano gli artt. 15-18 DPR 600/73.")
#  -> il testo con ogni articolo racchiuso in <span class="lkn-ref" data-urn=… …>…</span>
```

### Estrazione dalla normativa (modalità `normativa`)

La modalità predefinita resta prudente: un `articolo 15` isolato non è una citazione nella prosa
giuridica ordinaria. Quando si elabora una singola unità strutturale di normativa, si passa il suo
identificativo canonico:

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

L'ingresso è una stringa ordinaria e non richiede alcun formato di origine né alcun
pre-trattamento. La modalità va usata su una sola unità strutturale per volta. Le citazioni
esplicite seguono esattamente le stesse regole della modalità standard, mentre l'atto corrente fa
da ripiego per le partizioni che l'assemblaggio ordinario ha lasciato senza titolare. Le rubriche
strutturali `Art. N` non sono citazioni. Le unità nazionali usano il loro NIR esatto, comprensivo
della data di promulgazione completa; le unità UE usano un locatore CELEX canonico come
`CELEX:32016R0679~art17`.

Le *novelle* più ricorrenti sono ricondotte all'atto espressamente nominato. Nell'esempio che
segue, nessuno dei due riferimenti isolati appartiene al decreto in corso di elaborazione:

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

Si tratta deliberatamente di un risolutore di ambito, non di un analizzatore generale delle
modifiche normative. Gestisce soltanto un atto espressamente nominato, le formule di novella
prossime, i blocchi numerati e le virgolette bilanciate. Quando un estratto omette l'atto
novellato o l'attribuzione è genuinamente ambigua, il riferimento incompleto resta irrisolto
anziché essere collegato all'atto sbagliato. Le citazioni complete, comprese quelle contenute nel
testo sostitutivo, restano sul percorso di estrazione ordinario.

### Evidenziare i riferimenti in HTML

`annotate_html` restituisce il **testo originale** con ogni citazione riconosciuta evidenziata
(con lo stile di un collegamento). Il testo visibile non cambia; i campi estratti vivono soltanto
negli attributi `data-*` (li si ispeziona in DevTools o li si legge programmaticamente) — nulla
viene mostrato in linea.

Una funzione, due risultati, scelti con il flag `page`:

```python
from linkengine import LinkEngine, annotate_html

text = open("sentenza.txt").read()

# frammento in linea — da incorporare nella propria pagina o nel proprio template
annotate_html(text)

# documento autonomo completo — da scrivere direttamente su file e aprire nel browser
with open("sentenza.html", "w") as f:
    f.write(annotate_html(text, page=True))
```

Si passi `only_with_urn=True` per evidenziare soltanto le citazioni che si sono risolte in un
`urn`. Per riusare un'estrazione (o un motore già configurato), si passa il risultato:
`annotate_html(text, engine.extract(text))`.

### Individuare le citazioni nel testo di origine (`reference_anchors`)

L'HTML è un modo per presentare ciò che è stato riconosciuto; gli offset che vi stanno sotto sono
riutilizzabili. `reference_anchors` restituisce `[(start, end, [rows…]), …]` nell'ordine del
documento, dove `text[start:end]` è la superficie della citazione e le righe ne portano i campi.
Gli ancoraggi non si sovrappongono mai, quindi si possono percorrere in una sola passata per
ricostruire il testo con un proprio markup:

```python
from linkengine import LinkEngine, reference_anchors

text = "Si applica l'articolo 15, comma 1, lettere d), e), del d.lgs. 546/1992."

for start, end, rows in reference_anchors(text, only_with_urn=True):
    print(start, end, repr(text[start:end]), rows[0]["urn"])
# 13 45 'articolo 15, comma 1, lettere d)' ...:1992;546~art15-comma1-letd
# 47 70 'e), del d.lgs. 546/1992'          ...:1992;546~art15-comma1-lete
```

Ogni partizione riconosciuta conserva il proprio ancoraggio e il proprio identificativo, fino alla
lettera: un'elencazione *non* viene compattata. Le superfici non sono uniformi, come sopra: il
primo elemento di un elenco porta l'articolo e il comma, l'ultimo porta l'atto che identifica
l'intero elenco. Ciò che è garantito è che gli ancoraggi siano esatti, ordinati e non
sovrapposti, e che nessun riferimento venga perso o fuso con quello accanto. Le scelte di
presentazione — se un elenco di lettere meriti un collegamento o cinque, con quale granularità si
apra la destinazione — spettano al chiamante, non a questa libreria.

Le opzioni sono le stesse di `annotate_html`: `only_with_urn=True` per le sole citazioni risolte e
un `result` già calcolato per riusare un'estrazione o un motore configurato —
`reference_anchors(text, engine.extract(text, mode="normativa", current_unit_urn=urn))`.

### Configurare il contesto

```python
from linkengine import DocumentContext, LinkEngine

engine = LinkEngine()

# I metadati del documento si forniscono per singola estrazione, così un solo motore può
# elaborare atti di autorità diverse.
roma = DocumentContext(
    authority="CORTE_GIUST_TRIBUT_1", city="Roma", region="Lazio", document_year=2022)
engine.extract("questa Corte, sent. n. 50/2019", context=roma).rows[0]["urn"]
#  -> 'ECLI:IT:CGT1RM:2019:50'

lombardia = DocumentContext(authority="CORTE_GIUST_TRIBUT_2", region="Lombardia")
engine.extract("questa Corte, sent. n. 51/2019", context=lombardia).rows[0]["urn"]
#  -> 'ECLI:IT:CGT2LOM:2019:51'

# La regione del documento risolve anche una legge regionale non qualificata.
engine.extract(
    "art. 5 della legge regionale n. 4 del 2007", context=roma
).rows[0]["urn"]
#  -> 'urn:nir:regione.lazio:legge:2007;4~art5'

# Restano disponibili i valori predefiniti del costruttore e le sovrascritture per chiamata.
LinkEngine(default_authority="CORTE_CASS").extract(
    "questa Corte, sent. n. 50/2019"
).rows[0]["urn"]
#  -> 'ECLI:IT:CASS:2019:50CIV'
engine.extract(
    "questa Corte, sent. n. 50/2019", default_authority="CORTE_CASS"
).rows[0]["urn"]
#  -> 'ECLI:IT:CASS:2019:50CIV'

# Cassazione: la sezione civile o penale, quando la citazione non la indica
cass_pen = DocumentContext(authority="CORTE_CASS", chamber="PEN")
engine.extract("Sez. 1, n. 41738 del 19/10/2011", context=cass_pen).rows[0]["urn"]
#  -> 'ECLI:IT:CASS:2011:41738PEN'      (senza il contesto: ...41738CIV)
engine.extract("Cass. civ. n. 41738/2011", context=cass_pen).rows[0]["urn"]
#  -> 'ECLI:IT:CASS:2011:41738CIV'      la citazione dichiara la sua sezione: il contesto non si applica

# un "regolamento N/AAAA" isolato: nazionale (predefinito) o unionale
LinkEngine(default_regolamento_scope="comunitario").extract("il regolamento n. 123/2018").rows[0]["urn"]
#  -> 'CELEX:32018R0123'

# Le tolleranze per l'OCR sono attive per impostazione predefinita; si disattivano per
# un'analisi strettamente letterale
LinkEngine(ocr_accommodations=False).extract("artt. 7 I. 212/00").rows
#  -> []
```

`DocumentContext.authority` usa i codici stabili di `linkengine.catalog.COURTS`, come
`CORTE_CASS`, `CORTE_COST`, `CORTE_GIUST_TRIBUT_1`, `CORTE_GIUST_TRIBUT_2`, `COMM_TRIBUT_PROV`,
`COMM_TRIBUT_REG` e `TRIB_AMM_REG`. Non è, intenzionalmente, un analizzatore di denominazioni
libere. `city` accetta il nome di un comune o di una provincia italiana (`Reggio Calabria`) o il
suo codice ECLI (`RC`); `region` accetta il nome di una regione, il suo codice ECLI di tre lettere
(`LOM`) o il suo segmento URN (`lombardia`, `emilia.romagna`). I valori sconosciuti sollevano
`ValueError`.

Le corti di giustizia tributaria emettono le componenti ECLI distinte `CGT1` e `CGT2`; i
riferimenti storici a `COMM_TRIBUT_PROV` e `COMM_TRIBUT_REG` conservano `CTP` e `CTR`.

#### `authority="CORTE_COST"` — le autocitazioni della Corte

La Corte costituzionale cita le proprie pronunce con il solo numero e anno — «sentenza n. 269 del
2017» — senza nominare alcuna autorità, perché all'interno di una sua decisione ve n'è una sola.
È il suo stile redazionale: 308 occorrenze in 24 pronunce campionate, e la forma in cui compare la
gran parte dei suoi precedenti.

Altrove il contesto non può appropriarsi di una pronuncia priva di attribuzione: nella prosa
ordinaria «sentenza n. 123/2020» potrebbe essere di chiunque, e questo resta vero. Questa Corte è
l'eccezione, e poggia su un dato di fatto anziché su una presunzione: non ha né articolazione
territoriale né sezioni, quindi numero e anno identificano compiutamente una pronuncia. Si imposta
l'autorità e la forma si risolve:

```python
cost = DocumentContext(authority="CORTE_COST")
engine.extract("in senso conforme, la sentenza n. 269 del 2017", context=cost).rows[0]["urn"]
#  -> 'ECLI:IT:COST:2017:269'
```

Una citazione che nomini un'autorità è riconosciuta per la via ordinaria e non arriva mai qui. Tre
elementi escludono un numero non attribuito: il ruolo («registro ordinanze»), il numero di Gazzetta
Ufficiale con cui giunge ogni rimessione e qualunque menzione di una *sezione* — la Corte giudica
in collegio unico, sicché una sezione appartiene a un'autorità che ne ha, ed è ciò che impedisce a
un elenco di sbandare quando perde il nome dell'autorità dopo il primo elemento.

#### `cc_section` — la sezione della Corte dei conti

La Corte dei conti decide attraverso una cinquantina di collegi che numerano in modo autonomo, e il
suo ECLI porta il collegio decidente come suffisso del numero — `ECLI:IT:CONT:2023:89SGCAL`. Numero
e anno da soli non individuano quindi alcuna decisione, e una citazione che non indichi la sezione
resta irrisolta con i campi di riconoscimento valorizzati, anziché ricevere un identificativo che
non corrisponde a nulla.

`cc_section` fornisce la sezione del documento citante, così che le sue autocitazioni si risolvano:
circa un quinto di ciò che una decisione della Corte dei conti richiama è opera sua precedente:

```python
cc = DocumentContext(authority="CORTE_CONTI", cc_section="SGCAL")
engine.extract("questa Sezione n. 527/2009", context=cc).rows[0]["urn"]
#  -> 'ECLI:IT:CONT:2009:527SGCAL'
```

I valori sono i codici di `linkengine.catalog.CORTE_CONTI_SECTIONS`; uno sconosciuto solleva
`ValueError`. Come ogni altra autocitazione, colma soltanto il silenzio: una citazione che indichi
la propria sezione prevale sempre.

Ogni componente geografica di un codice di sezione è il codice standard di `geo.py` — la regione a
tre lettere (`SGCAL`, `SRCLOM`, `SSRRCOSAR`), oppure la sigla automobilistica della provincia per
una sezione che ha sede in una città anziché in una regione (`SGTN`, `SGBZ`, `SRCTN`, `SRCBZ`).
L'archivio della Corte non è coerente su questo punto, sicché tali identificativi sono di
linkengine e non del portale; in cambio, conoscere una regione significa conoscere il codice della
sua sezione.

#### `chamber` — la sezione civile o penale della Cassazione

`snciv` e `snpen` numerano le proprie decisioni in modo autonomo, sicché `Cass. n. 13808/2025`
individua due decisioni reali e distinte. La prassi citazionale italiana omette abitualmente la
sezione (`Sez. 1, n. 41738`), e nulla nella citazione consente di recuperarla: in assenza di
indizi il motore la legge come `CIV`, corretto per la grande maggioranza delle citazioni ma errato
per quasi tutte quelle contenute in una sentenza penale.

`chamber="PEN"` fornisce la sezione mancante a partire dal documento citante. È una presunzione,
adottata deliberatamente e delimitata da tre regole:

- **colma soltanto il silenzio** — `Cass. civ.`, `sez. trib.`, `sez. lavoro` e `Cass. pen.`
  dichiarano tutte la propria sezione e prevalgono sempre;
- **si fornisce soltanto `PEN`** — `CIV` è già il ripiego, quindi `chamber="CIV"` è accettato e non
  cambia alcun risultato;
- **nessun contesto, nessuna presunzione** — omettendolo, il comportamento resta invariato.

Di conseguenza una sezione *numerata* non porta con sé alcuna indicazione: `sez. V` produce la
sezione `5` (senza indicazione), e `5CIV` soltanto quando il testo dice `civ`/`trib`. Misurato su
150 sentenze penali, il contesto risolve il 95,8% delle loro citazioni di Cassazione verso la
gemella penale; il rischio residuo è una sentenza penale che citi una decisione genuinamente
civile, ipotesi che il corpus colloca prossima allo zero.

Per il resto il contesto è usato con prudenza: risolve le autocitazioni esplicite come `questa
Corte` e le leggi regionali non qualificate, ma non trasforma ogni `Sentenza n. 123/2020` isolata
in una decisione dell'autorità corrente. `document_year` è facoltativo; se fornito, una citazione
di un anno successivo resta un candidato irrisolto anziché ricevere un identificativo impossibile.
Si imposti `regional_law_region` quando il ripiego per le leggi regionali debba differire dalla
regione dell'autorità giudicante.

Le autorità della giustizia amministrativa identificano una decisione con il **tipo di
provvedimento** oltre che con il numero: ciascun tipo ha una propria numerazione, sicché `sentenza
n. 459/2023` e `ordinanza n. 459/2023` dello stesso TAR sono provvedimenti diversi. Il tipo si
ricava dalle parole della citazione, qualificazioni comprese — `ECLI:IT:TARBS:2023:459SENT`,
`ECLI:IT:CDS:2023:1251PDEF`, `decreto cautelare` → `DCAU` — e una citazione che non lo indichi è
letta come sentenza: esatto per l'85% degli identificativi costruiti su un campione di decisioni
reali. Autorità, anno e numero non vengono mai presunti, ma un tipo errato non dà sempre un
riferimento inesistente: il 41,5% delle terne autorità+anno+numero corrisponde a più tipi.
L'**Adunanza plenaria** del Consiglio di Stato (`Ad. Plen.`, `A.P.`) ha serie proprie, `APLE` e
`OPLE`: `Cons. Stato, Ad. Plen., n. 1/2022` è `ECLI:IT:CDS:2022:1APLE`, mentre `…:2022:1SENT` è
una sentenza della Sezione VI (l'archivio registra comunque come `SENT` 28 delle 264 sentenze
della plenaria). Un identificativo di TAR indica la **sede** che ha deciso, non la regione: `TAR
Lombardia, sezione staccata di Brescia` è `TARBS`, e una regione indicata da sola vale la sua
sede (`TAR Sicilia` → `TARPA`, Palermo), perché la sezione staccata viene esplicitata quando è
quella che ha deciso. Il Consiglio di Stato è `CDS` (anche come `Cons. St.`), il giudice
d'appello siciliano è `CGARS`, e il Trentino-Alto Adige non ha un TAR ma il `TRGA`, a Trento con
una sezione autonoma a Bolzano — indicato per sede, per regione e sede in qualunque ordine, o
per sola regione, che vale Trento.

La Corte dei conti risolve la propria sezione dalla citazione, in qualunque ordine essa si
presenti: `Sez. III App.`, `Prima Sezione Centrale d'Appello` e `Terza Sezione giurisdizionale
centrale d'appello` sono lette come sezioni, e così pure `Sez. contr. Lombardia`, `Sezioni riunite`
e `Sez. Autonomie`, che nominano l'autorità da sole. Il suo versante di controllo si pronuncia con
`deliberazione` e `parere`, e la relativa tipologia procedimentale fa parte dell'identificativo:
`deliberazione n. 102/2023/SRCPIE/PAR` → `ECLI:IT:CONT:2023:102SRCPIE-PAR`. La tipologia si ricava
dalla catena separata da barre comunque essa sia scritta (`9/SEZAUT/2009/INPR`, `130/PRSE/2012`,
`LOMBARDIA/164/2019/PAR`), e una citazione del versante di controllo che la ometta resta irrisolta.
Le sigle che accompagnano una citazione *giurisdizionale* (`n. 7/2007/QM`, `n. 11/2023/RGC`,
`n. 653/2013-A`) non fanno parte dell'identificativo e vengono scartate.

Per le corti di giustizia tributaria di secondo grado del Trentino-Alto Adige si includa
`city="Trento"` o `city="Bolzano"` nel contesto. I loro ECLI usano le componenti delle province
autonome `CGT2TN` e `CGT2BZ`; un contesto che indichi soltanto la regione è, intenzionalmente,
insufficiente.

### Ispezionare la pipeline

```python
res = engine.extract("art. 43 del d.P.R. n. 600/1973", debug=True)
res.references        # i riferimenti assemblati, con gli offset di carattere sul testo di origine
res.trace             # gli span prodotti da ciascun recognizer (debug=True)
```

---

## Come funziona

Il motore mantiene il testo in ingresso **immutabile** e vi accumula sopra un insieme tipizzato di
**span** (gli offset di carattere sono di prima classe — ideali per l'ancoraggio), poi assembla gli
span in riferimenti e costruisce l'identificativo di ciascun riferimento direttamente dai suoi
campi.

```
testo
 │  recognizers/         date · partizioni · numeri · tipi di atto · autorità ·
 ▼                       alias · convenzioni · leggi di bilancio · leggi regionali  → span tipizzati
span
 │  assembler            costruisce i frame tipizzati delle citazioni, assegna la titolarità di
 ▼                       slot e partizioni, poi ramifica e valida i riferimenti finali
riferimenti
 │  engine._fill_fields  campi di riconoscimento (ref-type, authority, doc-type, number, year,
 ▼                       partition, region/city, section, alias, …)
righe di campi
 │  urn.build_urn        identificativo canonico costruito direttamente dai campi
 ▼
righe con `urn`
```

### Mappa dei moduli (`linkengine/`)

| modulo | responsabilità |
|--------|----------------|
| `model.py` | il vocabolario degli span (`Entity`, `Span`, `Reference`, `ExtractResult`) e lo schema delle righe di campi |
| `context.py` | metadati validati, per documento, sull'autorità e sulla geografia |
| `normativa.py` | contesto validato dell'unità corrente (NIR/CELEX) e risoluzione dei locatori interni |
| `novelle.py` | classificazione prudente dell'ambito delle novelle, per i soli candidati della modalità normativa |
| `recognizers.py` | recognizer a espressioni regolari (date, numeri, tipi di atto, autorità, …) → span |
| `special_cases.py` | eccezioni lessicali circoscritte e nominate; le politiche strutturali non stanno qui |
| `partitions.py` | riconoscimento delle partizioni + segmentazione di intervalli ed elenchi |
| `assembler.py` | raggruppa gli span in riferimenti (legame, scissione, segmentazione) |
| `engine.py` | `LinkEngine` — esegue la pipeline e valorizza i campi di riconoscimento |
| `urn.py` | `build_urn(row)` e il renderer autonomo `urn_to_text(urn)` |
| `catalog.py` | la base di conoscenza: autorità (prefisso ECLI / geografia / denominazione), nomi dei tipi di atto, denominazioni degli alias |
| `aliases.py` | un record per ciascun alias normativo (riconoscimento + nir/celex + denominazione + ambito) |
| `conventions.py`, `budget_laws.py` | ricerche parametriche (convenzioni contro le doppie imposizioni; leggi di bilancio annuali) |
| `geo.py` | province / regioni / comuni ↔ codici (per la geografia degli ECLI) |
| `normalize.py` | costruzione e validazione di URN-NIR e CELEX |
| `html.py` | `reference_anchors(text)` — dove si colloca ciascuna citazione nel testo; `annotate_html(text, page=…)` — lo stesso, reso come HTML evidenziato |
| `runner.py` | `run_linkengine_string(text)` → CSV delle righe separato da barre verticali |

Ampliare la copertura è un'operazione localizzata: una nuova autorità va in `catalog.py`, un alias
in `aliases.py`, uno schema di riconoscimento in `recognizers.py`.

---

## Test e valutazione

Il comportamento è fissato da **gold set verificati a mano** (`tests/gold/`), valutati da
`tests/goldeval.py` (autosufficiente: usa soltanto il pacchetto):

- `gold_manual.csv` — recall sugli URN verificati a mano, per tutti i tipi di riferimento;
- `gold_partitions.csv` — catene profonde di articolo/comma/lettera/numero;
- `gold_precision.csv` — estratti di periodi interi valutati come insieme esatto (i falsi positivi
  contano);
- `gold_fields.jsonl` — per ciascuna citazione: la segmentazione attesa **e** ogni campo di
  riconoscimento.
- `gold_normativa.jsonl` — 81 estratti reali che coprono altrettante unità normative e decine di
  atti (statuti noti e atti ordinari, con i campioni casuali estratti a semi fissi), dal 1940 al
  2025, con sette tipi di atto e cinque autorità emananti. Alcune costruzioni non supportate
  restano come limiti misurati; la soglia protegge l'accuratezza complessiva senza pretendere che
  ogni forma sia analizzata.
- `gold_normativa_eu.jsonl` — 37 estratti reali che coprono unità normative e atti dell'Unione,
  regolamenti, direttive e decisioni sia noti sia ordinari, dal 1958 al 2025. Le citazioni esterne
  complete sono inoltre verificate per esatta identità con la modalità standard.
- `gold_normativa_novelle.jsonl` — 33 clausole di novella e note redazionali reali, tratte da 14
  unità normative italiane note e ordinarie, su 22 schemi e sette anni di origine. I casi
  supportati sono soglie di regressione esatte; 12 casi di limite nominati conservano il risultato
  semantico e documentano dove si ferma, per scelta, il piccolo risolutore di ambito.

- **gold su documenti interi** — ogni pronuncia di una famiglia di autorità citata in una decisione
  reale, letta a mano e verificata sull'archivio della stessa autorità:
  `gold_corte_conti_docs.jsonl` (20 documenti, 99 citazioni), `gold_giustizia_amm_docs.jsonl`
  (26 / 100), `gold_corte_cost_docs.jsonl` (15 / 163), `gold_merito_docs.jsonl` (22 / 24) e
  `gold_cassazione_docs.jsonl` (14 / 176). Elencano tanto le citazioni che il motore non riesce a
  raggiungere quanto quelle che raggiunge, sicché il recall registra fin dove arriva il
  riconoscimento anziché quanto gli è stato chiesto; la precisione è la metà con la soglia
  stringente. Le sentenze di merito sono state pseudonimizzate prima di essere incluse: il
  ministero sostituisce le parti, e i nomi, i dati di nascita, gli indirizzi e i numeri civici
  sopravvissuti a quella sostituzione sono qui segnaposto di ruolo.

```bash
pytest                          # test unitari + le soglie dei gold set
python -m tests.goldeval -v     # i punteggi dei gold set, con gli eventuali scarti
python -m tests.bench_full_docs  # throughput su documenti interi e unità di novella
```

---

## Notebook di esempio

[`examples/quickstart.ipynb`](examples/quickstart.ipynb) è una panoramica commentata ed eseguibile
della libreria: analisi, campi, segmentazione, identificativi, alias, contesto, modalità normativa
e output HTML.

---

## Come citare

Se si usa linkengine in lavori accademici, relazioni tecniche, dataset, benchmark o altri prodotti
della ricerca, si prega di citare la versione specifica utilizzata.

Formato di citazione consigliato:

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
Se il proprio stile BibTeX non supporta @software, si usi @misc.

---
## Riconoscimenti

linkengine è stata ispirata dalla libreria **Linkoln**, disponibile all'indirizzo
https://linkoln.gitlab.io/, sulla quale è stata inizialmente confrontata. Se si usa questa
libreria in lavori accademici, si prega di dare atto anche di quel progetto:

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

## Licenza

Apache License 2.0 — si veda [`LICENSE`](LICENSE).
