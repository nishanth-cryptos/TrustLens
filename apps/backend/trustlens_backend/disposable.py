"""Disposable-test mode (TRUSTLENS_TEST_DISPOSABLE_DB=1): the one shared fail-closed guard for configuration files.

In disposable mode no loader may read the sponsor's permanent TrustLens configuration (~/.config/trustlens: database
credentials, OIDC client secret, evidence key). guard_env_file() is called BEFORE any existence check, open or dotenv
call, and returns the exact path the caller must load:
- the ORIGINAL ~-expanded path is resolved by the operating-system rules: each symlink is followed before a later ".."
  is applied (there is no lexical normalisation first, which could inspect a different file);
- the resolved destination is refused if it is the resolved permanent directory or lies inside it (path-component
  containment, never a string prefix);
- the caller loads that resolved destination, so the file checked is the file read.
Outside disposable mode the ~-expanded path is returned unchanged and normal development behaviour is preserved.
"""
import os
from pathlib import Path
from typing import Mapping

DISPOSABLE_FLAG = "TRUSTLENS_TEST_DISPOSABLE_DB"
PERMANENT_CONFIG_DIR = Path("~/.config/trustlens")


class PermanentConfigurationRefused(ValueError):
    """Disposable mode refused a permanent configuration path before reading it."""


def disposable_mode(environment: Mapping[str, str] | None = None) -> bool:
    return (os.environ if environment is None else environment).get(DISPOSABLE_FLAG) == "1" \
        or os.environ.get(DISPOSABLE_FLAG) == "1"


def _resolved(path: Path) -> Path:
    try:
        return path.resolve(strict=False)              # realpath semantics: symlink first, then "..", component by component
    except (OSError, RuntimeError):
        raise PermanentConfigurationRefused("configuration path cannot be resolved safely in disposable mode") from None


def is_permanent_path(path) -> bool:
    destination = _resolved(Path(path).expanduser())
    protected = _resolved(PERMANENT_CONFIG_DIR.expanduser())
    return destination == protected or destination.is_relative_to(protected)


def guard_env_file(path, environment: Mapping[str, str] | None = None) -> Path:
    """The path the caller must load. In disposable mode: the resolved destination, refused (before any access) when it is
    permanent configuration. Otherwise: the ~-expanded path, unchanged."""
    expanded = Path(path).expanduser()
    if not disposable_mode(environment):
        return expanded
    destination = _resolved(expanded)
    protected = _resolved(PERMANENT_CONFIG_DIR.expanduser())
    if destination == protected or destination.is_relative_to(protected):
        raise PermanentConfigurationRefused("refusing permanent configuration under ~/.config/trustlens in disposable mode")
    return destination
