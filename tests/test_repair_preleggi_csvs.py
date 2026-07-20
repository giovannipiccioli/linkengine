from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from tools.repair_preleggi_csvs import repair_file, scan_file


HEADER = ["text", "context", "alias", "url", "urn", "filename"]
OLD = "urn:nir:stato:regio.decreto:1942;262:2~art11"
NEW = "urn:nir:stato:regio.decreto:1942;262:1~art11"


def _write(path, header, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="|", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def _read(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle, delimiter="|"))


class RepairPreleggiCsvsTest(unittest.TestCase):
    def test_repair_is_targeted_and_dry_run_is_non_mutating(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "refs.csv"
            rows = [
                [
                    "art. 11 preleggi",
                    "art. 11 preleggi",
                    "COD_CIV",
                    "https://example.test/urn:nir:stato:regio.decreto:1942;262:2~art11",
                    OLD,
                    "one.txt",
                ],
                ["art. 11 codice civile", "", "COD_CIV", "", OLD, "two.txt"],
                [
                    "art. 11",
                    "art. 11 preleggi e art. 2697 c.c.",
                    "COD_CIV",
                    "",
                    OLD,
                    "three.txt",
                ],
                [
                    "art. 11 preleggi",
                    "",
                    "",
                    "",
                    "urn:nir:stato:legge:2000;212~art11",
                    "four.txt",
                ],
            ]
            _write(path, HEADER, rows)
            original = path.read_bytes()

            audit = scan_file(path)
            self.assertEqual(audit.matched_rows, 1)
            self.assertEqual(audit.context_only_rows, 1)
            self.assertEqual(path.read_bytes(), original)

            result = repair_file(path)
            self.assertTrue(result.applied)
            self.assertEqual(result.matched_rows, 1)

            data = _read(path)
            self.assertEqual(data[1][2], "PRELEGGI")
            self.assertTrue(data[1][3].endswith(";262:1~art11"))
            self.assertEqual(data[1][4], NEW)
            self.assertEqual(data[2:], rows[1:])

    def test_original_text_schema_and_long_form(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "refs_hallu.csv"
            header = ["original_text", "urn", "verdict"]
            rows = [
                ["art. 11 delle disposizioni sulla legge in generale", OLD, "present"],
                ["art. 12 disp. prel.", OLD.replace("art11", "art12"), "present"],
            ]
            _write(path, header, rows)

            result = repair_file(path)
            self.assertTrue(result.applied)
            self.assertEqual(result.matched_rows, 2)
            data = _read(path)
            self.assertTrue(data[1][1].endswith(";262:1~art11"))
            self.assertTrue(data[2][1].endswith(";262:1~art12"))


if __name__ == "__main__":
    unittest.main()
