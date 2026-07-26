from __future__ import annotations

import base64
import csv
from hashlib import sha256
from io import StringIO
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import tarfile
from unittest import mock
from zipfile import ZIP_DEFLATED
from zipfile import ZipFile

import build_backend
import gtp


SOURCE_PACKAGE_VERSION = build_backend._project()["version"]


EXPECTED_WHEEL_SOURCE_MANIFEST = (
    "src/gtp/__init__.py",
    "src/gtp/__main__.py",
    "src/gtp/carrier.py",
    "src/gtp/cli.py",
    "src/gtp/github.py",
    "src/gtp/model.py",
    "src/gtp/presentation.py",
    "src/gtp/reducer.py",
    "src/gtp/schema.py",
    "src/gtp/status.py",
    "src/gtp/urls.py",
)

EXPECTED_REPOSITORY_ONLY_SOURCE_PATHS = (
    ".github/workflows/ci.yml",
    ".gitignore",
)

EXPECTED_SDIST_SOURCE_MANIFEST = (
    "DECISIONS.md",
    "DESIGN.md",
    "GTP.md",
    "LICENSE",
    "README.md",
    "acceptance/explicit-setup-install/delivery.json",
    "acceptance/explicit-setup-install/run.json",
    "acceptance/legacy/issue-1/README.md",
    "acceptance/legacy/issue-1/run.json",
    "acceptance/legacy/v1.0.0/STATUS.md",
    "acceptance/legacy/v1.0.0/v1.0.0.json",
    "acceptance/level0/README.md",
    "acceptance/level0/run.json",
    "acceptance/level1/README.md",
    "acceptance/level1/human-probe.md",
    "acceptance/level1/run.json",
    "acceptance/level1/stdout/current-done.txt",
    "acceptance/level1/stdout/done.txt",
    "acceptance/level1/stdout/halt.txt",
    "acceptance/level1/stdout/stopped.txt",
    "acceptance/pr-snapshot-binding-run.json",
    "acceptance/problem-explanations/human-probe.md",
    "acceptance/problem-explanations/run.json",
    "acceptance/public-release-v1.0.1.json",
    "acceptance/public-release-v1.0.2.json",
    "acceptance/public-release-v1.0.3.json",
    "acceptance/purpose-alignment/run.json",
    "acceptance/purpose-alignment/walking-skeleton.json",
    "acceptance/purpose-safety-run.json",
    "acceptance/release-notes-v1.0.1.md",
    "acceptance/release-notes-v1.0.2.md",
    "acceptance/release-notes-v1.0.3.md",
    "acceptance/release-notes-v1.0.4.md",
    "acceptance/release.json",
    "acceptance/stop-time-boundary-run.json",
    "acceptance/v1.0.4/live-paths.json",
    "acceptance/v1.0.4/public-record-disclosure.json",
    "acceptance/v1.0.4/release-candidate.json",
    "acceptance/v1.0.4/walking-skeleton.json",
    "adr/0035-human-actionable-problem-explanations.md",
    "adr/0036-reproducible-release-artifacts.md",
    "adr/0037-separate-private-instructions-from-public-records.md",
    "adr/0038-protocol-1-1-revisions-and-package-versioning.md",
    "adr/0039-existing-instructions-and-issue-lifecycle-boundary.md",
    "adr/0040-production-source-budget-and-formatting.md",
    "adr/0041-readme-human-entry-budget.md",
    "build_backend.py",
    "pyproject.toml",
    "src/gtp/__init__.py",
    "src/gtp/__main__.py",
    "src/gtp/carrier.py",
    "src/gtp/cli.py",
    "src/gtp/github.py",
    "src/gtp/model.py",
    "src/gtp/presentation.py",
    "src/gtp/reducer.py",
    "src/gtp/schema.py",
    "src/gtp/status.py",
    "src/gtp/urls.py",
    "tests/fixtures/adr-conformance.json",
    "tests/fixtures/carriers/contract-valid.md",
    "tests/fixtures/carriers/done-valid.md",
    "tests/fixtures/carriers/start-valid.md",
    "tests/fixtures/carriers/stop-valid.md",
    "tests/fixtures/cli/problem-explanations.json",
    "tests/fixtures/cli/prune-report.txt",
    "tests/fixtures/cli/status-matrix.json",
    "tests/fixtures/http/done-success.json",
    "tests/fixtures/http/live-binding-matrix.json",
    "tests/fixtures/http/prune-report.txt",
    "tests/fixtures/http/purpose-alignment-walking-skeleton.json",
    "tests/fixtures/http/purpose-safety-walking-skeleton.json",
    "tests/fixtures/http/walking-skeleton.json",
    "tests/fixtures/prune-report.txt",
    "tests/fixtures/protocol-1.1/walking-skeleton.json",
    "tests/fixtures/reducer-truth-table.json",
    "tests/fixtures/release/prune-report.txt",
    "tests/fixtures/release/surface.json",
    "tests/fixtures/schema-conformance.json",
    "tests/fixtures/setup-preflight.json",
    "tests/test_adr_coverage.py",
    "tests/test_build_backend.py",
    "tests/test_carrier.py",
    "tests/test_cli.py",
    "tests/test_github.py",
    "tests/test_reducer.py",
    "tests/test_release_surface.py",
    "tests/test_schema.py",
    "tests/test_status.py",
    "tests/test_v1_conformance.py",
)


class BuildBackendTests(unittest.TestCase):
    def test_runtime_and_package_versions_match_v104_source(self) -> None:
        project_version = build_backend._project()["version"]
        self.assertRegex(project_version, r"^[0-9]+\.[0-9]+\.[0-9]+$")
        self.assertEqual("1.0.4", project_version)
        self.assertEqual(project_version, gtp.__version__)

    def test_source_manifests_are_explicit_complete_and_ordered(self) -> None:
        self.assertEqual(
            EXPECTED_WHEEL_SOURCE_MANIFEST,
            build_backend.WHEEL_SOURCE_MANIFEST,
        )
        self.assertEqual(
            EXPECTED_SDIST_SOURCE_MANIFEST,
            build_backend.SDIST_SOURCE_MANIFEST,
        )
        self.assertEqual(11, len(build_backend.WHEEL_SOURCE_MANIFEST))
        self.assertEqual(90, len(build_backend.SDIST_SOURCE_MANIFEST))
        backend_source = Path(build_backend.__file__).read_text(encoding="utf-8")
        self.assertNotIn(".glob(", backend_source)
        self.assertNotIn(".rglob(", backend_source)
        self.assertNotIn("git ls-files", backend_source)

    def test_duplicate_paths_returns_each_duplicate_once_in_sorted_order(
        self,
    ) -> None:
        self.assertEqual(
            ["a.py", "b.py"],
            build_backend._duplicate_paths(
                ("b.py", "a.py", "b.py", "a.py", "a.py", "c.py")
            ),
        )

    def test_tracked_source_manifest_accepts_the_exact_declared_set(self) -> None:
        self.assertEqual(
            EXPECTED_REPOSITORY_ONLY_SOURCE_PATHS,
            build_backend._REPOSITORY_ONLY_SOURCE_PATHS,
        )
        tracked_paths = (
            *EXPECTED_SDIST_SOURCE_MANIFEST,
            *EXPECTED_REPOSITORY_ONLY_SOURCE_PATHS,
        )

        self.assertIsNone(
            build_backend._validate_tracked_source_manifest(tracked_paths)
        )

    def test_tracked_source_manifest_rejects_an_undeclared_addition(self) -> None:
        tracked_paths = (
            *EXPECTED_SDIST_SOURCE_MANIFEST,
            *EXPECTED_REPOSITORY_ONLY_SOURCE_PATHS,
            "NOTICE.md",
        )

        with self.assertRaises(ValueError) as raised:
            build_backend._validate_tracked_source_manifest(tracked_paths)
        self.assertEqual(
            "tracked source manifest mismatch: "
            "undeclared=['NOTICE.md'], missing=[]",
            str(raised.exception),
        )

    def test_tracked_source_manifest_rejects_a_missing_declared_path(self) -> None:
        tracked_paths = tuple(
            path
            for path in (
                *EXPECTED_SDIST_SOURCE_MANIFEST,
                *EXPECTED_REPOSITORY_ONLY_SOURCE_PATHS,
            )
            if path != "README.md"
        )

        with self.assertRaises(ValueError) as raised:
            build_backend._validate_tracked_source_manifest(tracked_paths)
        self.assertEqual(
            "tracked source manifest mismatch: "
            "undeclared=[], missing=['README.md']",
            str(raised.exception),
        )

    def test_tracked_source_manifest_rejects_duplicate_paths(self) -> None:
        tracked_paths = (
            *EXPECTED_SDIST_SOURCE_MANIFEST,
            *EXPECTED_REPOSITORY_ONLY_SOURCE_PATHS,
        )
        duplicate_cases = (
            (
                "input",
                "duplicate input paths: ['README.md']",
                (*tracked_paths, "README.md"),
                "SDIST_SOURCE_MANIFEST",
                EXPECTED_SDIST_SOURCE_MANIFEST,
            ),
            (
                "sdist",
                "duplicate sdist paths: ['README.md']",
                tracked_paths,
                "SDIST_SOURCE_MANIFEST",
                (*EXPECTED_SDIST_SOURCE_MANIFEST, "README.md"),
            ),
            (
                "wheel",
                "duplicate wheel paths: ['src/gtp/__init__.py']",
                tracked_paths,
                "WHEEL_SOURCE_MANIFEST",
                (*EXPECTED_WHEEL_SOURCE_MANIFEST, "src/gtp/__init__.py"),
            ),
            (
                "repository-only",
                "duplicate repository-only paths: ['.gitignore']",
                tracked_paths,
                "_REPOSITORY_ONLY_SOURCE_PATHS",
                (*EXPECTED_REPOSITORY_ONLY_SOURCE_PATHS, ".gitignore"),
            ),
        )
        for (
            label,
            message,
            supplied_paths,
            attribute,
            replacement,
        ) in duplicate_cases:
            with self.subTest(label=label):
                with mock.patch.object(build_backend, attribute, replacement):
                    with self.assertRaises(ValueError) as raised:
                        build_backend._validate_tracked_source_manifest(
                            supplied_paths
                        )
                self.assertEqual(message, str(raised.exception))

    def test_tracked_source_manifest_rejects_wheel_paths_outside_sdist(self) -> None:
        outside_path = "src/gtp/wheel-only.py"
        tracked_paths = (
            *EXPECTED_SDIST_SOURCE_MANIFEST,
            *EXPECTED_REPOSITORY_ONLY_SOURCE_PATHS,
        )

        with mock.patch.object(
            build_backend,
            "WHEEL_SOURCE_MANIFEST",
            (*EXPECTED_WHEEL_SOURCE_MANIFEST, outside_path),
        ):
            with self.assertRaises(ValueError) as raised:
                build_backend._validate_tracked_source_manifest(tracked_paths)
        self.assertEqual(
            "wheel manifest is outside sdist: "
            "['src/gtp/wheel-only.py']",
            str(raised.exception),
        )

    def test_tracked_source_manifest_rejects_repository_only_sdist_overlap(
        self,
    ) -> None:
        tracked_paths = (
            *EXPECTED_SDIST_SOURCE_MANIFEST,
            *EXPECTED_REPOSITORY_ONLY_SOURCE_PATHS,
        )
        with mock.patch.object(
            build_backend,
            "_REPOSITORY_ONLY_SOURCE_PATHS",
            (".github/workflows/ci.yml", "README.md"),
        ):
            with self.assertRaises(ValueError) as raised:
                build_backend._validate_tracked_source_manifest(tracked_paths)
        self.assertEqual(
            "duplicate sdist/repository-only paths: ['README.md']",
            str(raised.exception),
        )

    def test_tracked_source_manifest_allows_repository_only_paths(self) -> None:
        tracked_paths = (
            *EXPECTED_SDIST_SOURCE_MANIFEST,
            *EXPECTED_REPOSITORY_ONLY_SOURCE_PATHS,
        )

        self.assertIsNone(
            build_backend._validate_tracked_source_manifest(tracked_paths)
        )

    def test_invalid_source_date_epoch_fails_before_writing_an_artifact(self) -> None:
        for value in ("", "-1", "1.5", "not-an-integer"):
            for builder in (build_backend.build_wheel, build_backend.build_sdist):
                with self.subTest(value=value, builder=builder.__name__):
                    with tempfile.TemporaryDirectory() as directory:
                        with mock.patch.dict(
                            os.environ,
                            {"SOURCE_DATE_EPOCH": value},
                            clear=False,
                        ):
                            with self.assertRaises(ValueError):
                                builder(directory)
                        self.assertEqual([], list(Path(directory).iterdir()))

    def test_missing_source_date_epoch_uses_a_fixed_archive_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("SOURCE_DATE_EPOCH", None)
                wheel_name = build_backend.build_wheel(directory)
                sdist_name = build_backend.build_sdist(directory)
            with ZipFile(Path(directory) / wheel_name) as wheel:
                self.assertEqual(
                    {(1980, 1, 1, 0, 0, 0)},
                    {info.date_time for info in wheel.infolist()},
                )
            with tarfile.open(Path(directory) / sdist_name, "r:gz") as archive:
                self.assertEqual({0}, {info.mtime for info in archive.getmembers()})
            gzip_mtime = int.from_bytes(
                (Path(directory) / sdist_name).read_bytes()[4:8],
                "little",
            )
            self.assertEqual(0, gzip_mtime)

    def test_manifest_validation_fails_before_writing_an_artifact(self) -> None:
        valid = EXPECTED_WHEEL_SOURCE_MANIFEST[0]
        invalid_manifests = {
            "duplicate": (valid, valid),
            "empty": ("",),
            "absolute": (str((Path(build_backend.ROOT) / valid).resolve()),),
            "backslash": (r"src\gtp\__init__.py",),
            "dot": ("src/./gtp/__init__.py",),
            "dotdot": ("src/gtp/../gtp/__init__.py",),
            "root escape": ("../README.md",),
            "missing": ("src/gtp/not-present.py",),
            "nonregular": ("src/gtp",),
        }
        for reason, manifest in invalid_manifests.items():
            for builder, manifest_name in (
                (build_backend.build_wheel, "WHEEL_SOURCE_MANIFEST"),
                (build_backend.build_sdist, "SDIST_SOURCE_MANIFEST"),
            ):
                with self.subTest(reason=reason, builder=builder.__name__):
                    with tempfile.TemporaryDirectory() as directory:
                        with mock.patch.object(
                            build_backend,
                            manifest_name,
                            manifest,
                        ):
                            with self.assertRaises((OSError, ValueError)):
                                builder(directory)
                        self.assertEqual([], list(Path(directory).iterdir()))

    def test_manifest_rejects_a_symlink_in_a_path_component(self) -> None:
        for symlink_location in ("directory", "file"):
            with self.subTest(symlink_location=symlink_location):
                with tempfile.TemporaryDirectory() as directory:
                    temporary_root = Path(directory) / "source"
                    output = Path(directory) / "dist"
                    temporary_root.mkdir()
                    output.mkdir()
                    for name in ("pyproject.toml", "README.md", "LICENSE"):
                        shutil.copy2(
                            Path(build_backend.ROOT) / name,
                            temporary_root / name,
                        )
                    (temporary_root / "src").mkdir()
                    if symlink_location == "directory":
                        (temporary_root / "src" / "gtp").symlink_to(
                            Path(build_backend.ROOT) / "src" / "gtp",
                            target_is_directory=True,
                        )
                    else:
                        (temporary_root / "src" / "gtp").mkdir()
                        (temporary_root / "src" / "gtp" / "__init__.py").symlink_to(
                            Path(build_backend.ROOT) / "src" / "gtp" / "__init__.py"
                        )
                    with mock.patch.object(build_backend, "ROOT", temporary_root):
                        with mock.patch.object(
                            build_backend,
                            "WHEEL_SOURCE_MANIFEST",
                            ("src/gtp/__init__.py",),
                        ):
                            with self.assertRaisesRegex(ValueError, "symlink"):
                                build_backend.build_wheel(str(output))
                    self.assertEqual([], list(output.iterdir()))

    def test_same_sources_and_epoch_produce_byte_identical_normalized_archives(
        self,
    ) -> None:
        epoch = 1_700_000_001
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            with mock.patch.dict(
                os.environ,
                {"SOURCE_DATE_EPOCH": str(epoch)},
                clear=False,
            ):
                first_wheel_name = build_backend.build_wheel(str(first))
                first_sdist_name = build_backend.build_sdist(str(first))
                second_wheel_name = build_backend.build_wheel(str(second))
                second_sdist_name = build_backend.build_sdist(str(second))

            first_wheel = first / first_wheel_name
            second_wheel = second / second_wheel_name
            first_sdist = first / first_sdist_name
            second_sdist = second / second_sdist_name
            self.assertEqual(first_wheel.read_bytes(), second_wheel.read_bytes())
            self.assertEqual(first_sdist.read_bytes(), second_sdist.read_bytes())

            project = build_backend._project()
            dist_info = f"github_task_protocol-{project['version']}.dist-info"
            expected_wheel_names = [
                name.removeprefix("src/")
                for name in EXPECTED_WHEEL_SOURCE_MANIFEST
            ] + [
                f"{dist_info}/METADATA",
                f"{dist_info}/WHEEL",
                f"{dist_info}/entry_points.txt",
                f"{dist_info}/licenses/LICENSE",
                f"{dist_info}/RECORD",
            ]
            timestamp = time.gmtime(epoch)
            expected_zip_timestamp = (
                timestamp.tm_year,
                timestamp.tm_mon,
                timestamp.tm_mday,
                timestamp.tm_hour,
                timestamp.tm_min,
                timestamp.tm_sec - timestamp.tm_sec % 2,
            )
            with ZipFile(first_wheel) as wheel:
                self.assertEqual(expected_wheel_names, wheel.namelist())
                for info in wheel.infolist():
                    self.assertEqual(expected_zip_timestamp, info.date_time)
                    self.assertEqual(3, info.create_system)
                    self.assertEqual(0o100644, info.external_attr >> 16)
                    self.assertEqual(ZIP_DEFLATED, info.compress_type)
                    self.assertEqual(b"", info.extra)

            sdist_root = f"github-task-protocol-{project['version']}"
            expected_sdist_names = [
                f"{sdist_root}/{name}"
                for name in EXPECTED_SDIST_SOURCE_MANIFEST
            ] + [f"{sdist_root}/PKG-INFO"]
            with tarfile.open(first_sdist, "r:gz") as archive:
                self.assertEqual(expected_sdist_names, archive.getnames())
                self.assertEqual(91, len(archive.getmembers()))
                for info in archive.getmembers():
                    self.assertTrue(info.isreg())
                    self.assertEqual(0o644, info.mode)
                    self.assertEqual(epoch, info.mtime)
                    self.assertEqual(0, info.uid)
                    self.assertEqual(0, info.gid)
                    self.assertEqual("", info.uname)
                    self.assertEqual("", info.gname)
            gzip_mtime = int.from_bytes(first_sdist.read_bytes()[4:8], "little")
            self.assertEqual(epoch, gzip_mtime)

    def test_direct_wheel_matches_wheel_built_from_the_sdist(self) -> None:
        epoch = "1700000000"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            direct_directory = root / "direct"
            sdist_directory = root / "sdist"
            extracted_directory = root / "extracted"
            roundtrip_directory = root / "roundtrip"
            for path in (
                direct_directory,
                sdist_directory,
                extracted_directory,
                roundtrip_directory,
            ):
                path.mkdir()
            with mock.patch.dict(
                os.environ,
                {"SOURCE_DATE_EPOCH": epoch},
                clear=False,
            ):
                wheel_name = build_backend.build_wheel(str(direct_directory))
                sdist_name = build_backend.build_sdist(str(sdist_directory))
            with tarfile.open(sdist_directory / sdist_name, "r:gz") as archive:
                archive.extractall(extracted_directory, filter="data")
            source_root = (
                extracted_directory
                / f"github-task-protocol-{SOURCE_PACKAGE_VERSION}"
            )
            environment = os.environ.copy()
            environment["SOURCE_DATE_EPOCH"] = epoch
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import build_backend, sys; "
                        "build_backend.build_wheel(sys.argv[1])"
                    ),
                    str(roundtrip_directory),
                ],
                cwd=source_root,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                (direct_directory / wheel_name).read_bytes(),
                (roundtrip_directory / wheel_name).read_bytes(),
            )

    def test_undeclared_files_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            baseline_output = root / "baseline"
            changed_output = root / "changed"
            shutil.copytree(
                build_backend.ROOT,
                source,
                ignore=shutil.ignore_patterns(".git", "__pycache__"),
            )
            baseline_output.mkdir()
            changed_output.mkdir()
            epoch = "1700000000"
            with mock.patch.object(build_backend, "ROOT", source):
                with mock.patch.dict(
                    os.environ,
                    {"SOURCE_DATE_EPOCH": epoch},
                    clear=False,
                ):
                    wheel_name = build_backend.build_wheel(str(baseline_output))
                    sdist_name = build_backend.build_sdist(str(baseline_output))

            marker = sha256(str(root).encode("utf-8")).hexdigest().encode("ascii")
            local_path = str(root / "private" / "credentials.json").encode("utf-8")
            token_assignment = b"GITHUB_TOKEN=gh" + b"p_" + marker
            undeclared = {
                "src/gtp/undeclared.py": b"# " + marker + b"\n",
                "acceptance/undeclared.json": (
                    b'{"marker":"' + marker + b'","path":"' + local_path + b'"}\n'
                ),
                "adr/undeclared.md": b"# " + marker + b"\n",
                ".env": token_assignment + b"\n",
                ".DS_Store": b"Finder metadata " + marker,
                "src/gtp/__pycache__/x.pyc": b"\x00\x00" + marker,
            }
            for relative_name, data in undeclared.items():
                path = source / relative_name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                path.chmod(0o600)
                os.utime(path, (1_800_000_000, 1_800_000_000))
            for index, relative_name in enumerate(
                build_backend.SDIST_SOURCE_MANIFEST
            ):
                path = source / relative_name
                path.chmod(0o755 if index % 2 else 0o600)
                changed_time = 1_600_000_000 + index
                os.utime(path, (changed_time, changed_time))

            with mock.patch.object(build_backend, "ROOT", source):
                with mock.patch.dict(
                    os.environ,
                    {"SOURCE_DATE_EPOCH": epoch},
                    clear=False,
                ):
                    changed_wheel_name = build_backend.build_wheel(str(changed_output))
                    changed_sdist_name = build_backend.build_sdist(str(changed_output))

            self.assertEqual(wheel_name, changed_wheel_name)
            self.assertEqual(sdist_name, changed_sdist_name)
            self.assertEqual(
                (baseline_output / wheel_name).read_bytes(),
                (changed_output / changed_wheel_name).read_bytes(),
            )
            self.assertEqual(
                (baseline_output / sdist_name).read_bytes(),
                (changed_output / changed_sdist_name).read_bytes(),
            )

            with ZipFile(changed_output / changed_wheel_name) as wheel:
                wheel_names = wheel.namelist()
                wheel_payload = b"".join(wheel.read(name) for name in wheel_names)
            with tarfile.open(changed_output / changed_sdist_name, "r:gz") as archive:
                sdist_names = archive.getnames()
                sdist_payload = b"".join(
                    extracted.read()
                    for info in archive.getmembers()
                    if info.isreg()
                    for extracted in [archive.extractfile(info)]
                    if extracted is not None
                )
            for relative_name in undeclared:
                archive_names = {
                    relative_name,
                    relative_name.removeprefix("src/"),
                }
                self.assertFalse(
                    any(
                        name == undeclared_name
                        or name.endswith(f"/{undeclared_name}")
                        for name in wheel_names + sdist_names
                        for undeclared_name in archive_names
                    ),
                    relative_name,
                )
            for forbidden_content in (marker, local_path, token_assignment):
                self.assertNotIn(forbidden_content, wheel_payload)
                self.assertNotIn(forbidden_content, sdist_payload)

    def test_wheel_contains_package_entrypoint_and_complete_record(self) -> None:
        version = build_backend._project()["version"]
        dist_info = f"github_task_protocol-{version}.dist-info"
        with tempfile.TemporaryDirectory() as directory:
            filename = build_backend.build_wheel(directory)
            with ZipFile(Path(directory) / filename) as wheel:
                names = set(wheel.namelist())
                self.assertIn("gtp/cli.py", names)
                self.assertIn("gtp/presentation.py", names)
                self.assertIn(
                    f"{dist_info}/licenses/LICENSE", names
                )
                self.assertIn(
                    f"{dist_info}/entry_points.txt", names
                )
                record_name = f"{dist_info}/RECORD"
                rows = list(csv.reader(StringIO(wheel.read(record_name).decode("utf-8"))))
                self.assertEqual(names, {row[0] for row in rows})
                self.assertEqual(len(names), len(rows))
                self.assertTrue(all(len(row) == 3 for row in rows))
                records = {row[0]: row[1:] for row in rows}
                self.assertEqual(["", ""], records[record_name])
                for name in names - {record_name}:
                    data = wheel.read(name)
                    digest = base64.urlsafe_b64encode(sha256(data).digest())
                    encoded = digest.rstrip(b"=").decode("ascii")
                    self.assertEqual(
                        [f"sha256={encoded}", str(len(data))],
                        records[name],
                        name,
                    )
                metadata = wheel.read(f"{dist_info}/METADATA").decode("utf-8")
                self.assertIn("License-Expression: MIT", metadata)
                self.assertIn(
                    "Project-URL: Repository, https://github.com/shinya0x00/github-task-protocol",
                    metadata,
                )
                self.assertIn("# GitHub Task Protocol", metadata)

    def test_sdist_contains_public_spec_license_source_and_tests(self) -> None:
        project = build_backend._project()
        root = f"github-task-protocol-{project['version']}"
        expected_filename = f"github_task_protocol-{project['version']}.tar.gz"
        with tempfile.TemporaryDirectory() as directory:
            filename = build_backend.build_sdist(directory)
            wheel_filename = build_backend.build_wheel(directory)
            self.assertEqual(expected_filename, filename)
            archive_path = Path(directory) / filename
            self.assertTrue(archive_path.is_file())
            dist_info = f"github_task_protocol-{project['version']}.dist-info"
            with ZipFile(Path(directory) / wheel_filename) as wheel:
                wheel_metadata = wheel.read(f"{dist_info}/METADATA")
            with tarfile.open(archive_path, "r:gz") as archive:
                names = set(archive.getnames())
                self.assertEqual({root}, {name.split("/", 1)[0] for name in names})
                extracted = archive.extractfile(f"{root}/PKG-INFO")
                self.assertIsNotNone(extracted)
                pkg_info_bytes = extracted.read()
                pkg_info = pkg_info_bytes.decode("utf-8")
                readme_file = archive.extractfile(f"{root}/README.md")
                design_file = archive.extractfile(f"{root}/DESIGN.md")
                adr_file = archive.extractfile(
                    f"{root}/adr/0035-human-actionable-problem-explanations.md"
                )
                self.assertIsNotNone(readme_file)
                self.assertIsNotNone(design_file)
                self.assertIsNotNone(adr_file)
                readme = readme_file.read().decode("utf-8")
                design = design_file.read().decode("utf-8")
                adr = adr_file.read().decode("utf-8")
        self.assertEqual(pkg_info_bytes, wheel_metadata)
        for required in (
            "GTP.md",
            "README.md",
            "DESIGN.md",
            "DECISIONS.md",
            "adr",
            "LICENSE",
            "src",
            "tests",
        ):
            self.assertTrue(
                any(name == f"{root}/{required}" or name.startswith(f"{root}/{required}/") for name in names),
                required,
            )
        self.assertIn("](GTP.md)", design)
        self.assertIn(f"{root}/GTP.md", names)
        self.assertIn("](../DESIGN.md)", adr)
        self.assertIn(f"{root}/DESIGN.md", names)
        self.assertIn(
            f"{root}/adr/0035-human-actionable-problem-explanations.md",
            names,
        )
        self.assertIn(
            f"{root}/adr/0036-reproducible-release-artifacts.md",
            names,
        )
        for required in (
            "adr/0037-separate-private-instructions-from-public-records.md",
            "adr/0038-protocol-1-1-revisions-and-package-versioning.md",
            "adr/0039-existing-instructions-and-issue-lifecycle-boundary.md",
            "acceptance/release-notes-v1.0.4.md",
            "acceptance/v1.0.4/walking-skeleton.json",
            "acceptance/v1.0.4/live-paths.json",
            "acceptance/v1.0.4/public-record-disclosure.json",
            "acceptance/v1.0.4/release-candidate.json",
        ):
            self.assertIn(f"{root}/{required}", names)
        self.assertIn(f"{root}/acceptance/release-notes-v1.0.3.md", names)
        self.assertIn(f"{root}/PKG-INFO", names)
        self.assertIn("Metadata-Version: 2.4", pkg_info)
        self.assertIn(f"Name: {project['name']}", pkg_info)
        self.assertIn(f"Version: {project['version']}", pkg_info)
        package_identity_boundaries = (
            "このsource treeのPython distribution versionは`1.0.4`",
            "この値はpublicationのEvidenceでも、"
            "exact source commitのidentityでもありません。",
            "source metadataのpackage versionは配布候補の識別子",
        )
        surfaces = {
            "README": readme,
            "sdist PKG-INFO": pkg_info,
            "wheel METADATA": wheel_metadata.decode("utf-8"),
        }
        for surface_name, surface in surfaces.items():
            with self.subTest(surface=surface_name):
                commands = tuple(
                    line
                    for line in surface.splitlines()
                    if line.startswith((
                        "uvx --from github-task-protocol==",
                        'uvx --from "github-task-protocol==',
                    ))
                )
                self.assertEqual(2, len(commands))
                parsed = [
                    re.fullmatch(
                        r'uvx --from "?github-task-protocol==([^" ]+)"? '
                        r"gtp (status|check) (.+)",
                        command,
                    )
                    for command in commands
                ]
                self.assertTrue(all(parsed))
                version_tokens = {match.group(1) for match in parsed if match}
                self.assertEqual(1, len(version_tokens))
                version_token = next(iter(version_tokens))
                self.assertIsNone(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version_token))
                for boundary in package_identity_boundaries:
                    self.assertIn(boundary, surface)
                for forbidden in (
                    "github-task-protocol==1.0.4",
                    "github-task-protocol==1.0.3",
                    "github-task-protocol==1.0.2",
                    "source内容のidentity",
                    "現在のsource candidate",
                    "（公開前）",
                    "利用commandは検証済みの`1.0.2`に固定",
                ):
                    self.assertNotIn(forbidden, surface)

    def test_installed_console_script_runs_status_and_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheel_dir = root / "dist"
            wheel_dir.mkdir()
            filename = build_backend.build_wheel(str(wheel_dir))
            environment = root / "venv"
            subprocess.run(
                [sys.executable, "-m", "venv", str(environment)],
                check=True,
                capture_output=True,
                text=True,
            )
            python = environment / "bin" / "python"
            command = environment / "bin" / "gtp"
            subprocess.run(
                [str(python), "-m", "pip", "install", "--no-deps", str(wheel_dir / filename)],
                check=True,
                capture_output=True,
                text=True,
            )
            checked = subprocess.run(
                [str(command), "check", str(Path(__file__).parent / "fixtures" / "carriers" / "contract-valid.md")],
                check=False,
                capture_output=True,
                text=True,
            )
            status = subprocess.run(
                [str(command), "status", "not-a-github-issue-url"],
                check=False,
                capture_output=True,
                text=True,
            )
            version = subprocess.run(
                [str(command), "--version"],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(0, checked.returncode)
        self.assertIn("offline schemaに適合", checked.stdout)
        self.assertIn('"command": "check"', checked.stdout)
        self.assertEqual(2, status.returncode)
        self.assertIn("状態: 不明", status.stdout)
        self.assertIn('"command": "status"', status.stdout)
        self.assertEqual(0, version.returncode)
        self.assertEqual(f"{gtp.__version__}\n", version.stdout)


if __name__ == "__main__":
    unittest.main()
