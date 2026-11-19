import pytest
from containerimage import (
    changed_images,
    containerfile_arg,
    findings,
    named,
    sarif,
    tags,
)

EPOCH = "1761900000"


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("3.7.3", ["3.7.3-E", "3.7.3", "3.7", "3", "latest"]),
        ("10.0.12", ["10.0.12-E", "10.0.12", "10.0", "10", "latest"]),
        ("0.28.1", ["0.28.1-E", "0.28.1", "0.28", "latest"]),
        ("0.0.1", ["0.0.1-E", "0.0.1", "0.0", "latest"]),
        ("18.6", ["18.6-E", "18.6", "18", "latest"]),
        ("0.9", ["0.9-E", "0.9", "latest"]),
        ("26.10.2.103", ["26.10.2.103-E", "26.10.2.103", "26.10", "latest"]),
        ("0.1.2.3", ["0.1.2.3-E", "0.1.2.3", "0.1", "latest"]),
    ],
)
def test_tags(version: str, expected: list[str]) -> None:
    assert tags(version, EPOCH) == [t.replace("-E", f"-{EPOCH}") for t in expected]


@pytest.mark.parametrize(
    "version",
    [
        "v3.7.3",
        "3",
        "3.7.3.1.2",
        "3.7.3-rc.1",
        "26.10.2.103-stable",
        "03.7.3",
        "3.7.",
        "",
    ],
)
def test_tags_rejects_version(version: str) -> None:
    with pytest.raises(ValueError, match="version"):
        tags(version, EPOCH)


@pytest.mark.parametrize("epoch", ["dev", "", "176190000", "0761900000"])
def test_tags_rejects_epoch(epoch: str) -> None:
    with pytest.raises(ValueError, match="epoch"):
        tags("3.7.3", epoch)


def test_containerfile_arg() -> None:
    text = (
        "# renovate: datasource=github-releases\n"
        "ARG VERSION=0.9.7\n"
        "ARG BASE_IMAGE=registry.access.redhat.com/ubi10/ubi-micro:10.2@sha256:abc\n"
        "FROM ${BASE_IMAGE}\n"
        "ARG VERSION\n"
    )
    assert containerfile_arg(text, "VERSION") == "0.9.7"
    assert containerfile_arg(text, "BASE_IMAGE").endswith("@sha256:abc")
    assert containerfile_arg(text, "RELEASE") == ""


def test_changed_images() -> None:
    images = ["maddy", "mailpit", "prometheus"]
    paths = ["maddy/Containerfile", "README.md", "mailpit/README.md", ".github/x.yml"]
    assert changed_images(paths, images) == ["maddy", "mailpit"]
    assert changed_images(["README.md"], images) == []


def test_named() -> None:
    assert named("mailpit, maddy maddy") == ["maddy", "mailpit"]
    with pytest.raises(SystemExit):
        named("maddy nosuchimage")
    with pytest.raises(SystemExit):
        named(" ")


REPORT = {
    "status": "scanned",
    "data": {
        "Layer": {
            "Features": [
                {
                    "Name": "openssl-libs",
                    "Version": "3.5.1-1.el10",
                    "Vulnerabilities": [
                        {"Name": "CVE-1", "Severity": "High", "FixedBy": ""},
                        {"Name": "CVE-2", "Severity": "Medium", "FixedBy": ""},
                        {"Name": "CVE-3", "Severity": "Low", "FixedBy": "3.5.1-2.el10"},
                    ],
                },
                {
                    "Name": "stdlib",
                    "Version": "1.27.3",
                    "Vulnerabilities": [
                        {
                            "Name": "GO-1",
                            "Severity": "Unknown",
                            "FixedBy": "1.27.4",
                            "NamespaceName": "osv/go",
                            "Link": "https://go.dev/issue/1 https://go.dev/issue/2",
                        }
                    ],
                },
                {"Name": "bash", "Version": "5.2", "Vulnerabilities": None},
            ]
        }
    },
}


def test_findings_keeps_fixable_or_high() -> None:
    kept = findings("maddy", REPORT)
    assert [f["id"] for f in kept] == ["CVE-1", "CVE-3", "GO-1"]
    assert kept[2]["link"] == "https://go.dev/issue/1"


def test_sarif() -> None:
    run = sarif(findings("maddy", REPORT) + findings("mailpit", REPORT))["runs"][0]
    rules = {r["id"]: r for r in run["tool"]["driver"]["rules"]}
    assert sorted(rules) == ["CVE-1", "CVE-3", "GO-1"]
    assert rules["CVE-1"]["properties"]["security-severity"] == "8.0"
    assert "security-severity" not in rules["GO-1"]["properties"]
    assert len(run["results"]) == 6
    first = run["results"][0]
    assert first["level"] == "error"
    assert first["message"]["text"] == (
        "ubi10-maddy: openssl-libs 3.5.1-1.el10, CVE-1 (High), no fix yet"
    )
    location = first["locations"][0]["physicalLocation"]["artifactLocation"]
    assert location["uri"] == "maddy/Containerfile"
    fingerprints = {r["partialFingerprints"]["finding/v1"] for r in run["results"]}
    assert len(fingerprints) == 6
