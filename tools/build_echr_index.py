"""Build linkengine/data/echr_judgments.tsv.gz from the HUDOC metadata of the judgments.

    python tools/build_echr_index.py ~/Documents/trib_data_unzipped/ECHR_txt_norm

The folder holds one ``echr_<year>.csv`` per year, pipe-separated, with at least the columns
``ecli, docname, appno, respondent, doctype`` (the output of the project's HUDOC scraper).
One line per judgment: ``ecli, respondents (+), ordinal, applicant slug, other applicants
(|), applications (|), display name``. Rerun it when new judgments are added; the file is
rebuilt whole, about 270 KB.
"""
import csv
import glob
import gzip
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from linkengine.echr import (DATA_FILE, applicant_segments, applicant_slug,  # noqa: E402
                             display_name)

_PREFIX = re.compile(r"^(?:CASE OF|AFFAIRE|ARR[ÊE]T|CASE)\s+", re.I)
_VS = re.compile(r"\s*(?:\bv\.|\bc\.|\bcontre\b|\bagainst\b|\bvs\.?)\s+", re.I)
_ORDINAL = re.compile(r"\(\s*(?:N[°ºo]?\.?|no\.?|nr\.?)\s*(\d+)\s*\)|\(\s*(\d)\s*\)", re.I)
_ECLI = re.compile(r"ECLI:CE:ECHR:\d{4}:\d{4}(?:JUD|DEC)\d{9}")


def rows(folder):
    csv.field_size_limit(10 ** 9)
    for path in sorted(glob.glob(os.path.join(folder, "echr_*.csv"))):
        with open(path, encoding="utf-8") as fh:
            reader = csv.reader(fh, delimiter="|")
            header = next(reader)
            for row in reader:
                if len(row) == len(header):
                    yield dict(zip(header, row))


def main(folder, out=DATA_FILE):
    lines = []
    for r in rows(folder):
        dn = _PREFIX.sub("", r["docname"].strip())
        m = _VS.search(dn)
        if not (m and _ECLI.fullmatch(r.get("ecli", ""))):
            continue
        left = dn[:m.start()]
        left_clean = _ORDINAL.sub("", left).strip()
        o = _ORDINAL.search(dn)
        ordinal = int(o.group(1) or o.group(2)) if o else 0
        resp = "+".join(sorted(x for x in r["respondent"].split(";") if x))
        slug = applicant_slug(left_clean)
        if not (slug and resp):
            continue
        segs = [x for x in applicant_segments(left_clean)[1:] if x != slug]
        appnos = "|".join(a.strip() for a in r["appno"].split(";") if a.strip())
        lines.append("\t".join([r["ecli"], resp, str(ordinal), slug, "|".join(segs), appnos,
                                display_name(left_clean)]))
    lines.sort()
    with gzip.GzipFile(out, "wb", mtime=0) as fh:
        fh.write(("\n".join(lines) + "\n").encode("utf-8"))
    print(f"{len(lines)} judgments -> {out} ({os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    main(sys.argv[1], *(sys.argv[2:3]))
