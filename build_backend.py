"""Small dependency-free PEP 517 backend for the pure-Python GTP CLI."""

from __future__ import annotations

import base64
import csv
from hashlib import sha256
from io import StringIO
from pathlib import Path
import tarfile
import tomllib
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).parent


def _project() -> dict[str, Any]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def _dist_name() -> str:
    return _project()["name"].replace("-", "_")


def _dist_info() -> str:
    return f"{_dist_name()}-{_project()['version']}.dist-info"


def _metadata() -> bytes:
    project = _project()
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
        (ROOT / project["readme"]).read_text(encoding="utf-8"),
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


def _wheel_files() -> list[tuple[str, bytes]]:
    files: list[tuple[str, bytes]] = []
    for path in sorted((ROOT / "src" / "gtp").rglob("*.py")):
        files.append((path.relative_to(ROOT / "src").as_posix(), path.read_bytes()))
    dist_info = _dist_info()
    files.extend(
        [
            (f"{dist_info}/METADATA", _metadata()),
            (f"{dist_info}/WHEEL", _wheel_metadata()),
            (f"{dist_info}/entry_points.txt", _entry_points()),
            (f"{dist_info}/licenses/LICENSE", (ROOT / "LICENSE").read_bytes()),
        ]
    )
    return files


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
    target = Path(metadata_directory) / dist_info
    target.mkdir(parents=True, exist_ok=True)
    (target / "METADATA").write_bytes(_metadata())
    (target / "WHEEL").write_bytes(_wheel_metadata())
    (target / "entry_points.txt").write_bytes(_entry_points())
    return dist_info


def build_wheel(
    wheel_directory: str,
    config_settings: dict[str, Any] | None = None,
    metadata_directory: str | None = None,
) -> str:
    project = _project()
    filename = f"{_dist_name()}-{project['version']}-py3-none-any.whl"
    target = Path(wheel_directory) / filename
    files = _wheel_files()
    record = StringIO()
    writer = csv.writer(record, lineterminator="\n")
    for name, data in files:
        writer.writerow(_record_line(name, data))
    record_name = f"{_dist_info()}/RECORD"
    writer.writerow((record_name, "", ""))
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as wheel:
        for name, data in files:
            wheel.writestr(name, data)
        wheel.writestr(record_name, record.getvalue().encode("utf-8"))
    return filename


def get_requires_for_build_sdist(config_settings: dict[str, Any] | None = None) -> list[str]:
    return []


def build_sdist(
    sdist_directory: str,
    config_settings: dict[str, Any] | None = None,
) -> str:
    project = _project()
    base = f"{project['name']}-{project['version']}"
    filename = f"{base}.tar.gz"
    include = [
        ROOT / "pyproject.toml",
        ROOT / "build_backend.py",
        ROOT / "README.md",
        ROOT / "GTP.md",
        ROOT / "DECISIONS.md",
        ROOT / "LICENSE",
        ROOT / "src",
        ROOT / "tests",
        ROOT / "acceptance",
    ]
    with tarfile.open(Path(sdist_directory) / filename, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for path in include:
            archive.add(path, arcname=f"{base}/{path.relative_to(ROOT)}")
    return filename
