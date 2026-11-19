#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""The repository's images: which to build, their tags, and publishing one.

  containerimage.py list --changed-since <sha>   images whose directory changed since <sha>
  containerimage.py list --base-moved [--all]    published images whose UBI base digest moved
  containerimage.py list --named "<image> ..."   the named images, checked to exist
  containerimage.py tags <version> <epoch>       the tags of one release, immutable first
  containerimage.py publish <image>              build, push and record one release
  containerimage.py scan --sarif <file> [--health <dir>]
                                                 Quay's Clair findings for every image, as SARIF,
                                                 and each image's health grade as a site

An image is a top-level directory holding a tracked Containerfile; it is published as
quay.io/panda-coop/ubi10-<image>. `list` prints a JSON array, or with --github-output writes
it as `images` to GITHUB_OUTPUT.

publish reads from the environment:

  REGISTRY_HOST   registry to log in to (quay environment variable)
  REGISTRY_USER   robot account with write on the image (quay environment variable)
  BASE_IMAGE      overrides ARG BASE_IMAGE (rebuild.yml); empty keeps the Containerfile pin
  GITHUB_SHA, ACTIONS_ID_TOKEN_REQUEST_URL, ACTIONS_ID_TOKEN_REQUEST_TOKEN
                  provided by GitHub Actions; the OIDC pair needs `id-token: write`

and writes ref=<image>@<digest> to GITHUB_OUTPUT and REGISTRY_AUTH_FILE to GITHUB_ENV, so the
sign and sbom steps reuse the login.

scan reads the security scan Quay runs with Clair on each image's :latest, from Quay's public
API, and keeps a finding when it is fixable or High or Critical; the rest stays in Quay's UI.
With --health it grades each image with Red Hat's Container Health Index method (A to F, from
the age of the oldest released Critical or Important fix for a Red Hat package the image lacks;
https://access.redhat.com/articles/2803031), the fix dates from Red Hat's CSAF VEX files, and
writes a page, a shields.io endpoint badge per image and index.json into <dir>.
"""

import argparse
import base64
import datetime
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import NoReturn

REPOSITORY = "quay.io/panda-coop/ubi10-{image}"
PART = r"(0|[1-9][0-9]*)"
VERSION = re.compile(rf"^{PART}(\.{PART}){{1,3}}$")
EPOCH = re.compile(r"^[1-9][0-9]{9,}$")


def fail(message: str) -> NoReturn:
    print(f"::error::{message}", file=sys.stderr)
    sys.exit(1)


def note(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def git(*args: str) -> str:
    return subprocess.run(
        ("git", *args), capture_output=True, text=True, check=True
    ).stdout


def run(*args: str, stdin: str | None = None) -> None:
    note("+ " + " ".join(args))
    subprocess.run(args, input=stdin, text=True, check=True)


def append(name: str, line: str) -> None:
    with open(os.environ[name], "a", encoding="utf-8") as f:
        f.write(line + "\n")


# Images and their Containerfiles


def all_images() -> list[str]:
    files = git("ls-files", "--", "*/Containerfile").split()
    return sorted({f.split("/")[0] for f in files if f.count("/") == 1})


def changed_images(paths: list[str], images: list[str]) -> list[str]:
    """The images among the top-level directories of the changed paths."""
    return sorted({p.split("/")[0] for p in paths if "/" in p} & set(images))


def containerfile_arg(text: str, name: str) -> str:
    """The default of `ARG <name>=` in a Containerfile, or empty."""
    match = re.search(rf"^ARG {name}=(\S+)$", text, re.MULTILINE)
    return match.group(1) if match else ""


def read_arg(image: str, name: str) -> str:
    return containerfile_arg(Path(image, "Containerfile").read_text(), name)


# Tags (ADR 0001)


def tags(version: str, epoch: str) -> list[str]:
    """The tags of one release, the immutable <version>-<epoch> first.

    x.y.z    x.y.z-EPOCH, x.y.z, x.y, x, latest   (a 0.y.z gets no `0`: 0.y is its major)
    x.y      x.y-EPOCH, x.y, x, latest            (a 0.y gets no `0`)
    w.x.y.z  w.x.y.z-EPOCH, w.x.y.z, w.x, latest  (no `w`: a year, not a compatibility promise)
    """
    if not VERSION.match(version):
        raise ValueError(f"version {version!r} is not x.y, x.y.z or w.x.y.z")
    if not EPOCH.match(epoch):
        raise ValueError(f"epoch {epoch!r} is not a Unix timestamp")
    v = version.split(".")
    floating = {
        2: [v[0]] if v[0] != "0" else [],
        3: [f"{v[0]}.{v[1]}"] + ([v[0]] if v[0] != "0" else []),
        4: [f"{v[0]}.{v[1]}"],
    }[len(v)]
    return [f"{version}-{epoch}", version, *floating, "latest"]


# list


def named(names: str) -> list[str]:
    """The images named, space- or comma-separated; an unknown name fails."""
    images = all_images()
    wanted = sorted(set(names.replace(",", " ").split()))
    if not wanted:
        fail("no image named")
    unknown = [n for n in wanted if n not in images]
    if unknown:
        fail(f"not an image directory: {' '.join(unknown)}")
    return wanted


def changed_since(base: str) -> list[str]:
    """Images changed since base; every image for no base, a new branch or an unknown commit."""
    images = all_images()
    known = (
        base.strip("0")
        and subprocess.run(
            ("git", "cat-file", "-e", f"{base}^{{commit}}"),
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )
    if not known:
        return images
    return changed_images(git("diff", "--name-only", base, "HEAD").split(), images)


def skopeo_inspect(ref: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ("skopeo", "inspect", "--no-creds", "--no-tags", *args, f"docker://{ref}"),
        capture_output=True,
        text=True,
        check=False,
    )


def base_moved(every: bool) -> list[dict[str, str]]:
    """Published images whose base tag now resolves to another digest than they were built on.

    base_image is the tag pinned to the current digest, for the rebuild to use.
    """
    moved = []
    for image in all_images():
        pin = read_arg(image, "BASE_IMAGE")
        if not pin:
            note(f"{image}: no ARG BASE_IMAGE, skipped")
            continue
        base = pin.split("@")[0]
        current = skopeo_inspect(base, "--format", "{{.Digest}}")
        if current.returncode:
            fail(f"{image}: cannot resolve {base}: {current.stderr.strip()}")
        current_digest = current.stdout.strip()
        published = skopeo_inspect(REPOSITORY.format(image=image) + ":latest")
        if published.returncode:
            note(f"{image}: not published yet, skipped (release.yml publishes it)")
            continue
        labels = json.loads(published.stdout).get("Labels") or {}
        built_on = labels.get("org.opencontainers.image.base.name", "").split("@")[-1]
        if every or built_on != current_digest:
            note(f"{image}: base {built_on} -> {current_digest}")
            moved.append({"image": image, "base_image": f"{base}@{current_digest}"})
        else:
            note(f"{image}: base {current_digest} unchanged")
    return moved


# publish


def get_json(url: str, authorization: str = "") -> dict:
    headers = {"Authorization": authorization} if authorization else {}
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        fail(f"{url.split('?')[0]}: HTTP {error.code}")


def robot_token(host: str, user: str) -> str:
    """Exchange GitHub's OIDC token (audience quay) for a short-lived robot token."""
    oidc = get_json(
        os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"] + "&audience=quay",
        "bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"],
    ).get("value")
    if not oidc:
        fail("no OIDC token from GitHub: the job needs `id-token: write`")
    print(f"::add-mask::{oidc}", flush=True)
    basic = base64.b64encode(f"{user}:{oidc}".encode()).decode()
    token = get_json(
        f"https://{host}/oauth2/federation/robot/token", "Basic " + basic
    ).get("token")
    if not token:
        fail(f"no token from {host} for {user}: check the robot's federation entry")
    print(f"::add-mask::{token}", flush=True)
    return token


def publish(image: str) -> None:
    env = os.environ
    if image not in all_images():
        fail(f"{image} is not an image directory")
    # Fail loudly and early: without these the push fails after the whole build.
    for name in ("REGISTRY_HOST", "REGISTRY_USER"):
        if not env.get(name):
            fail(f"{name} is unset: set it in the quay environment's variables")
    for name in ("GITHUB_SHA", "GITHUB_OUTPUT", "GITHUB_ENV"):
        if not env.get(name):
            fail(f"{name} is unset: publish runs in GitHub Actions")
    host, user = env["REGISTRY_HOST"], env["REGISTRY_USER"]

    repository = REPOSITORY.format(image=image)
    epoch = int(time.time())
    created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))
    try:
        release = tags(read_arg(image, "VERSION"), str(epoch))
    except ValueError as error:
        fail(f"{image}: {error}")

    args = ["--build-arg", f"RELEASE={epoch}"]
    args += ["--build-arg", f"REVISION={env['GITHUB_SHA']}"]
    args += ["--build-arg", f"CREATED={created}"]
    if env.get("BASE_IMAGE"):
        args += ["--build-arg", f"BASE_IMAGE={env['BASE_IMAGE']}"]
    for tag in release:
        args += ["-t", f"{repository}:{tag}"]
    # Docker format: the OCI format drops SHELL and HEALTHCHECK, and the RUN steps rely on
    # bash -o pipefail.
    run(
        "buildah",
        "build",
        "--format",
        "docker",
        *args,
        "-f",
        f"{image}/Containerfile",
        image,
    )

    # The Docker-format auth file, the one cosign and syft read.
    auth_file = Path.home() / ".docker" / "config.json"
    auth_file.parent.mkdir(parents=True, exist_ok=True)
    os.environ["REGISTRY_AUTH_FILE"] = str(auth_file)
    append("GITHUB_ENV", f"REGISTRY_AUTH_FILE={auth_file}")
    token = robot_token(host, user)
    run("buildah", "login", "-u", user, "--password-stdin", host, stdin=token)

    # The immutable <version>-<epoch> tag goes first; the floating tags follow it. v2s2 keeps
    # the Docker manifest the build produced.
    first, *floating = release
    push = ("buildah", "push", "--format", "v2s2")
    run(*push, "--digestfile", "digest", f"{repository}:{first}")
    for tag in floating:
        run(*push, f"{repository}:{tag}")

    ref = f"{repository}@{Path('digest').read_text().strip()}"
    append("GITHUB_OUTPUT", f"ref={ref}")
    if env.get("GITHUB_STEP_SUMMARY"):
        append("GITHUB_STEP_SUMMARY", f"pushed {ref}: {' '.join(release)}")


# scan

SEVERITIES = ("Critical", "High", "Medium", "Low", "Negligible", "Unknown")
# GitHub ranks code-scanning alerts by security-severity: >= 9 critical, >= 7 high, >= 4
# medium, else low.
SECURITY_SEVERITY = {"Critical": "9.5", "High": "8.0", "Medium": "5.5", "Low": "3.0"}


def quay_api(image: str, path: str) -> dict:
    host, repository = REPOSITORY.format(image=image).split("/", 1)
    return get_json(f"https://{host}/api/v1/repository/{repository}/{path}")


def findings(image: str, report: dict) -> list[dict[str, str]]:
    """The kept findings of one Clair report: fixable, or High or Critical."""
    kept = []
    for feature in (report.get("data") or {}).get("Layer", {}).get("Features", []):
        for vulnerability in feature.get("Vulnerabilities") or []:
            severity = vulnerability.get("Severity") or "Unknown"
            if severity not in SEVERITIES:
                severity = "Unknown"
            fixed_by = vulnerability.get("FixedBy") or ""
            if not fixed_by and severity not in ("Critical", "High"):
                continue
            kept.append(
                {
                    "image": image,
                    "id": vulnerability["Name"],
                    "package": feature["Name"],
                    "version": feature["Version"],
                    "severity": severity,
                    "fixed_by": fixed_by,
                    "source": vulnerability.get("NamespaceName") or "",
                    "link": (vulnerability.get("Link") or "").split(" ")[0],
                    "description": (vulnerability.get("Description") or "").strip(),
                }
            )
    return kept


def sarif(kept: list[dict[str, str]]) -> dict:
    """One SARIF run, a rule per vulnerability id and a result per image and package."""
    rules: dict[str, dict] = {}
    results = []
    for f in sorted(kept, key=lambda f: (f["image"], f["package"], f["id"])):
        rule = rules.setdefault(
            f["id"],
            {
                "id": f["id"],
                "shortDescription": {"text": f["id"]},
                "fullDescription": {"text": f["description"] or f["id"]},
                "helpUri": f["link"] or None,
                "properties": {
                    "tags": ["security", f["source"]],
                    "severity": "Unknown",
                },
            },
        )
        # A rule carries the highest severity any of its findings has.
        if SEVERITIES.index(f["severity"]) < SEVERITIES.index(
            rule["properties"]["severity"]
        ):
            rule["properties"]["severity"] = f["severity"]
        fix = f"fixed in {f['fixed_by']}" if f["fixed_by"] else "no fix yet"
        results.append(
            {
                "ruleId": f["id"],
                "level": "error"
                if f["severity"] in ("Critical", "High")
                else "warning",
                "message": {
                    "text": f"ubi10-{f['image']}: {f['package']} {f['version']}, "
                    f"{f['id']} ({f['severity']}), {fix}"
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": f"{f['image']}/Containerfile"},
                            "region": {"startLine": 1},
                        }
                    }
                ],
                "partialFingerprints": {
                    "finding/v1": f"{f['image']}/{f['package']}/{f['id']}"
                },
            }
        )
    for rule in rules.values():
        severity = rule["properties"].pop("severity")
        if severity in SECURITY_SEVERITY:
            rule["properties"]["security-severity"] = SECURITY_SEVERITY[severity]
        if rule["helpUri"] is None:
            del rule["helpUri"]
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Clair",
                        "informationUri": "https://quay.github.io/clair/",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }


# health (Red Hat's Container Health Index method)

# The best grade whose limits every missing fix keeps: days since a missing Critical fix was
# released, days since a missing Important one was. Worse than E is F.
GRADE_LIMITS = (("B", 7, 30), ("C", 30, 90), ("D", 90, 365), ("E", 365, 365))
GRADE_COLOURS = {
    "A": "brightgreen",
    "B": "green",
    "C": "yellow",
    "D": "orange",
    "E": "red",
    "F": "critical",
    "Unknown": "lightgrey",
}
# Clair reports Red Hat's own rating for RHEL packages; its High is Red Hat's Important.
IMPACT = {"Critical": "Critical", "High": "Important"}
VEX = "https://security.access.redhat.com/data/csaf/v2/vex/{year}/{cve}.json"
CVE = re.compile(r"^CVE-(\d{4})-\d+$")


def unapplied(report: dict) -> list[dict[str, str]]:
    """Released Critical or Important fixes for Red Hat packages the image does not have."""
    missing = []
    for feature in (report.get("data") or {}).get("Layer", {}).get("Features", []):
        for vulnerability in feature.get("Vulnerabilities") or []:
            impact = IMPACT.get(vulnerability.get("Severity") or "")
            if (
                vulnerability.get("NamespaceName") == "rhel-vex"
                and vulnerability.get("FixedBy")
                and impact
            ):
                missing.append(
                    {
                        "id": vulnerability["Name"],
                        "package": feature["Name"],
                        "fixed_by": vulnerability["FixedBy"],
                        "impact": impact,
                    }
                )
    return missing


def fix_released(vex: dict, package: str, fixed_by: str) -> datetime.datetime | None:
    """When Red Hat released the fix: the vendor_fix naming the package at that version, else
    the earliest RHEL 10 vendor_fix, else the CVE's first publication."""
    version = re.escape(fixed_by.split(":")[-1])
    exact = re.compile(rf":{re.escape(package)}-\d+:{version}\.")
    dates, rhel10 = [], []
    for vulnerability in vex.get("vulnerabilities", []):
        for remediation in vulnerability.get("remediations", []):
            if remediation.get("category") != "vendor_fix" or not remediation.get(
                "date"
            ):
                continue
            products = remediation.get("product_ids", [])
            date = datetime.datetime.fromisoformat(remediation["date"])
            if any(exact.search(p) for p in products):
                dates.append(date)
            if any(
                p.startswith(("BaseOS-10", "AppStream-10", "CRB-10")) for p in products
            ):
                rhel10.append(date)
    if dates or rhel10:
        return min(dates or rhel10)
    published = vex.get("document", {}).get("tracking", {}).get("initial_release_date")
    return datetime.datetime.fromisoformat(published) if published else None


def grade(missing: list[dict], now: datetime.datetime) -> str:
    ages = [(m["impact"], (now - m["released"]).days) for m in missing]
    if not ages:
        return "A"
    for letter, critical, important in GRADE_LIMITS:
        if all(
            age <= (critical if impact == "Critical" else important)
            for impact, age in ages
        ):
            return letter
    return "F"


def health(image: str, report: dict | None, now: datetime.datetime, vex) -> dict:
    """One image's grade; vex(cve) returns Red Hat's VEX document for a CVE, or {}."""
    if report is None:
        return {"image": image, "grade": "Unknown", "missing": [], "packages": []}
    missing = []
    for m in unapplied(report):
        match = CVE.match(m["id"])
        released = (
            fix_released(vex(m["id"]), m["package"], m["fixed_by"]) if match else None
        )
        # An undated fix counts as released now: it cannot be dated, so it is not aged.
        missing.append({**m, "released": released or now})
    missing.sort(key=lambda m: m["released"])
    return {
        "image": image,
        "grade": grade(missing, now),
        "missing": missing,
        "packages": packages(report),
    }


def package_type(name: str, version: str) -> str:
    # Clair lists the Red Hat images an image is built from (ubi10/ubi-minimal and the like)
    # with Red Hat's build timestamp as the version.
    if "/" in name and re.fullmatch(r"\d{9,}", version):
        return "Image"
    if re.search(r"\.(el|rhel)\d", version):
        return "RPM"
    if ":" in name:
        return "Java"
    if "/" in name or name == "stdlib":
        return "Go"
    return "Other"


def packages(report: dict | None) -> list[dict]:
    # One row per name and version: Clair repeats a package once per layer it found it in.
    rows: dict[tuple[str, str], dict] = {}
    for feature in (
        ((report or {}).get("data") or {}).get("Layer", {}).get("Features", [])
    ):
        found = feature.get("Vulnerabilities") or []
        key = (feature["Name"], feature["Version"])
        row = rows.setdefault(
            key,
            {
                "name": feature["Name"],
                "version": feature["Version"],
                "type": package_type(feature["Name"], feature["Version"]),
                "findings": 0,
                "fixable": 0,
            },
        )
        row["findings"] = max(row["findings"], len(found))
        row["fixable"] = max(row["fixable"], sum(1 for v in found if v.get("FixedBy")))
    order = ("Image", "RPM", "Go", "Java", "Other")
    return sorted(
        rows.values(), key=lambda r: (order.index(r["type"]), r["name"].lower())
    )


GRADE_TEXT = {
    "A": "No released Critical or Important update for a Red Hat package is missing.",
    "Unknown": "Quay has not scanned this image yet; the grade follows its next scan.",
}


def strip(g: dict, now: datetime.datetime) -> str:
    """The A to F strip, the current grade framed, with its explanation."""
    cells = "".join(
        f'<li class="grade-{x}{" current" if x == g["grade"] else ""}">{x}</li>'
        for x in "ABCDEF"
    )
    if g["grade"] in GRADE_TEXT:
        text = GRADE_TEXT[g["grade"]]
    else:
        oldest = g["missing"][0]
        days = (now - oldest["released"]).days
        text = (
            f"{len(g['missing'])} released Critical or Important update(s) for Red Hat "
            f"packages missing; the oldest, {html.escape(oldest['id'])} in "
            f"{html.escape(oldest['package'])}, was released "
            f"{oldest['released']:%Y-%m-%d} ({days} days ago)."
        )
    return (
        '<div class="health-index">\n'
        '<p class="health-title">Health grade</p>\n'
        f'<ol class="health-grades">{cells}</ol>\n'
        f'<p class="health-text"><strong>{text}</strong><br>\n'
        "Only RPM packages signed by Red Hat are graded; other software in the image is "
        "not.</p>\n"
        f'<p class="health-asof">Graded on {now:%d %b %Y, %H:%M} UTC</p>\n'
        '<p class="health-note">Calculated by this project with the method Red Hat publishes '
        'for its <a href="https://access.redhat.com/articles/2803031">Container Health '
        "Index</a>. Not issued by, affiliated with or endorsed by Red Hat.</p>\n"
        "</div>\n"
    )


def cell(text: str) -> str:
    return str(text).replace("|", "\\|")


def write_health(directory: str, grades: list[dict], now: datetime.datetime) -> None:
    """The health site's Markdown for Zensical, plus a shields.io endpoint badge per image."""
    root = Path(directory)
    for sub in ("badges", "images"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    # The site's fixed files: its stylesheet, and the getting-started page as its home, at
    # the path the edit button points to.
    static = Path(__file__).resolve().parent.parent / "health"
    for name in ("health.css", "index.md"):
        (root / name).write_text((static / name).read_text())

    for g in grades:
        badge = {
            "schemaVersion": 1,
            "label": "health",
            "message": g["grade"],
            "color": GRADE_COLOURS[g["grade"]],
        }
        (root / "badges" / f"{g['image']}.json").write_text(json.dumps(badge) + "\n")

    summary = [
        {
            "image": g["image"],
            "grade": g["grade"],
            "missing": [
                {**m, "released": m["released"].date().isoformat()}
                for m in g["missing"]
            ],
        }
        for g in grades
    ]
    as_of = now.strftime("%Y-%m-%d %H:%M UTC")
    (root / "health.json").write_text(
        json.dumps({"as_of": as_of, "images": summary}, indent=1) + "\n"
    )

    rows = []
    for g in grades:
        pkgs = g["packages"]
        rows.append(
            f"| [ubi10-{g['image']}](images/{g['image']}.md) "
            f"| {mini(g['grade'])} "
            f"| {len(g['missing'])} | {len(pkgs)} "
            f"| {sum(p['findings'] for p in pkgs)} |"
        )
    (root / "health.md").write_text(
        OVERVIEW.format(as_of=as_of, rows="\n".join(rows)), encoding="utf-8"
    )

    for g in grades:
        image = g["image"]
        repository = REPOSITORY.format(image=image)
        quay = "https://" + repository.replace("quay.io/", "quay.io/repository/", 1)
        lines = [
            f"# ubi10-{image}",
            "",
            GENERATED,
            "",
            strip(g, now),
            "| Item | Value |",
            "|---|---|",
            f"| Repository | [`{repository}`]({quay}) |",
            f"| Scanned | `:latest`, `{g.get('digest') or 'not scanned'}` |",
            f"| Source | [`{image}/`]({GITHUB}/tree/main/{image}) |",
            f"| Base | `{cell(read_arg(image, 'BASE_IMAGE').split('@')[0])}` |",
            "",
            "## Missing security updates",
            "",
        ]
        if g["missing"]:
            lines += [
                "| Flaw | Impact | Package | Fixed in | Released |",
                "|---|---|---|---|---|",
            ]
            for m in g["missing"]:
                cve = m["id"]
                lines.append(
                    f"| [{cve}](https://access.redhat.com/security/cve/{cve.lower()}) "
                    f"| {m['impact']} | `{cell(m['package'])}` | `{cell(m['fixed_by'])}` "
                    f"| {m['released']:%Y-%m-%d} |"
                )
        else:
            lines.append("None.")
        pkgs = g["packages"]
        counts = ", ".join(
            f"{sum(1 for p in pkgs if p['type'] == t)} {t}"
            for t in ("Image", "RPM", "Go", "Java", "Other")
            if any(p["type"] == t for p in pkgs)
        )
        lines += [
            "",
            "## Packages",
            "",
            (
                f"{len(pkgs)} packages ({counts or 'none'}), as Clair found them. "
                "Findings are every known flaw, fixed or not; Fixable is how many have a fix."
            ),
            "",
        ]
        if pkgs:
            flagged = sorted(pkgs, key=lambda p: (-p["findings"], -p["fixable"]))
            lines += [
                f"The {min(PREVIEW, len(pkgs))} with the most findings:",
                "",
                *package_table(flagged[:PREVIEW]),
                "",
                # Folded: an image can hold a thousand packages.
                f'??? packages "All {len(pkgs)} packages"',
                "",
                *("    " + row for row in package_table(pkgs)),
            ]
        lines += [
            "",
            "## Releases",
            "",
            (
                "Releases on Quay, newest first. A release tag never moves; the other "
                "tags follow the newest release of their line. Each release graded as "
                "of today."
            ),
            "",
        ]
        history = g.get("releases") or []
        if not history:
            lines.append("None yet.")
        elif len(history) <= PREVIEW:
            lines += release_table(history)
        else:
            lines += [
                *release_table(history[:PREVIEW]),
                "",
                f'??? releases "All {len(history)} releases"',
                "",
                *("    " + row for row in release_table(history)),
            ]
        containerfile = Path(image, "Containerfile").read_text().rstrip("\n")
        lines += [
            "",
            "## Containerfile",
            "",
            f"[`{image}/Containerfile`]({GITHUB}/blob/main/{image}/Containerfile) on `main`:",
            "",
            "```dockerfile",
            containerfile,
            "```",
        ]
        (root / "images" / f"{image}.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )


GITHUB = "https://github.com/panda-coop/containers"
PREVIEW = 10


def mini(letter: str) -> str:
    """The grade alone, framed with its colour bar, as it stands in the health index."""
    return f'<span class="grade-cell grade-{letter}" title="Grade {letter}">{letter}</span>'


def package_table(pkgs: list[dict]) -> list[str]:
    return [
        "| Package | Version | Type | Findings | Fixable |",
        "|---|---|---|---|---|",
        *(
            f"| `{cell(p['name'])}` | `{cell(p['version'])}` | {p['type']} "
            f"| {p['findings']} | {p['fixable']} |"
            for p in pkgs
        ),
    ]


def release_table(history: list[dict]) -> list[str]:
    return [
        "| Release | Published | Grade | Also tagged | Digest |",
        "|---|---|---|---|---|",
        *(
            f"| `{r['tag']}` | {r['published']:%Y-%m-%d %H:%M} | {mini(r['grade'])} "
            f"| {', '.join(f'`{t}`' for t in r['floating'])} | `{r['digest'][:19]}` |"
            for r in history
        ),
    ]


GENERATED = '<span class="generated" hidden></span>'

OVERVIEW = """# Image health

<span class="generated" hidden></span>

Each image's `:latest`, graded with the method Red Hat publishes for its
[Container Health Index](https://access.redhat.com/articles/2803031): **A** means no released
Critical or Important security update for a Red Hat package is missing; **B** to **F** grade
the age of the oldest one that is. Only RPM packages signed by Red Hat count.

The packages and flaws come from the scan [Quay](https://quay.io/organization/panda-coop) runs
with Clair on every pushed image; the release dates of the fixes from Red Hat Product
Security's [CSAF VEX data](https://security.access.redhat.com/data/csaf/v2/vex/). Computed
daily by this repository's scan workflow, not issued by Red Hat. As of {as_of}.

| Image | Grade | Missing updates | Packages | Findings |
|---|---|---|---|---|
{rows}

Machine-readable: [health.json](health.json), and a
[shields.io](https://shields.io/badges/endpoint-badge) endpoint badge per image under
`badges/<image>.json`.
"""


RELEASE_TAG = re.compile(r"-[1-9][0-9]{9,}$")


def releases(image: str, now: datetime.datetime, vex, keep: int = 30) -> list[dict]:
    """The newest releases on Quay, each with the floating tags on it and its grade."""
    tags_on: dict[str, list[str]] = {}
    found = []
    page = 1
    while True:
        listing = quay_api(image, f"tag/?onlyActiveTags=true&limit=100&page={page}")
        for tag in listing.get("tags", []):
            tags_on.setdefault(tag["manifest_digest"], []).append(tag["name"])
            if RELEASE_TAG.search(tag["name"]):
                found.append(tag)
        if not listing.get("has_additional"):
            break
        page += 1
    found.sort(key=lambda t: t["start_ts"], reverse=True)
    history = []
    for tag in found[:keep]:
        digest = tag["manifest_digest"]
        report = quay_api(image, f"manifest/{digest}/security?vulnerabilities=true")
        scanned = report if report.get("status") == "scanned" else None
        history.append(
            {
                "tag": tag["name"],
                "published": datetime.datetime.fromtimestamp(
                    tag["start_ts"], datetime.UTC
                ),
                "digest": digest,
                "floating": sorted(t for t in tags_on[digest] if t != tag["name"]),
                "grade": health(image, scanned, now, vex)["grade"],
            }
        )
    return history


def scan(path: str, health_dir: str | None = None) -> None:
    kept, grades = [], []
    now = datetime.datetime.now(datetime.UTC)
    documents: dict[str, dict] = {}

    def vex(cve: str) -> dict:
        if cve not in documents:
            year = CVE.match(cve).group(1)
            # A CVE Red Hat has no VEX file for yet is dated by the fallbacks.
            url = VEX.format(year=year, cve=cve.lower())
            try:
                with urllib.request.urlopen(url, timeout=30) as response:
                    documents[cve] = json.load(response)
            except urllib.error.HTTPError:
                documents[cve] = {}
        return documents[cve]

    for image in all_images():
        tags_page = quay_api(image, "tag/?specificTag=latest&onlyActiveTags=true")
        if not tags_page.get("tags"):
            note(f"{image}: not published yet, skipped")
            continue
        digest = tags_page["tags"][0]["manifest_digest"]
        report = quay_api(image, f"manifest/{digest}/security?vulnerabilities=true")
        if report.get("status") != "scanned":
            note(f"{image}: Quay scan {report.get('status')}, skipped")
            grades.append(health(image, None, now, vex))
            continue
        found = findings(image, report)
        graded = {**health(image, report, now, vex), "digest": digest}
        if health_dir:
            graded["releases"] = releases(image, now, vex)
        grades.append(graded)
        note(f"{image}: {len(found)} findings kept, health {grades[-1]['grade']}")
        kept += found
    Path(path).write_text(json.dumps(sarif(kept), indent=1) + "\n")
    note(f"{len(kept)} findings in {path}")
    if health_dir:
        write_health(health_dir, grades, now)
        note(f"health of {len(grades)} images in {health_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    listing = commands.add_parser("list", help="list images as a JSON array")
    which = listing.add_mutually_exclusive_group(required=True)
    which.add_argument("--changed-since", metavar="SHA")
    which.add_argument("--base-moved", action="store_true")
    which.add_argument("--named", metavar="IMAGES")
    listing.add_argument(
        "--all", action="store_true", help="with --base-moved: every published image"
    )
    listing.add_argument(
        "--github-output", action="store_true", help="write images=... to GITHUB_OUTPUT"
    )

    tagging = commands.add_parser("tags", help="print the tags of one release")
    tagging.add_argument("version")
    tagging.add_argument("epoch")

    publishing = commands.add_parser(
        "publish", help="build, push and record one release"
    )
    publishing.add_argument("image")

    scanning = commands.add_parser("scan", help="Quay's Clair findings as SARIF")
    scanning.add_argument("--sarif", required=True, metavar="FILE")
    scanning.add_argument("--health", metavar="DIR", help="write the health site here")

    args = parser.parse_args()
    os.chdir(git("rev-parse", "--show-toplevel").strip())

    if args.command == "list":
        if args.all and not args.base_moved:
            parser.error("--all goes with --base-moved")
        if args.base_moved:
            images = base_moved(args.all)
        elif args.named is not None:
            images = named(args.named)
        else:
            images = changed_since(args.changed_since)
        line = json.dumps(images, separators=(",", ":"))
        if args.github_output:
            append("GITHUB_OUTPUT", f"images={line}")
        print(line)
    elif args.command == "tags":
        try:
            print("\n".join(tags(args.version, args.epoch)))
        except ValueError as error:
            fail(str(error))
    elif args.command == "scan":
        scan(args.sarif, args.health)
    else:
        publish(args.image)


if __name__ == "__main__":
    main()
