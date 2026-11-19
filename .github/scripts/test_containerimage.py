import pytest
from containerimage import changed_images, containerfile_arg, tags

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
