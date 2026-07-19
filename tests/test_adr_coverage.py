from __future__ import annotations

import importlib
import json
from pathlib import Path
import unittest


class AdrCoverageTests(unittest.TestCase):
    def test_every_v1_adr_has_a_resolvable_conformance_test(self) -> None:
        path = Path(__file__).parent / "fixtures" / "adr-conformance.json"
        coverage = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(
            {f"ADR-{number:03d}" for number in range(1, 27)},
            set(coverage),
        )
        for adr, reference in coverage.items():
            with self.subTest(adr=adr):
                module_name, class_name, method_name = reference.split(".")
                module = importlib.import_module(module_name)
                case = getattr(module, class_name)
                self.assertTrue(callable(getattr(case, method_name)))


if __name__ == "__main__":
    unittest.main()
