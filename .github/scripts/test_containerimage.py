import datetime

import pytest
from containerimage import (
    changed_images,
    containerfile_arg,
    findings,
    fix_released,
    grade,
    health,
    mini,
    named,
    package_type,
    packages,
    sarif,
    strip,
    tags,
    unapplied,
    write_health,
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


NOW = datetime.datetime(2026, 11, 19, tzinfo=datetime.UTC)


def missing(impact: str, days: int) -> dict:
    return {"impact": impact, "released": NOW - datetime.timedelta(days=days)}


@pytest.mark.parametrize(
    ("fixes", "expected"),
    [
        ([], "A"),
        ([missing("Critical", 7), missing("Important", 30)], "B"),
        ([missing("Critical", 8)], "C"),
        ([missing("Important", 31)], "C"),
        ([missing("Critical", 31)], "D"),
        ([missing("Important", 91)], "D"),
        ([missing("Critical", 91)], "E"),
        ([missing("Important", 365)], "D"),
        ([missing("Critical", 365)], "E"),
        ([missing("Critical", 366)], "F"),
        ([missing("Important", 2), missing("Important", 400)], "F"),
    ],
)
def test_grade(fixes: list[dict], expected: str) -> None:
    assert grade(fixes, NOW) == expected


RHEL_REPORT = {
    "data": {
        "Layer": {
            "Features": [
                {
                    "Name": "openssl-libs",
                    "Version": "1:3.5.1-1.el10_2",
                    "Vulnerabilities": [
                        {
                            "Name": "CVE-2026-1",
                            "Severity": "High",
                            "FixedBy": "1:3.5.1-2.el10_2",
                            "NamespaceName": "rhel-vex",
                        },
                        {
                            "Name": "CVE-2026-2",
                            "Severity": "Medium",
                            "FixedBy": "1:3.5.1-2.el10_2",
                            "NamespaceName": "rhel-vex",
                        },
                        {
                            "Name": "CVE-2026-3",
                            "Severity": "Critical",
                            "FixedBy": "",
                            "NamespaceName": "rhel-vex",
                        },
                    ],
                },
                {
                    "Name": "stdlib",
                    "Version": "1.27.3",
                    "Vulnerabilities": [
                        {
                            "Name": "GO-1",
                            "Severity": "Critical",
                            "FixedBy": "1.27.4",
                            "NamespaceName": "osv/go",
                        }
                    ],
                },
            ]
        }
    }
}

VEX_DOC = {
    "document": {"tracking": {"initial_release_date": "2026-01-01T00:00:00+00:00"}},
    "vulnerabilities": [
        {
            "remediations": [
                {
                    "category": "vendor_fix",
                    "date": "2026-09-01T10:00:00+00:00",
                    "product_ids": [
                        "BaseOS-10.2.Z:openssl-libs-1:3.5.1-2.el10_2.x86_64",
                        "BaseOS-10.2.Z:openssl-1:3.5.1-2.el10_2.x86_64",
                    ],
                },
                {
                    "category": "vendor_fix",
                    "date": "2026-08-01T10:00:00+00:00",
                    "product_ids": [
                        "AppStream-9.6.Z:openssl-libs-1:3.2.2-9.el9_6.x86_64"
                    ],
                },
                {"category": "none_available", "product_ids": []},
            ]
        }
    ],
}


def test_unapplied_counts_released_red_hat_fixes_only() -> None:
    assert unapplied(RHEL_REPORT) == [
        {
            "id": "CVE-2026-1",
            "package": "openssl-libs",
            "fixed_by": "1:3.5.1-2.el10_2",
            "impact": "Important",
        }
    ]


def test_fix_released() -> None:
    exact = fix_released(VEX_DOC, "openssl-libs", "1:3.5.1-2.el10_2")
    assert exact == datetime.datetime.fromisoformat("2026-09-01T10:00:00+00:00")
    # No product at that version: the earliest RHEL 10 fix.
    other = fix_released(VEX_DOC, "openssl-libs", "1:3.5.1-3.el10_2")
    assert other == exact
    # No RHEL 10 fix at all: the CVE's first publication.
    assert fix_released(
        {"document": VEX_DOC["document"]}, "x", "1"
    ) == datetime.datetime.fromisoformat("2026-01-01T00:00:00+00:00")


def test_health() -> None:
    graded = health("maddy", RHEL_REPORT, NOW, lambda cve: VEX_DOC)
    assert graded["grade"] == "C"  # an Important fix released 78 days ago
    assert health("maddy", None, NOW, lambda cve: {})["grade"] == "Unknown"


@pytest.mark.parametrize(
    ("name", "version", "expected"),
    [
        ("openssl-libs", "1:3.5.1-1.el10_2", "RPM"),
        ("postgresql18-server", "18.6-4PGDG.rhel10.2", "RPM"),
        ("io.quarkus:quarkus-core", "3.40.1", "Java"),
        ("golang.org/x/crypto", "v0.58.0", "Go"),
        ("stdlib", "1.27.3", "Go"),
        ("patroni", "4.1.5", "Other"),
        ("ubi10/ubi-minimal", "1793835006", "Image"),
    ],
)
def test_package_type(name: str, version: str, expected: str) -> None:
    assert package_type(name, version) == expected


def test_strip_frames_the_grade() -> None:
    graded = health("maddy", RHEL_REPORT, NOW, lambda cve: VEX_DOC)
    html = strip(graded, NOW)
    assert '<li class="grade-C current">C</li>' in html
    assert html.count("current") == 1
    assert "CVE-2026-1 in openssl-libs, was released 2026-09-01 (78 days ago)" in html
    unknown = strip(health("maddy", None, NOW, lambda cve: {}), NOW)
    assert "current" not in unknown


def test_write_health(tmp_path) -> None:
    graded = {
        **health("maddy", RHEL_REPORT, NOW, lambda cve: VEX_DOC),
        "digest": "sha256:abc",
    }
    write_health(str(tmp_path), [graded], NOW)
    badge = (tmp_path / "badges" / "maddy.json").read_text()
    assert '"message": "C"' in badge and '"color": "yellow"' in badge
    assert (tmp_path / "index.md").read_text().startswith("# Getting started")
    overview = (tmp_path / "health.md").read_text()
    assert "[ubi10-maddy](images/maddy.md)" in overview
    assert '<span class="grade-cell grade-C" title="Grade C">C</span>' in overview
    assert '<span class="generated" hidden></span>' in overview
    page = (tmp_path / "images" / "maddy.md").read_text()
    assert "## Missing security updates" in page
    assert "The 2 with the most findings:" in page
    assert "\n| `openssl-libs` | `1:3.5.1-1.el10_2` | RPM | 3 | 2 |" in page
    assert '??? packages "All 2 packages"' in page
    assert "    | `openssl-libs` | `1:3.5.1-1.el10_2` | RPM | 3 | 2 |" in page
    assert (tmp_path / "health.css").exists()


def test_mini_is_the_grade_alone() -> None:
    assert mini("B") == '<span class="grade-cell grade-B" title="Grade B">B</span>'


def test_packages_merges_layer_duplicates() -> None:
    base = {"Name": "ubi10/ubi-minimal", "Version": "1793835006", "Vulnerabilities": []}
    report = {
        "data": {
            "Layer": {
                "Features": [
                    base,
                    dict(base),
                    RHEL_REPORT["data"]["Layer"]["Features"][0],
                ]
            }
        }
    }
    rows = packages(report)
    assert [(r["name"], r["type"]) for r in rows] == [
        ("ubi10/ubi-minimal", "Image"),
        ("openssl-libs", "RPM"),
    ]
