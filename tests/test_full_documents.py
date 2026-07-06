from pathlib import Path
from collections import Counter
from functools import lru_cache
import json
import re

from linkengine import LinkEngine


DOC_DIR = Path(__file__).with_name("benchmark_docs")
SPAN_GOLD = Path(__file__).with_name("gold") / "full_document_spans.jsonl"
SPAN_JACCARD_THRESHOLD = 0.82


@lru_cache(maxsize=None)
def _rows(name: str):
    text = (DOC_DIR / name).read_text(encoding="utf-8")
    return LinkEngine().extract(text).rows


@lru_cache(maxsize=1)
def _span_gold_rows():
    return [
        json.loads(line)
        for line in SPAN_GOLD.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def _jaccard(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def _best_unmatched_match(target, candidates, used):
    best = None
    for i, candidate in enumerate(candidates):
        if i in used or candidate["urn"] != target["urn"]:
            continue
        score = _jaccard(target["text"], candidate["text"])
        if best is None or score > best[0]:
            best = (score, i, candidate)
    return best


def _span_gold_docs():
    return sorted({row["doc"] for row in _span_gold_rows()})


def _span_gold_for(name: str):
    return [row for row in _span_gold_rows() if row["doc"] == name]


def _produced_span_rows(name: str):
    return [
        {"urn": row["urn"], "text": row["text"]}
        for row in _rows(name)
        if row["urn"]
    ]

EXPECTED_URNS = {
    "admin_tar_sicilia_2021_2023.txt": {
        "urn:nir:stato:decreto.legislativo:2000;267~art143-comma11",
        "urn:nir:stato:decreto.legge:2020;137~art25",
        "urn:nir:stato:legge:2009;94~art2-comma30",
    },
    "admin_tar_lazio_2026_2731.txt": {
        "ECLI:IT:TARLAZ:2026:1283",
        "ECLI:IT:TARLAZ:2026:4649",
        "urn:nir:stato:decreto.legislativo:2010;104:2~art30",
        "urn:nir:stato:decreto.legislativo:2010;104:2~art55",
    },
    "admin_consiglio_stato_2021_2023.txt": {
        "urn:nir:stato:decreto.legge:2020;137~art25",
        "urn:nir:stato:decreto.legge:2020;28~art4-comma1",
        "urn:nir:stato:decreto.legislativo:2010;104:2~art120",
        "urn:nir:stato:decreto.legislativo:2010;104:2~art35-comma1-letc",
        "urn:nir:stato:legge:2020;176",
        "urn:nir:stato:legge:2020;70",
    },
    "bdgt_sentenza_z46_8121_2022.txt": {
        "DM2012-07-05",
        "ECLI:IT:CASS:2016:13378CIV",
        "ECLI:IT:CASS:2018:10029CIV",
        "ECLI:IT:CASS:2022:4307CIV",
        "ECLI:IT:CONSSTATO:2018:67",
        "ECLI:IT:CTPPA:2016:6084",
        "PRAX:AE:CIRC:2013:31",
        "PRAX:AE:RIS:2010:132/E",
        "PRAX:AE:RIS:2016:58/E",
        "urn:nir:presidente.repubblica:decreto:1973;600~art36bis",
        "urn:nir:presidente.repubblica:decreto:1973;600~art43",
        "urn:nir:presidente.repubblica:decreto:1973;602~art38",
        "urn:nir:stato:legge:2000;388~art6",
        "urn:nir:stato:legge:2000;388~art6-comma13",
    },
    "bdgt_sentenza_v28_898_2022.txt": {
        "ECLI:IT:CASS:2005:9135CIV",
        "ECLI:IT:CASS:2006:25506CIV",
        "ECLI:IT:CASS:2016:12377CIV",
        "ECLI:IT:CASS:2017:12273CIV",
        "ECLI:IT:CASS:2019:21080CIV",
        "ECLI:IT:CASS:2020:6702CIV",
        "urn:nir:stato:decreto.legislativo:1992;504~art2-comma1-letb",
        "urn:nir:stato:decreto.legislativo:1992;504~art5",
        "urn:nir:stato:decreto.legislativo:1992;504~art5-comma5",
        "urn:nir:stato:decreto.legislativo:1997;446~art52",
        "urn:nir:stato:decreto.legislativo:1997;446~art59",
        "urn:nir:stato:decreto.legislativo:2000;267~art48",
        "urn:nir:stato:decreto.legge:2005;203~art11quater-comma16",
        "urn:nir:stato:decreto.legge:2006;223~art36-comma2",
        "urn:nir:stato:legge:2006;248",
        "urn:nir:stato:legge:2000;212~art7",
    },
    "bdgt_sentenza_u01_106_2022.txt": {
        "ECLI:IT:CASS:2008:5791CIV",
        "ECLI:IT:CASS:2017:17694CIV",
        "ECLI:IT:CASS:2021:10012CIV",
        "urn:nir:presidente.repubblica:decreto:1973;600~art65",
        "urn:nir:presidente.repubblica:decreto:1973;600~art65-comma2",
        "urn:nir:stato:regio.decreto:1940;1443:1~art140",
    },
    "bdgt_sentenza_u01_110_2022.txt": {
        "urn:nir:stato:decreto.legge:1990;167~art4",
        "urn:nir:stato:decreto.legge:2009;78~art12-comma2",
    },
    "bdgt_sentenza_u59_465_2022.txt": {
        "ECLI:IT:CASS:2007:6197CIV",
        "ECLI:IT:CASS:2009:9519CIV",
        "ECLI:IT:CASS:2011:2214CIV",
        "ECLI:IT:CASS:2011:5076CIV",
        "ECLI:IT:CASS:2012:17928CIV",
        "ECLI:IT:CASS:2013:441CIV",
        "ECLI:IT:CASS:2015:5925CIV",
        "ECLI:IT:CASS:2017:27778CIV",
        "ECLI:IT:CASS:2018:30069CIV",
        "ECLI:IT:CASS:2018:32959CIV",
        "ECLI:IT:CASS:2019:27049CIV",
        "ECLI:IT:CASS:2019:30351CIV",
        "ECLI:IT:CASS:2019:33976CIV",
        "ECLI:IT:CASS:2021:14242CIV",
        "ECLI:IT:CASS:2021:24820CIV",
        "ECLI:IT:CASS:2022:3307CIV",
        "ECLI:IT:CASS:2022:8652CIV",
        "ECLI:IT:CTPMO:2021:32",
        "urn:nir:presidente.repubblica:decreto:1973;600~art14-letd",
        "urn:nir:presidente.repubblica:decreto:1973;600~art39-comma1-letd",
        "urn:nir:presidente.repubblica:decreto:1973;600~art41bis",
        "urn:nir:presidente.repubblica:decreto:1986;917~art47-comma1",
        "urn:nir:presidente.repubblica:decreto:1986;917~art67-comma1-letc",
        "urn:nir:stato:decreto.legge:2018;119",
        "urn:nir:stato:decreto.legge:2018;119~art1",
        "urn:nir:stato:decreto.legge:2018;119~art1-comma4",
        "urn:nir:stato:decreto.legge:2019;119~art1",
        "urn:nir:stato:decreto.legislativo:1992;546~art15-comma2septies",
        "urn:nir:stato:decreto.legislativo:1997;471",
        "urn:nir:stato:decreto.legislativo:1997;472",
        "urn:nir:stato:regio.decreto:1942;262:2~art2727",
    },
    "bdgt_sentenza_z01_745_2022.txt": {
        "ECLI:IT:CASS:2015:2241CIV",
        "ECLI:IT:CASS:2019:16524CIV",
        "ECLI:IT:CASS:2020:8080CIV",
        "ECLI:IT:CASS:2022:11431CIV",
        "ECLI:IT:CONSSTATO:2016:882",
        "ECLI:IT:CTPSI:2019:163",
        "ECLI:IT:CTRTOS:2018:1761",
        "ECLI:IT:CTRTOS:2018:1985",
        "urn:nir:regione.toscana:legge:1994;34",
        "urn:nir:regione.toscana:legge:1994;34~art28",
        "urn:nir:regione.toscana:legge:2012;79",
        "urn:nir:regione.toscana:legge:2012;79~art4-comma1-letc",
        "urn:nir:regione.toscana:legge:2012;79~art22",
        "urn:nir:regione.toscana:legge:2012;79~art23",
        "urn:nir:regione.toscana:legge:2012;79~art26",
        "urn:nir:regione.toscana:legge:2012;79~art28",
        "urn:nir:stato:decreto.legislativo:1999;46~art17-comma3",
        "urn:nir:stato:legge:2005;246~art14-comma14",
        "urn:nir:stato:legge:2005;246~art14-comma14ter",
        "urn:nir:stato:regio.decreto:1933;215~art1",
        "urn:nir:stato:regio.decreto:1933;215~art10",
        "urn:nir:stato:regio.decreto:1933;215~art10-comma2",
        "urn:nir:stato:regio.decreto:1933;215~art21",
        "urn:nir:stato:regio.decreto:1942;262:2~art860",
    },
    "bdgt_sentenza_z55_3804_2022.txt": {
        "ECLI:IT:CASS:2008:5791CIV",
        "ECLI:IT:CASS:2009:10672CIV",
        "ECLI:IT:CASS:2011:9873CIV",
        "ECLI:IT:CASS:2012:14861CIV",
        "ECLI:IT:CASS:2015:16952CIV",
        "urn:nir:stato:decreto.legislativo:1992;546~art19",
        "urn:nir:stato:decreto.legislativo:1992;546~art19-comma3",
        "urn:nir:stato:regio.decreto:1940;1443:1~art100",
    },
    "cass_2018_12769_civ.txt": {
        "CELEX:61981CJ0052~num27",
        "CELEX:61981CJ0245~num27",
        "CELEX:61985CJ0424~num33",
        "CELEX:61988CJ0350",
        "ECLI:IT:CASS:2010:11722CIV",
        "ECLI:IT:CASS:2013:3754CIV",
        "ECLI:IT:CASS:2014:25773CIV",
        "ECLI:IT:CASS:2014:8998CIV",
        "ECLI:IT:CASS:2016:332CIV",
        "ECLI:IT:COST:2014:236",
        "ECLI:IT:COST:2017:149",
        "urn:nir:presidente.repubblica:decreto:1972;633~art56",
        "urn:nir:presidente.repubblica:decreto:1973;600~art42",
        "urn:nir:stato:legge:1990;241~art21octies",
        "urn:nir:stato:legge:2000;212~art7",
        "urn:nir:stato:regio.decreto:1940;1443:1~art360-comma1-num3",
        "urn:nir:stato:regio.decreto:1940;1443:1~art360-comma1-num5",
    },
    "cass_2018_32458_pen.txt": {
        "ECLI:IT:CASS:2011:41738CIV",
        "ECLI:IT:CASS:2014:9930CIV",
        "urn:nir:stato:regio.decreto:1930;1398:1~art240",
        "urn:nir:stato:decreto.del.presidente.della.repubblica:1988;447~art129",
        "urn:nir:stato:decreto.del.presidente.della.repubblica:1988;447~art173-comma1",
        "urn:nir:stato:decreto.del.presidente.della.repubblica:1988;447~art444",
        "urn:nir:stato:decreto.del.presidente.della.repubblica:1988;447~art445",
    },
    "cass_2018_17793_tax_civ.txt": {
        "ECLI:IT:CASS:2016:9451CIV",
        "urn:nir:stato:decreto.legislativo:1997;446~art2",
        "urn:nir:stato:decreto.legislativo:1997;446~art2-comma1",
        "urn:nir:stato:decreto.legislativo:1997;446~art3-comma1-letc",
    },
    "cass_2018_25504_tax_civ.txt": {
        "ECLI:IT:CASS:2010:20745CIV",
        "ECLI:IT:CASS:2011:795CIV",
        "urn:nir:stato:legge:2002;289",
        "urn:nir:stato:legge:2002;289~art9bis",
        "urn:nir:stato:regio.decreto:1940;1443:1~art346",
        "urn:nir:stato:regio.decreto:1940;1443:1~art360-comma1-num3",
        "urn:nir:stato:regio.decreto:1940;1443:1~art360-comma1-num4",
        "urn:nir:stato:regio.decreto:1940;1443:1~art360-comma1-num5",
    },
    "corte_conti_2016_220_sgven.txt": {
        "CELEX:32007D4247",
        "ECLI:IT:CASS:2009:20434CIV",
        "ECLI:IT:CASS:2011:17212CIV",
        "ECLI:IT:CASS:2011:4748CIV",
        "ECLI:IT:CCONTI:2016:220",
        "urn:nir:stato:legge:1994;19~art5",
        "urn:nir:stato:legge:1996;639",
        "urn:nir:stato:regio.decreto:1930;1398:1~art316",
        "urn:nir:stato:regio.decreto:1940;1443:1~art91",
        "urn:nir:stato:regio.decreto:1940;1443:1~art140",
    },
    "corte_conti_2016_45_sgbas.txt": {
        "ECLI:IT:CCONTI:2012:2443",
        "ECLI:IT:CCONTI:2016:45",
        "urn:nir:presidente.repubblica:decreto:1973;1092~art204",
        "urn:nir:stato:decreto.legislativo:1997;165",
        "urn:nir:stato:decreto.legislativo:2003;196~art52",
        "urn:nir:stato:decreto.legislativo:2010;66~art923",
        "urn:nir:stato:legge:1954;599~art28",
        "urn:nir:stato:legge:1954;599~art29",
        "urn:nir:stato:legge:1954;599~art37-comma2",
        "urn:nir:stato:legge:1961;1168",
        "urn:nir:stato:legge:1997;449~art59-comma6",
    },
    "corte_conti_2016_682_app3.txt": {
        "ECLI:IT:CASS:2015:2087CIV",
        "ECLI:IT:CASS:2016:476CIV",
        "ECLI:IT:CCONTI:2012:135",
        "ECLI:IT:CCONTI:2016:682",
        "urn:nir:presidente.repubblica:decreto:1973;1092~art204",
        "urn:nir:presidente.repubblica:decreto:1973;1092~art205",
        "urn:nir:presidente.repubblica:decreto:1973;1092~art206",
        "urn:nir:presidente.repubblica:decreto:1973;1092~art207",
        "urn:nir:presidente.repubblica:decreto:1973;1092~art208",
        "urn:nir:presidente.repubblica:decreto:1986;538~art7",
        "urn:nir:presidente.repubblica:decreto:1986;538~art8",
        "urn:nir:stato:regio.decreto:1933;1038~art1",
        "urn:nir:stato:regio.decreto:1933;1038~art2",
        "urn:nir:stato:regio.decreto:1940;1443:1~art342",
        "urn:nir:stato:regio.decreto:1942;262:2~art1218",
        "urn:nir:stato:regio.decreto:1942;262:2~art1227",
        "urn:nir:stato:regio.decreto:1942;262:2~art2056",
    },
    "corte_conti_2024_36_app3.txt": {
        "ECLI:IT:CCONTI:2024:36",
        "urn:nir:presidente.repubblica:decreto:1973;1092~art54",
        "urn:nir:presidente.repubblica:decreto:1973;1092~art54-comma1",
        "urn:nir:stato:decreto.legislativo:2003;196~art52",
        "urn:nir:stato:legge:1995;335",
        "urn:nir:stato:legge:1995;335~art1-comma12",
    },
    "corte_cost_2010_368.txt": {
        "ECLI:IT:COST:2010:368",
        "urn:nir:stato:costituzione~art111",
        "urn:nir:stato:costituzione~art24",
        "urn:nir:stato:costituzione~art3",
        "urn:nir:stato:costituzione~art97",
        "urn:nir:stato:decreto.legge:2005;35~art2-comma3-lete",
        "urn:nir:stato:decreto.legislativo:2000;267~art159",
        "urn:nir:stato:legge:1865;2248~art4",
        "urn:nir:stato:legge:2005;80",
        "urn:nir:stato:regio.decreto:1940;1443:1~art517",
        "urn:nir:stato:regio.decreto:1940;1443:1~art546-comma1",
        "urn:nir:stato:regio.decreto:1940;1443:1~art553",
    },
    "corte_cost_2020_281.txt": {
        "CELEX:31992L0043",
        "CELEX:31992L0043~all1",
        "CELEX:32009L0147",
        "ECLI:IT:COST:2020:281",
        "urn:nir:ministero:decreto:2015;70",
        "urn:nir:ministero:decreto:2015;70:1~punto9",
        "urn:nir:presidente.repubblica:decreto:1997;357",
        "urn:nir:presidente.repubblica:decreto:1997;357~art4",
        "urn:nir:regione.friuli.venezia.giulia:legge:2009;17~art12",
        "urn:nir:regione.friuli.venezia.giulia:legge:2019;9~art45-comma1-letb",
        "urn:nir:regione.friuli.venezia.giulia:legge:2019;9~art88",
        "urn:nir:stato:costituzione~art117-comma2-lets",
        "urn:nir:stato:costituzione~art3",
        "urn:nir:stato:decreto.legislativo:1998;286~art40",
        "urn:nir:stato:legge.costituzionale:1963;1~art5-num16",
        "urn:nir:stato:legge:1992;157",
    },
    "corte_cost_2024_204.txt": {
        "CELEX:12012P/TXT~art47",
        "CONV_EU_DIR_UOMO~art6-num1",
        "ECLI:IT:CASS:2021:16180CIV",
        "ECLI:IT:COST:2024:204",
        "urn:nir:stato:costituzione~art101",
        "urn:nir:stato:costituzione~art104",
        "urn:nir:stato:costituzione~art108",
        "urn:nir:stato:costituzione~art111",
        "urn:nir:stato:costituzione~art117",
        "urn:nir:stato:costituzione~art97",
        "urn:nir:stato:decreto.legge:2011;98~art39",
        "urn:nir:stato:decreto.legge:2023;44~art20-comma2bis",
        "urn:nir:stato:decreto.legge:2023;44~art20-comma2ter",
        "urn:nir:stato:decreto.legislativo:1992;545",
        "urn:nir:stato:decreto.legislativo:1992;545~art11-comma1",
        "urn:nir:stato:decreto.legislativo:1992;545~art13",
        "urn:nir:stato:decreto.legislativo:1992;545~art15-comma1",
        "urn:nir:stato:decreto.legislativo:1992;545~art1bis",
        "urn:nir:stato:decreto.legislativo:1992;545~art24-comma1-letd",
        "urn:nir:stato:decreto.legislativo:1992;545~art24-comma1-lete",
        "urn:nir:stato:decreto.legislativo:1992;545~art24-comma2bis",
        "urn:nir:stato:decreto.legislativo:1992;545~art31",
        "urn:nir:stato:decreto.legislativo:1992;545~art32-comma1",
        "urn:nir:stato:decreto.legislativo:1992;545~art32-comma2",
        "urn:nir:stato:decreto.legislativo:1992;545~art34",
        "urn:nir:stato:decreto.legislativo:1992;545~art37",
        "urn:nir:stato:decreto.legislativo:2015;156~art11",
        "urn:nir:stato:legge:1991;413~art30",
        "urn:nir:stato:legge:2011;111",
        "urn:nir:stato:legge:2014;23~art6-comma6",
        "urn:nir:stato:legge:2022;130",
        "urn:nir:stato:legge:2022;130~art1-comma10",
        "urn:nir:stato:legge:2022;130~art1-comma14",
        "urn:nir:stato:legge:2022;130~art8",
        "urn:nir:stato:legge:2022;130~art8-comma5",
        "urn:nir:stato:legge:2023;74",
        "urn:nir:stato:regio.decreto:1940;1443:1~art51",
    },
    "cgue_62024cc0043_it.txt": {
        "CELEX:12012E/TXT~art21-num1",
        "CELEX:12012P/TXT~art45-num1",
        "CELEX:32004L0038~art4-num3",
        "CELEX:32019R1157",
        "CELEX:62004CJ0423~num45",
        "CELEX:62016CJ0673",
        "CELEX:62024CJ0043",
    },
    "cgue_62024cj0367_it.txt": {
        "CELEX:32002L0022",
        "CELEX:32012R0531",
        "CELEX:32015R2120",
        "CELEX:32015R2120~art3",
        "CELEX:62018CJ0807~num47",
        "CELEX:62019CJ0039~num47",
        "CELEX:62020CJ0034",
        "CELEX:62020CJ0034~num26",
        "CELEX:62020CJ0034~num32",
        "CELEX:62024CJ0367",
    },
    "law_10_2020_body_tissue.txt": {
        "urn:nir:presidente.repubblica:decreto:1990;285",
        "urn:nir:presidente.repubblica:decreto:2000;396",
        "urn:nir:stato:decreto.legge:2012;158~art12-comma10",
        "urn:nir:stato:decreto.legge:2012;158~art12-comma11",
        "urn:nir:stato:decreto.legislativo:2003;211",
        "urn:nir:stato:legge:1983;184",
        "urn:nir:stato:legge:1988;400~art17-comma1-letb",
        "urn:nir:stato:legge:1993;578",
        "urn:nir:stato:legge:2012;189",
        "urn:nir:stato:legge:2017;205~art1-comma418",
        "urn:nir:stato:legge:2017;219~art4-comma6",
        "urn:nir:stato:legge:2018;3~art2",
        "urn:nir:stato:legge:2020;10",
        "urn:nir:stato:regio.decreto:1933;1592",
    },
    "law_199_2025_budget.txt": {
        "CELEX:12012E/TXT~art123",
        "CELEX:12012E/TXT~art127",
        "CELEX:12012E/TXT~art130",
        "CELEX:32023R1114~art3-num1-num7",
        "urn:nir:presidente.consiglio.ministri:decreto:2013;159",
        "urn:nir:presidente.repubblica:decreto:1986;131",
        "urn:nir:presidente.repubblica:decreto:1986;917",
        "urn:nir:presidente.repubblica:decreto:1986;917~art11-comma1-letb",
        "urn:nir:presidente.repubblica:decreto:1986;917~art16ter",
        "urn:nir:presidente.repubblica:decreto:1986;917~art24bis-comma2",
        "urn:nir:presidente.repubblica:decreto:1986;917~art43-comma2-periodo1",
        "urn:nir:presidente.repubblica:decreto:1986;917~art51-comma2-letc",
        "urn:nir:presidente.repubblica:decreto:1986;917~art67-comma1-letcsexies",
        "urn:nir:presidente.repubblica:decreto:1988;148",
        "urn:nir:presidente.repubblica:decreto:1998;322",
        "urn:nir:stato:decreto.legge:2003;269",
        "urn:nir:stato:decreto.legge:2011;70~art5-comma10",
        "urn:nir:stato:decreto.legge:2011;201~art5-comma1",
        "urn:nir:stato:decreto.legge:2013;63",
        "urn:nir:stato:decreto.legge:2013;149~art11",
        "urn:nir:stato:decreto.legge:2020;34~art119-comma4-periodo5",
        "urn:nir:stato:decreto.legge:2024;63~art5-comma2quater",
        "urn:nir:stato:decreto.legislativo:1997;241~art17",
        "urn:nir:stato:decreto.legislativo:1997;281~art8",
        "urn:nir:stato:decreto.legislativo:2003;66~art1-comma2",
        "urn:nir:stato:decreto.legislativo:2024;174",
        "urn:nir:stato:legge:1985;47",
        "urn:nir:stato:legge:1994;724",
        "urn:nir:stato:legge:2003;326",
        "urn:nir:stato:legge:2009;196~art21-comma1ter-leta",
        "urn:nir:stato:legge:2011;106",
        "urn:nir:stato:legge:2011;214",
        "urn:nir:stato:legge:2014;13",
        "urn:nir:stato:legge:2014;190~art1-comma154",
        "urn:nir:stato:legge:2015;208~art1-comma182",
        "urn:nir:stato:legge:2016;232~art1-comma44-periodo2",
        "urn:nir:stato:legge:2020;77",
        "urn:nir:stato:legge:2020;178~art1-comma595-periodo1",
        "urn:nir:stato:legge:2022;197~art1-comma450",
        "urn:nir:stato:legge:2022;197~art1-comma451bis",
        "urn:nir:stato:legge:2024;101",
        "urn:nir:stato:legge:2024;207~art1-comma385",
        "urn:nir:stato:legge:2025;76~art6-comma1-periodo3",
        "urn:nir:stato:legge:2025;199",
        "urn:nir:stato:regio.decreto:1942;262:2~art43",
    },
    "law_dl_326_1987_spettacoli.txt": {
        "urn:nir:presidente.repubblica:decreto:1972;640",
        "urn:nir:presidente.repubblica:decreto:1973;602~art38-comma2",
        "urn:nir:presidente.repubblica:decreto:1977;954~art3",
        "urn:nir:stato:costituzione~art77",
        "urn:nir:stato:costituzione~art87",
        "urn:nir:stato:decreto.legge:1982;697~art7-comma1",
        "urn:nir:stato:decreto.legge:1986;2~art1bis-comma1",
        "urn:nir:stato:decreto.legge:1987;326",
        "urn:nir:stato:decreto.legge:1987;326~art1-comma4quater",
        "urn:nir:stato:legge:1975;656",
        "urn:nir:stato:legge:1982;887",
        "urn:nir:stato:legge:1987;403",
    },
    "law_dpr_917_1986_tuir.txt": {
        "CELEX:32019R1238",
        "urn:nir:presidente.repubblica:decreto:1986;917",
        "urn:nir:presidente.repubblica:decreto:1986;917~art8",
        "urn:nir:stato:decreto.legge:1989;69",
        "urn:nir:stato:decreto.legge:1995;41",
        "urn:nir:stato:decreto.legge:2006;223",
        "urn:nir:stato:decreto.legge:2011;138",
        "urn:nir:stato:decreto.legislativo:2003;344~art2-comma4",
        "urn:nir:stato:decreto.legislativo:2017;116~art29",
        "urn:nir:stato:legge:1989;154~art38-comma1",
        "urn:nir:stato:legge:1995;85~art29-comma2",
        "urn:nir:stato:legge:2000;212~art3-comma1",
        "urn:nir:stato:legge:2006;248~art36-comma28",
        "urn:nir:stato:legge:2007;244~art1-comma30",
        "urn:nir:stato:legge:2011;148~art2-comma2",
        "urn:nir:stato:legge:2018;145~art1-comma24",
        "urn:nir:stato:legge:2025;51",
    },
    "prassi_ae_risoluzione_2017_146.txt": {
        "DM2016-05-26~art3",
        "PRAX:AE:CIRC:2004:22",
        "PRAX:AE:CIRC:2011:4",
        "PRAX:AE:CIRC:2017:17",
        "urn:nir:presidente.repubblica:decreto:1986;917~art2",
        "urn:nir:presidente.repubblica:decreto:1986;917~art50-comma1-lete",
        "urn:nir:stato:decreto.legge:2003;269~art3",
        "urn:nir:stato:decreto.legislativo:1999;517~art5-comma2",
        "urn:nir:stato:decreto.legislativo:2015;147~art16",
        "urn:nir:stato:decreto.legge:2010;78~art44",
        "urn:nir:stato:legge:2000;212~art11",
        "urn:nir:stato:legge:2014;190~art1-comma14-leta",
        "urn:nir:stato:legge:2016;232~art1-comma149",
    },
    "prassi_ae_interpello_2025_26.txt": {
        "urn:nir:stato:decreto.legge:2020;34~art119",
        "urn:nir:stato:decreto.legge:2020;34~art119-comma8bis",
        "urn:nir:stato:decreto.legge:2020;34~art119-comma13ter",
        "urn:nir:stato:decreto.legge:2020;34~art121",
        "urn:nir:stato:decreto.legge:2020;34~art121-comma1bis",
        "urn:nir:stato:decreto.legge:2023;11",
        "urn:nir:stato:decreto.legge:2023;11~art2",
        "urn:nir:stato:decreto.legge:2023;11~art2-comma2",
        "urn:nir:stato:decreto.legge:2023;11~art2-comma3",
        "urn:nir:stato:decreto.legge:2024;39",
        "urn:nir:stato:decreto.legge:2024;39~art1",
        "urn:nir:stato:decreto.legge:2024;39~art1-comma5",
        "urn:nir:stato:legge:2020;77",
        "urn:nir:stato:legge:2023;38",
        "urn:nir:stato:legge:2024;67",
    },
    "prassi_ae_interpello_2025_10.txt": {
        "PRAX:AE:RIS:2007:105/E",
        "PRAX:AE:RIS:2009:23/E",
        "urn:nir:presidente.repubblica:decreto:1986;917",
        "urn:nir:presidente.repubblica:decreto:1986;917~art67-comma1-letb",
    },
    "prassi_ae_risoluzione_2025_13.txt": {
        "ECLI:IT:CASS:2021:11925CIV",
        "ECLI:IT:CASS:2023:29842CIV",
        "ECLI:IT:CASS:2023:31530CIV",
        "ECLI:IT:CASS:2023:31590CIV",
        "ECLI:IT:CASS:2023:33442CIV",
        "ECLI:IT:CASS:2024:15727CIV",
        "PRAX:AE:CIRC:2012:27",
        "urn:nir:presidente.repubblica:decreto:1986;131",
        "urn:nir:stato:decreto.legislativo:2019;14",
        "urn:nir:stato:decreto.legislativo:2019;14~art240",
        "urn:nir:stato:regio.decreto:1942;262:2~art1273",
        "urn:nir:stato:regio.decreto:1942;267~art124",
        "urn:nir:stato:regio.decreto:1986;131~art21-comma2",
    },
    "prassi_dogane_circolare_2017_8.txt": {
        "urn:nir:stato:decreto.del.presidente.della.repubblica:1988;447~art444",
        "urn:nir:stato:decreto.legge:2006;262~art1-comma1-leta",
        "urn:nir:stato:decreto.legislativo:1995;504",
        "urn:nir:stato:decreto.legislativo:1995;504~art8-comma1",
        "urn:nir:stato:decreto.legislativo:1995;504~art10-comma2-leta",
        "urn:nir:stato:decreto.legislativo:1995;504~art21",
        "urn:nir:stato:decreto.legislativo:1995;504~art23-comma6",
        "urn:nir:stato:decreto.legislativo:1995;504~art29-comma4",
        "urn:nir:stato:legge:2006;286",
        "urn:nir:stato:legge:2016;232~art1-comma535",
    },
    "tribunale_roma_lavoro_2016_5495.txt": {
        "ECLI:IT:CASS:2010:25145CIV",
        "ECLI:IT:CASS:2014:6110CIV",
        "urn:nir:stato:legge:1966;604",
        "urn:nir:stato:legge:1966;604~art10",
        "urn:nir:stato:legge:1966;604~art3",
        "urn:nir:stato:legge:1970;300",
        "urn:nir:stato:regio.decreto:1940;1443:1~art423",
        "urn:nir:stato:regio.decreto:1940;1443:1~art429",
        "urn:nir:stato:regio.decreto:1942;262:2~art2119",
    },
    "tribunale_roma_contratti_2024_15396.txt": {
        "ECLI:IT:CASS:1977:4884CIV",
        "ECLI:IT:CASS:1982:3141CIV",
        "ECLI:IT:CASS:1997:9589CIV",
        "ECLI:IT:CASS:2007:18570CIV",
        "ECLI:IT:CASS:2011:15290CIV",
        "ECLI:IT:CASS:2011:15669CIV",
        "ECLI:IT:CASS:2015:12310CIV",
        "ECLI:IT:CASS:2021:7765CIV",
        "ECLI:IT:CASS:2023:16120CIV",
        "ECLI:IT:TRIBRM:2013:16268",
        "urn:nir:stato:regio.decreto:1940;1443:1~art281sexies",
        "urn:nir:stato:regio.decreto:1940;1443:1~art649",
        "urn:nir:stato:regio.decreto:1940;1443:1~art96",
        "urn:nir:stato:regio.decreto:1942;262:2~art1284-comma4",
        "urn:nir:stato:regio.decreto:1942;262:2~art1385",
        "urn:nir:stato:regio.decreto:1942;262:2~art1401",
        "urn:nir:stato:regio.decreto:1942;262:2~art1453-comma1",
        "urn:nir:stato:regio.decreto:1942;262:2~art2932",
        "urn:nir:stato:regio.decreto:1942;262:2~art2943",
        "urn:nir:stato:regio.decreto:1942;262:2~art2945",
    },
}

FORBIDDEN_URN_ANCHOR_SUBSTRINGS = {
    "bdgt_sentenza_v28_898_2022.txt": {
        "Del Comune Di Pizz",
        "Email_3 Sentenza",
    },
    "cass_2018_12769_civ.txt": {
        "legge (artt. 7 I. 212/00",
    },
    "cgue_62024cj0367_it.txt": {
        "[[20]] Dal secondo comma",
    },
}

FORBIDDEN_URNS = {
    "admin_tar_lazio_2026_2731.txt": {
        "PRAX:AE:INT:2026:398",
    },
    "admin_consiglio_stato_2021_2023.txt": {
        "ECLI:IT:CONSSTATO:2020:9292",
    },
    "bdgt_sentenza_v28_898_2022.txt": {
        "urn:nir:stato:legge:2006;223~art36-comma2",
        "urn:nir:stato:legge:2006;248~art36-comma2",
    },
    "bdgt_sentenza_u59_465_2022.txt": {
        "ECLI:IT:CTREMR:2021:1202",
    },
    "corte_conti_2024_36_app3.txt": {
        "ECLI:IT:CCONTI:1936:202",
    },
    "corte_cost_2024_204.txt": {
        "CONV_EU_DIR_UOMO~art47",
    },
    "law_dl_326_1987_spettacoli.txt": {
        "urn:nir:presidente.repubblica:decreto:1972;1",
        "urn:nir:presidente.repubblica:decreto:1972;2~art1",
        "urn:nir:presidente.repubblica:decreto:1972;3",
    },
    "prassi_ae_interpello_2025_26.txt": {
        "urn:nir:stato:decreto.legge:2020;34~art119-comma8",
        "urn:nir:stato:decreto.legge:2020;34~art119-comma13",
        "urn:nir:stato:decreto.legge:2020;34~art121-comma1",
        "urn:nir:stato:legge:2020;34~art119-comma13",
        "urn:nir:stato:legge:2023;11~art2-comma2",
        "urn:nir:stato:legge:2023;11~art2-comma3",
    },
    "tribunale_roma_contratti_2024_15396.txt": {
        "ECLI:IT:CASS:2024:17361CIV",
        "ECLI:IT:CASS:2024:3141CIV",
        "ECLI:IT:TRIBRM:2024:17361",
    },
}

EXPECTED_TEXT_ANCHOR_SUBSTRINGS = {
    "admin_consiglio_stato_2021_2023.txt": {
        "urn:nir:stato:decreto.legge:2020;137~art25": {
            "art. 25 del d.l. n. 137 del 2020",
        },
    },
    "bdgt_sentenza_v28_898_2022.txt": {
        "ECLI:IT:CASS:2006:25506CIV": {
            "Sezioni Unite n. 25506/2006",
        },
    },
    "bdgt_sentenza_u59_465_2022.txt": {
        "urn:nir:stato:decreto.legge:2018;119~art1": {
            "art. 1 del D.L. n. 119/2018",
        },
        "ECLI:IT:CASS:2019:30351CIV": {
            "Cassazione n. 30351 del 19/09/2019",
        },
    },
    "bdgt_sentenza_z55_3804_2022.txt": {
        "ECLI:IT:CASS:2009:10672CIV": {
            "Cass. SU 10672/2009",
        },
    },
    "cass_2018_25504_tax_civ.txt": {
        "urn:nir:stato:regio.decreto:1940;1443:1~art360-comma1-num5": {
            "art. 360 c.p.c., comma 1, n. 5",
        },
    },
    "corte_conti_2024_36_app3.txt": {
        "ECLI:IT:CCONTI:2024:36": {
            "SENTENZA\nN. 36/2024/2023",
        },
    },
    "law_10_2020_body_tissue.txt": {
        "urn:nir:stato:legge:2020;10": {
            "LEGGE 10 febbraio 2020 , n. 10",
        },
    },
    "law_dl_326_1987_spettacoli.txt": {
        "urn:nir:stato:decreto.legge:1987;326": {
            "DECRETO-LEGGE 4 agosto 1987 , n. 326",
        },
    },
    "prassi_ae_risoluzione_2025_13.txt": {
        "PRAX:AE:CIRC:2012:27": {
            "circolare 21 giugno 2012, n. 27/E",
            "circolare n. 27/E del 21 giugno 2012",
        },
        "ECLI:IT:CASS:2023:31530CIV": {
            "Cass. 13 novembre 2023, n. 31530",
        },
    },
    "prassi_dogane_circolare_2017_8.txt": {
        "urn:nir:stato:decreto.legislativo:1995;504~art8-comma1": {
            "art.8, comma 1, del D.Lgs. n.504/95",
        },
    },
    "tribunale_roma_contratti_2024_15396.txt": {
        "ECLI:IT:CASS:1982:3141CIV": {
            "Cass., 22 maggio 1982, n. 3141",
        },
        "ECLI:IT:TRIBRM:2013:16268": {
            "sentenza Tribunale Roma n.16268/2013",
        },
    },
}


def test_benchmark_documents_expected_urns():
    for name, expected in EXPECTED_URNS.items():
        produced = {row["urn"] for row in _rows(name) if row["urn"]}
        assert expected <= produced


def test_benchmark_documents_avoid_known_broad_anchors():
    for name, forbidden in FORBIDDEN_URN_ANCHOR_SUBSTRINGS.items():
        urn_rows = [row for row in _rows(name) if row["urn"]]
        for row in urn_rows:
            assert all(fragment not in row["text"] for fragment in forbidden)


def test_benchmark_documents_reject_known_spurious_urns():
    for name, forbidden in FORBIDDEN_URNS.items():
        produced = {row["urn"] for row in _rows(name) if row["urn"]}
        assert produced.isdisjoint(forbidden)


def test_benchmark_documents_expected_text_anchors():
    for name, urn_anchors in EXPECTED_TEXT_ANCHOR_SUBSTRINGS.items():
        for urn, expected_fragments in urn_anchors.items():
            texts = [row["text"] for row in _rows(name) if row["urn"] == urn]
            assert texts
            assert any(
                fragment in text
                for text in texts
                for fragment in expected_fragments
            )


def test_full_document_span_gold_urn_occurrences_match():
    for name in _span_gold_docs():
        gold = Counter(row["urn"] for row in _span_gold_for(name))
        produced = Counter(row["urn"] for row in _produced_span_rows(name))
        assert produced == gold


def test_full_document_span_gold_anchor_recall():
    for name in _span_gold_docs():
        gold_rows = _span_gold_for(name)
        produced_rows = _produced_span_rows(name)

        used_produced = set()
        missing = []
        for gold in gold_rows:
            match = _best_unmatched_match(gold, produced_rows, used_produced)
            if match is None or match[0] < SPAN_JACCARD_THRESHOLD:
                missing.append(gold)
            else:
                used_produced.add(match[1])
        assert not missing


def test_full_document_span_gold_anchor_precision():
    for name in _span_gold_docs():
        gold_rows = _span_gold_for(name)
        produced_rows = _produced_span_rows(name)

        used_gold = set()
        extras = []
        for produced in produced_rows:
            match = _best_unmatched_match(produced, gold_rows, used_gold)
            if match is None or match[0] < SPAN_JACCARD_THRESHOLD:
                extras.append(produced)
            else:
                used_gold.add(match[1])
        assert not extras
