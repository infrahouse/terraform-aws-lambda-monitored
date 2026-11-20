"""
Terraform version floor test for terraform-aws-lambda-monitored (issue #36).

``required_version`` in ``terraform.tf`` used to allow Terraform 1.0 while the module only loaded on
newer versions, so callers on old versions passed the version check and then failed on configuration
errors. These tests read the floor, the ``>=`` bound of ``required_version``, from ``terraform.tf``,
download that Terraform release, and run ``terraform init -backend=false`` and ``terraform validate``
on a copy of the module. They need no AWS access, so CI runs them (``make test-terraform-floor``)
before the integration tests.
"""

import hashlib
import platform
import re
import shutil
import stat
import subprocess
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path
from typing import List

import pytest

from tests.conftest import LOG

REPO_ROOT = Path(__file__).resolve().parent.parent
RELEASES_URL = "https://releases.hashicorp.com/terraform"
DOWNLOAD_TIMEOUT_SECONDS = 300

# platform.machine() values mapped to the architecture names HashiCorp release archives use.
RELEASE_ARCHITECTURES = {
    "x86_64": "amd64",
    "amd64": "amd64",
    "aarch64": "arm64",
    "arm64": "arm64",
}


def terraform_floor(terraform_tf: str) -> str:
    """
    Find the oldest Terraform version that ``required_version`` allows.

    :param str terraform_tf: Contents of ``terraform.tf``
    :return: The ``>=`` bound of ``required_version`` padded to three components, e.g. ``1.9.0``
        for ``">= 1.9, < 2.0"``
    :rtype: str
    :raise ValueError: If there is no ``required_version``, or it has no ``>=`` bound
    """
    match = re.search(
        r'^\s*required_version\s*=\s*"([^"]*)"', terraform_tf, re.MULTILINE
    )
    if match is None:
        raise ValueError("terraform.tf has no required_version")
    for constraint in match.group(1).split(","):
        bound = re.fullmatch(r"\s*>=\s*(\d+(?:\.\d+){0,2})\s*", constraint)
        if bound:
            parts = bound.group(1).split(".")
            return ".".join(parts + ["0"] * (3 - len(parts)))
    raise ValueError(
        f'required_version = "{match.group(1)}" has no ">=" bound, so the floor test '
        'can\'t tell which Terraform to download. Write it as ">= <floor>, < 2.0".'
    )


def download_terraform(version: str, dest_dir: Path) -> Path:
    """
    Download a Terraform release for this host and check it against the release's SHA256SUMS.

    :param str version: Terraform version, e.g. ``1.9.0``
    :param Path dest_dir: Directory to put the ``terraform`` binary in
    :return: Path to the ``terraform`` binary
    :rtype: Path
    :raise KeyError: If HashiCorp doesn't build Terraform for this host's architecture
    :raise ValueError: If the archive's checksum doesn't match SHA256SUMS
    """
    os_name = platform.system().lower()
    arch = RELEASE_ARCHITECTURES[platform.machine().lower()]
    archive_name = f"terraform_{version}_{os_name}_{arch}.zip"
    LOG.info("Downloading %s/%s/%s", RELEASES_URL, version, archive_name)

    with urllib.request.urlopen(
        f"{RELEASES_URL}/{version}/{archive_name}", timeout=DOWNLOAD_TIMEOUT_SECONDS
    ) as response:
        archive = response.read()
    with urllib.request.urlopen(
        f"{RELEASES_URL}/{version}/terraform_{version}_SHA256SUMS",
        timeout=DOWNLOAD_TIMEOUT_SECONDS,
    ) as response:
        checksums = {}
        for line in response.read().decode().splitlines():
            digest, name = line.split()
            checksums[name] = digest

    actual = hashlib.sha256(archive).hexdigest()
    if actual != checksums[archive_name]:
        raise ValueError(
            f"{archive_name}: SHA256 {actual} doesn't match SHA256SUMS {checksums[archive_name]}"
        )

    with zipfile.ZipFile(BytesIO(archive)) as release:
        binary = Path(release.extract("terraform", dest_dir))
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    return binary


def copy_module(dest_dir: Path) -> None:
    """
    Copy the module's files, tracked and untracked but not ignored, to dest_dir.

    The copy keeps ``terraform init`` from writing ``.terraform/`` and ``.terraform.lock.hcl``
    into the checkout, and leaves out whatever an earlier run left there.

    :param Path dest_dir: Empty directory to copy the module into
    :raise subprocess.CalledProcessError: If ``git ls-files`` fails
    """
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    )
    for name in listing.stdout.decode().split("\0"):
        source = REPO_ROOT / name
        # --cached also lists tracked files deleted from the working tree.
        if name and source.is_file():
            target = dest_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def run_terraform(
    binary: Path, args: List[str], cwd: Path
) -> subprocess.CompletedProcess:
    """
    Run a Terraform command, logging its output.

    :param Path binary: Path to the ``terraform`` binary
    :param list args: Arguments after ``terraform``
    :param Path cwd: Directory to run in
    :return: The finished process, stdout and stderr merged into stdout
    :rtype: subprocess.CompletedProcess
    """
    result = subprocess.run(
        [str(binary), *args, "-no-color"],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    LOG.info(
        "terraform %s exited %d:\n%s", " ".join(args), result.returncode, result.stdout
    )
    return result


class TestTerraformFloor:
    """
    The oldest Terraform that ``required_version`` allows must load the whole module.
    """

    @pytest.mark.parametrize(
        "required_version, floor",
        [
            (">= 1.9, < 2.0", "1.9.0"),
            ("< 2.0, >= 1.9.3", "1.9.3"),
            (">= 1", "1.0.0"),
        ],
        ids=["minor", "patch-second", "major"],
    )
    def test_floor_parses(self, required_version: str, floor: str) -> None:
        """
        Test that the floor is the ``>=`` bound, wherever it is in the constraint, padded to x.y.z.

        :param str required_version: Value of ``required_version``
        :param str floor: Expected floor
        """
        terraform_tf = f'terraform {{\n  required_version = "{required_version}"\n}}\n'
        assert terraform_floor(terraform_tf) == floor

    @pytest.mark.parametrize(
        "terraform_tf",
        [
            'terraform {\n  required_version = "~> 1.9"\n}\n',
            "terraform {\n}\n",
        ],
        ids=["no-lower-bound", "no-required-version"],
    )
    def test_floor_rejects(self, terraform_tf: str) -> None:
        """
        Test that a terraform.tf without a ``>=`` bound fails instead of picking some version.

        :param str terraform_tf: Contents of ``terraform.tf``
        """
        with pytest.raises(ValueError):
            terraform_floor(terraform_tf)

    def test_module_validates_at_floor(self, tmp_path: Path) -> None:
        """
        Test that ``terraform init -backend=false`` and ``terraform validate`` pass on the module
        with the oldest Terraform that ``required_version`` allows.

        Init checks the ``required_version`` of every module it installs, so a submodule that
        needs a newer Terraform fails here too.

        :param Path tmp_path: pytest's per-test temporary directory
        """
        floor = terraform_floor((REPO_ROOT / "terraform.tf").read_text())
        LOG.info("Terraform floor from terraform.tf: %s", floor)
        binary = download_terraform(floor, tmp_path / "bin")
        module_dir = tmp_path / "module"
        copy_module(module_dir)

        version = run_terraform(binary, ["version"], module_dir)
        assert f"Terraform v{floor}\n" in version.stdout, version.stdout

        init = run_terraform(
            binary, ["init", "-backend=false", "-input=false"], module_dir
        )
        assert init.returncode == 0, init.stdout

        validate = run_terraform(binary, ["validate"], module_dir)
        assert validate.returncode == 0, validate.stdout
