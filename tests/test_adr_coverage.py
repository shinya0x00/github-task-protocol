from __future__ import annotations

import importlib
import json
from pathlib import Path
import re
import unittest


class AdrCoverageTests(unittest.TestCase):
    def test_every_v1_adr_has_a_resolvable_conformance_test(self) -> None:
        root = Path(__file__).parent.parent
        sources: dict[str, list[str]] = {}

        decisions = (root / "DECISIONS.md").read_text(encoding="utf-8")
        decision_ids = re.findall(r"^## (ADR-\d{3}):", decisions, re.MULTILINE)
        self.assertEqual(
            len(decision_ids),
            len(set(decision_ids)),
            "DECISIONS.md contains duplicate ADR headings",
        )
        for adr in decision_ids:
            sources.setdefault(adr, []).append("DECISIONS.md")

        for adr_path in sorted((root / "adr").glob("*.md")):
            headings = re.findall(
                r"^# (ADR-\d{3}):",
                adr_path.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
            self.assertEqual(
                1,
                len(headings),
                f"{adr_path.name} must contain exactly one ADR heading",
            )
            filename = re.match(r"^(\d{4})-", adr_path.name)
            self.assertIsNotNone(
                filename,
                f"{adr_path.name} must start with a four-digit ADR number",
            )
            adr = headings[0]
            self.assertEqual(
                int(adr.removeprefix("ADR-")),
                int(filename.group(1)),
                f"{adr_path.name} does not match its {adr} heading",
            )
            sources.setdefault(adr, []).append(str(adr_path.relative_to(root)))

        duplicates = {
            adr: locations for adr, locations in sources.items() if len(locations) != 1
        }
        self.assertEqual({}, duplicates, "ADR IDs must have exactly one definition")

        path = Path(__file__).parent / "fixtures" / "adr-conformance.json"
        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                self.assertNotIn(key, result, f"duplicate ADR fixture key: {key}")
                result[key] = value
            return result

        coverage = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs
        )
        self.assertEqual(set(sources), set(coverage))
        for adr, reference in coverage.items():
            with self.subTest(adr=adr):
                module_name, class_name, method_name = reference.split(".")
                module = importlib.import_module(module_name)
                case = getattr(module, class_name)
                self.assertTrue(callable(getattr(case, method_name)))


if __name__ == "__main__":
    unittest.main()
