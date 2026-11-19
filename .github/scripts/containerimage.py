#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""The repository's images: which to build, their tags, and publishing one.

  containerimage.py list --changed-since <sha>   images whose directory changed since <sha>
  containerimage.py list --base-moved [--all]    published images whose UBI base digest moved
  containerimage.py tags <version> <epoch>       the tags of one release, immutable first
  containerimage.py publish <image>              build, push and record one release

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
"""

import argparse
import base64
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


def get_json(url: str, authorization: str) -> dict:
    request = urllib.request.Request(url, headers={"Authorization": authorization})
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    listing = commands.add_parser("list", help="list images as a JSON array")
    which = listing.add_mutually_exclusive_group(required=True)
    which.add_argument("--changed-since", metavar="SHA")
    which.add_argument("--base-moved", action="store_true")
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

    args = parser.parse_args()
    os.chdir(git("rev-parse", "--show-toplevel").strip())

    if args.command == "list":
        if args.all and not args.base_moved:
            parser.error("--all goes with --base-moved")
        images = (
            base_moved(args.all)
            if args.base_moved
            else changed_since(args.changed_since)
        )
        line = json.dumps(images, separators=(",", ":"))
        if args.github_output:
            append("GITHUB_OUTPUT", f"images={line}")
        print(line)
    elif args.command == "tags":
        try:
            print("\n".join(tags(args.version, args.epoch)))
        except ValueError as error:
            fail(str(error))
    else:
        publish(args.image)


if __name__ == "__main__":
    main()
