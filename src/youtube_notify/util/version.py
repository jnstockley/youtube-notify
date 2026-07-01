import tomllib
from importlib import metadata
from pathlib import Path


PACKAGE_NAME = "youtube-notify"


def get_version() -> str:
    try:
        return metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        pass

    try:
        pyproject_path = Path(__file__).resolve().parents[3] / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data["project"]["version"]
    except (FileNotFoundError, KeyError):
        return "unknown"
