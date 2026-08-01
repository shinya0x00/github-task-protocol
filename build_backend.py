"""Small dependency-free PEP 517 backend for the pure-Python GTP CLI."""

from __future__ import annotations

import base64
from collections.abc import Iterable
import csv
import gzip
from hashlib import sha256
from io import BytesIO, StringIO
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import stat
import tarfile
import time
import tomllib
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).parent

WHEEL_SOURCE_MANIFEST = (
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

SDIST_SOURCE_MANIFEST = (
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
    "acceptance/purpose-alignment/run.json",
    "acceptance/purpose-alignment/walking-skeleton.json",
    "acceptance/purpose-safety-run.json",
    "acceptance/release-notes-v1.0.1.md",
    "acceptance/release-notes-v1.0.2.md",
    "acceptance/release-notes-v1.0.3.md",
    "acceptance/release-notes-v1.0.3.post1.md",
    "acceptance/release.json",
    "acceptance/stop-time-boundary-run.json",
    "adr/0035-human-actionable-problem-explanations.md",
    "adr/0036-reproducible-release-artifacts.md",
    "adr/0037-final-legacy-post-release-candidate.md",
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

_REPOSITORY_ONLY_SOURCE_PATHS = (
    ".github/workflows/ci.yml",
    ".gitignore",
    "acceptance/public-release-v1.0.3.post1.json",
)

_DEFAULT_SOURCE_DATE_EPOCH = 0
_ZIP_MIN_EPOCH = 315_532_800  # 1980-01-01, the earliest ZIP timestamp.
_ZIP_MAX_EPOCH = 4_354_819_198  # 2107-12-31 23:59:58, the latest ZIP timestamp.
_GZIP_MAX_EPOCH = (1 << 32) - 1
_ARCHIVE_FILE_MODE = 0o644
_ZIP_COMPRESSION_LEVEL = 9


def _duplicate_paths(paths: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for path in paths:
        if path in seen:
            duplicates.add(path)
        else:
            seen.add(path)
    return sorted(duplicates)


def _validate_tracked_source_manifest(tracked_paths: Iterable[str]) -> None:
    tracked = tuple(tracked_paths)
    manifests = (
        ("input", tracked),
        ("sdist", SDIST_SOURCE_MANIFEST),
        ("wheel", WHEEL_SOURCE_MANIFEST),
        ("repository-only", _REPOSITORY_ONLY_SOURCE_PATHS),
    )
    for label, paths in manifests:
        duplicates = _duplicate_paths(paths)
        if duplicates:
            raise ValueError(f"duplicate {label} paths: {duplicates}")

    sdist_paths = set(SDIST_SOURCE_MANIFEST)
    repository_only_paths = set(_REPOSITORY_ONLY_SOURCE_PATHS)
    repository_only_in_sdist = sorted(sdist_paths & repository_only_paths)
    if repository_only_in_sdist:
        raise ValueError(
            "duplicate sdist/repository-only paths: "
            f"{repository_only_in_sdist}"
        )
    wheel_outside_sdist = sorted(set(WHEEL_SOURCE_MANIFEST) - sdist_paths)
    if wheel_outside_sdist:
        raise ValueError(
            f"wheel manifest is outside sdist: {wheel_outside_sdist}"
        )

    declared_paths = sdist_paths | repository_only_paths
    tracked_path_set = set(tracked)
    undeclared = sorted(tracked_path_set - declared_paths)
    missing = sorted(declared_paths - tracked_path_set)
    if undeclared or missing:
        raise ValueError(
            "tracked source manifest mismatch: "
            f"undeclared={undeclared}, missing={missing}"
        )


def _source_date_epoch() -> int:
    raw = os.environ.get("SOURCE_DATE_EPOCH")
    if raw is None:
        return _DEFAULT_SOURCE_DATE_EPOCH
    if not raw or not raw.isascii() or not raw.isdigit():
        raise ValueError("SOURCE_DATE_EPOCH must be an integer greater than or equal to 0")
    return int(raw, 10)


def _manifest_paths(manifest: tuple[str, ...]) -> list[tuple[str, Path]]:
    root = ROOT.resolve(strict=True)
    if ROOT.is_symlink():
        raise ValueError(f"source root must not be a symlink: {ROOT}")

    seen: set[str] = set()
    paths: list[tuple[str, Path]] = []
    for member in manifest:
        if not isinstance(member, str) or not member:
            raise ValueError("manifest members must be non-empty strings")
        if member in seen:
            raise ValueError(f"duplicate manifest member: {member}")
        seen.add(member)
        if "\\" in member:
            raise ValueError(f"manifest member must use forward slashes: {member}")
        if PurePosixPath(member).is_absolute() or PureWindowsPath(member).is_absolute():
            raise ValueError(f"manifest member must be relative: {member}")
        parts = member.split("/")
        if any(part == "" for part in parts):
            raise ValueError(f"manifest member has an empty path component: {member}")
        if any(part == "." for part in parts):
            raise ValueError(f"manifest member has a dot path component: {member}")
        if any(part == ".." for part in parts):
            raise ValueError(f"manifest member has a dotdot path component: {member}")

        path = ROOT.joinpath(*parts)
        current = ROOT
        for part in parts:
            current = current / part
            try:
                component_mode = current.lstat().st_mode
            except FileNotFoundError:
                break
            if stat.S_ISLNK(component_mode):
                raise ValueError(f"manifest member contains a symlink: {member}")

        try:
            resolved = path.resolve(strict=False)
            resolved.relative_to(root)
        except (RuntimeError, ValueError) as error:
            raise ValueError(f"manifest member escapes the source root: {member}") from error

        try:
            source_mode = path.stat(follow_symlinks=False).st_mode
        except (FileNotFoundError, NotADirectoryError) as error:
            raise FileNotFoundError(f"manifest member does not exist: {member}") from error
        if not stat.S_ISREG(source_mode):
            raise ValueError(f"manifest member is not a regular file: {member}")
        paths.append((member, path))
    return paths


def _read_manifest_file(member: str, path: Path) -> bytes:
    supports_openat = (
        hasattr(os, "O_DIRECTORY")
        and hasattr(os, "O_NOFOLLOW")
        and os.open in os.supports_dir_fd
    )
    if not supports_openat:
        with path.open("rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise ValueError(f"manifest member is not a regular file: {member}")
            return source.read()

    directory_flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )
    file_flags = (
        os.O_RDONLY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_BINARY", 0)
    )
    directory_fds: list[int] = []
    file_fd: int | None = None
    try:
        directory_fds.append(os.open(ROOT, directory_flags))
        parts = member.split("/")
        for part in parts[:-1]:
            directory_fds.append(
                os.open(part, directory_flags, dir_fd=directory_fds[-1])
            )
        file_fd = os.open(parts[-1], file_flags, dir_fd=directory_fds[-1])
        if not stat.S_ISREG(os.fstat(file_fd).st_mode):
            raise ValueError(f"manifest member is not a regular file: {member}")
        with os.fdopen(file_fd, "rb") as source:
            file_fd = None
            return source.read()
    except OSError as error:
        raise ValueError(
            f"manifest member could not be opened without following symlinks: {member}"
        ) from error
    finally:
        if file_fd is not None:
            os.close(file_fd)
        for directory_fd in reversed(directory_fds):
            os.close(directory_fd)


def _manifest_files(manifest: tuple[str, ...]) -> list[tuple[str, bytes]]:
    return [
        (member, _read_manifest_file(member, path))
        for member, path in _manifest_paths(manifest)
    ]


def _source_file(member: str) -> bytes:
    return _manifest_files((member,))[0][1]


def _project() -> dict[str, Any]:
    return tomllib.loads(_source_file("pyproject.toml").decode("utf-8"))["project"]


def _dist_name() -> str:
    return _project()["name"].replace("-", "_")


def _dist_info() -> str:
    return f"{_dist_name()}-{_project()['version']}.dist-info"


def _metadata() -> bytes:
    project = _project()
    readme = project["readme"]
    if not isinstance(readme, str):
        raise ValueError("project.readme must identify one source file")
    lines = [
        "Metadata-Version: 2.4",
        f"Name: {project['name']}",
        f"Version: {project['version']}",
        f"Summary: {project['description']}",
        f"Requires-Python: {project['requires-python']}",
        f"License-Expression: {project['license']}",
        "License-File: LICENSE",
        f"Project-URL: Repository, {project['urls']['Repository']}",
        "Description-Content-Type: text/markdown",
        "",
        _source_file(readme).decode("utf-8"),
    ]
    return "\n".join(lines).encode("utf-8")


def _wheel_metadata() -> bytes:
    return (
        "Wheel-Version: 1.0\n"
        "Generator: github-task-protocol.build_backend\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n\n"
    ).encode("utf-8")


def _entry_points() -> bytes:
    scripts = _project().get("scripts", {})
    values = ["[console_scripts]"] + [f"{name} = {target}" for name, target in sorted(scripts.items())]
    return ("\n".join(values) + "\n").encode("utf-8")


def _wheel_files(
    source_files: list[tuple[str, bytes]] | None = None,
) -> list[tuple[str, bytes]]:
    sources = source_files if source_files is not None else _manifest_files(WHEEL_SOURCE_MANIFEST)
    files = [
        (member.removeprefix("src/"), data)
        for member, data in sources
    ]
    dist_info = _dist_info()
    files.extend(
        [
            (f"{dist_info}/METADATA", _metadata()),
            (f"{dist_info}/WHEEL", _wheel_metadata()),
            (f"{dist_info}/entry_points.txt", _entry_points()),
            (f"{dist_info}/licenses/LICENSE", _source_file("LICENSE")),
        ]
    )
    return files


def _zip_timestamp(epoch: int) -> tuple[int, int, int, int, int, int]:
    normalized = min(max(epoch, _ZIP_MIN_EPOCH), _ZIP_MAX_EPOCH)
    timestamp = time.gmtime(normalized)
    return (
        timestamp.tm_year,
        timestamp.tm_mon,
        timestamp.tm_mday,
        timestamp.tm_hour,
        timestamp.tm_min,
        timestamp.tm_sec - timestamp.tm_sec % 2,
    )


def _zip_info(name: str, epoch: int) -> ZipInfo:
    info = ZipInfo(name, date_time=_zip_timestamp(epoch))
    info.compress_type = ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | _ARCHIVE_FILE_MODE) << 16
    info.internal_attr = 0
    info.extra = b""
    info.comment = b""
    return info


def _tar_info(name: str, data: bytes, epoch: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = _ARCHIVE_FILE_MODE
    info.mtime = epoch
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.type = tarfile.REGTYPE
    info.pax_headers = {}
    return info


def _record_line(name: str, data: bytes) -> tuple[str, str, str]:
    digest = base64.urlsafe_b64encode(sha256(data).digest()).rstrip(b"=").decode("ascii")
    return name, f"sha256={digest}", str(len(data))


def get_requires_for_build_wheel(config_settings: dict[str, Any] | None = None) -> list[str]:
    return []


def prepare_metadata_for_build_wheel(
    metadata_directory: str,
    config_settings: dict[str, Any] | None = None,
) -> str:
    dist_info = _dist_info()
    metadata = _metadata()
    wheel_metadata = _wheel_metadata()
    entry_points = _entry_points()
    target = Path(metadata_directory) / dist_info
    target.mkdir(parents=True, exist_ok=True)
    (target / "METADATA").write_bytes(metadata)
    (target / "WHEEL").write_bytes(wheel_metadata)
    (target / "entry_points.txt").write_bytes(entry_points)
    return dist_info


def build_wheel(
    wheel_directory: str,
    config_settings: dict[str, Any] | None = None,
    metadata_directory: str | None = None,
) -> str:
    epoch = _source_date_epoch()
    source_files = _manifest_files(WHEEL_SOURCE_MANIFEST)
    project = _project()
    filename = f"{_dist_name()}-{project['version']}-py3-none-any.whl"
    target = Path(wheel_directory) / filename
    files = _wheel_files(source_files)
    record = StringIO()
    writer = csv.writer(record, lineterminator="\n")
    for name, data in files:
        writer.writerow(_record_line(name, data))
    record_name = f"{_dist_info()}/RECORD"
    writer.writerow((record_name, "", ""))
    archive_files = files + [(record_name, record.getvalue().encode("utf-8"))]
    with ZipFile(
        target,
        "w",
        compression=ZIP_DEFLATED,
        compresslevel=_ZIP_COMPRESSION_LEVEL,
    ) as wheel:
        for name, data in files:
            wheel.writestr(_zip_info(name, epoch), data)
        wheel.writestr(
            _zip_info(archive_files[-1][0], epoch),
            archive_files[-1][1],
        )
    return filename


def get_requires_for_build_sdist(config_settings: dict[str, Any] | None = None) -> list[str]:
    return []


def build_sdist(
    sdist_directory: str,
    config_settings: dict[str, Any] | None = None,
) -> str:
    epoch = _source_date_epoch()
    source_files = _manifest_files(SDIST_SOURCE_MANIFEST)
    project = _project()
    base = f"{project['name']}-{project['version']}"
    filename = f"{_dist_name()}-{project['version']}.tar.gz"
    archive_files = [
        (f"{base}/{member}", data)
        for member, data in source_files
    ]
    archive_files.append((f"{base}/PKG-INFO", _metadata()))
    target = Path(sdist_directory) / filename
    with target.open("wb") as raw_archive:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            compresslevel=_ZIP_COMPRESSION_LEVEL,
            fileobj=raw_archive,
            mtime=min(epoch, _GZIP_MAX_EPOCH),
        ) as compressed_archive:
            with tarfile.open(
                fileobj=compressed_archive,
                mode="w",
                format=tarfile.PAX_FORMAT,
            ) as archive:
                for name, data in archive_files:
                    archive.addfile(_tar_info(name, data, epoch), BytesIO(data))
    return filename
