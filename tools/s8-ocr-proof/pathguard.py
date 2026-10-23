"""Fail-closed output-path containment for the S8 OCR proof host tools (Codex F1).

Every write, read and recursive removal by acquire.py, gen_synthetic_png.py and harness.py goes through a `Scratch`:

- The operator names an explicitly approved scratch root: an absolute, canonical path (no symlinked component
  anywhere), owned by the current user, not group- or world-writable, and neither inside nor an ancestor of the
  repository or any protected TrustLens location.
- The root is opened by walking from `/` one component at a time with O_NOFOLLOW | O_DIRECTORY, so a symlink at
  any level is refused rather than followed. That walk also closes the gap between checking a path and opening it.
- Below the root, every directory and file is reached with *at-style calls on held directory descriptors and
  O_NOFOLLOW. Replacing a path component after the Scratch was opened cannot redirect a write: the descriptors
  still point at the original directories.
- Files are written to an O_EXCL temporary name and atomically renamed into place. Recursive removal uses
  shutil.rmtree with dir_fd, and the platform must report `avoids_symlink_attacks`; a symlink is unlinked, never
  followed.

Residual (documented, not hidden): an external program such as the docker CLI is given a path string from
`external_path()`. That string is re-verified component by component immediately before use, but a process running
as the same user could still race it. Same-user attackers are outside this proof's threat model; the root must not
be writable by anyone else.
"""
import hashlib
import os
import re
import secrets
import shutil
import stat
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
_FILE_READ = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
_FILE_CREATE = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


FILE_MODE, DIR_MODE = 0o600, 0o700            # everything the Scratch creates; bound into the build-context manifest


class PathRefused(Exception):
    """A path failed containment. Nothing has been written or removed."""


def protected_locations() -> list:
    home = Path.home()
    paths = [REPO_ROOT, home / ".config" / "trustlens", home / ".local" / "share" / "trustlens", home / ".docker"]
    for variable in ("TRUSTLENS_EVIDENCE_DIR", "TRUSTLENS_EVIDENCE_KEK_FILE"):
        if os.environ.get(variable):
            paths.append(Path(os.environ[variable]).expanduser())
    result = []
    for path in paths:                                     # both the literal and the canonical form are protected
        for form in (Path(os.path.abspath(path)), Path(os.path.realpath(path))):
            if form not in result:
                result.append(form)
    return result


def _related(a: Path, b: Path) -> bool:
    return a == b or a in b.parents or b in a.parents


def _relative_parts(relative: str) -> list:
    if not isinstance(relative, str) or not relative or relative.startswith("/"):
        raise PathRefused(f"not a relative path: {relative!r}")
    parts = relative.split("/")
    if not all(_COMPONENT.match(p) for p in parts) or any(p in (".", "..") for p in parts):
        raise PathRefused(f"path component not allowed: {relative!r}")
    return parts


def _open_absolute_nofollow(path: str) -> int:
    """Open an absolute directory by walking from / with O_NOFOLLOW at every component."""
    fd = os.open("/", _DIR_FLAGS)
    try:
        for component in Path(path).parts[1:]:
            try:
                next_fd = os.open(component, _DIR_FLAGS, dir_fd=fd)
            except OSError as error:
                raise PathRefused(f"{path}: component {component!r} is missing, not a directory, or a symlink "
                                  f"({error.strerror})") from None
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def _check_owned_private(fd: int, label: str) -> None:
    st = os.fstat(fd)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o022:
        raise PathRefused(f"{label} must be a directory owned by this user and not group/world-writable")


class Scratch:
    """One approved workdir inside one approved scratch root. Use as a context manager."""

    def __init__(self, scratch_root: str, workdir: str, protected=None):
        if not shutil.rmtree.avoids_symlink_attacks:
            raise PathRefused("this platform cannot remove directory trees without following symlinks")
        if not isinstance(scratch_root, str) or not os.path.isabs(scratch_root):
            raise PathRefused("the scratch root must be an absolute path")
        normal = os.path.normpath(scratch_root)
        if normal != scratch_root.rstrip("/") or os.path.realpath(normal) != normal:
            raise PathRefused(f"the scratch root must be canonical with no symlinked component "
                              f"(canonical form: {os.path.realpath(normal)})")
        root = Path(normal)
        for location in (protected if protected is not None else protected_locations()):
            if _related(root, Path(location)):
                raise PathRefused(f"the scratch root {root} overlaps protected location {location}")
        self._parts = _relative_parts(workdir)
        self.root, self.workdir = root, root.joinpath(*self._parts)
        self._root_fd = _open_absolute_nofollow(normal)
        try:
            _check_owned_private(self._root_fd, "the scratch root")
            self._work_fd = self._walk(self._root_fd, self._parts, create=True)
        except BaseException:
            os.close(self._root_fd)
            raise

    # -- descriptor walking ---------------------------------------------------------------------------------------
    @staticmethod
    def _walk(base_fd: int, parts: list, create: bool) -> int:
        fd = os.dup(base_fd)
        try:
            for part in parts:
                created = False
                if create:
                    try:
                        os.mkdir(part, 0o700, dir_fd=fd)
                        created = True
                    except FileExistsError:
                        pass
                try:
                    next_fd = os.open(part, _DIR_FLAGS, dir_fd=fd)
                except OSError as error:
                    raise PathRefused(f"{part!r} is missing, not a directory, or a symlink ({error.strerror})") from None
                os.close(fd)
                fd = next_fd
                if created:
                    os.fchmod(fd, DIR_MODE)                     # deterministic, whatever the umask
                _check_owned_private(fd, f"directory {part!r}")
            return fd
        except BaseException:
            os.close(fd)
            raise

    def _parent(self, relative: str, create: bool):
        parts = _relative_parts(relative)
        return self._walk(self._work_fd, parts[:-1], create), parts[-1]

    # -- operations -------------------------------------------------------------------------------------------------
    def write_bytes(self, relative: str, data: bytes) -> None:
        parent, name = self._parent(relative, create=True)
        temporary = f".tmp-{secrets.token_hex(8)}"
        try:
            fd = os.open(temporary, _FILE_CREATE, FILE_MODE, dir_fd=parent)
            try:
                os.fchmod(fd, FILE_MODE)                        # deterministic, whatever the umask
                view = memoryview(data)
                while view:
                    view = view[os.write(fd, view):]
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)   # replaces a symlink, never follows it
        except BaseException:
            try:
                os.unlink(temporary, dir_fd=parent)
            except OSError:
                pass
            raise
        finally:
            os.close(parent)

    def write_text(self, relative: str, text: str) -> None:
        self.write_bytes(relative, text.encode("utf-8"))

    def read_bytes(self, relative: str) -> bytes:
        parent, name = self._parent(relative, create=False)
        try:
            try:
                fd = os.open(name, _FILE_READ, dir_fd=parent)
            except OSError as error:
                raise PathRefused(f"{relative}: missing or a symlink ({error.strerror})") from None
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise PathRefused(f"{relative}: not a regular file")
                chunks = []
                while True:
                    block = os.read(fd, 1 << 20)
                    if not block:
                        return b"".join(chunks)
                    chunks.append(block)
            finally:
                os.close(fd)
        finally:
            os.close(parent)

    def read_text(self, relative: str) -> str:
        return self.read_bytes(relative).decode("utf-8")

    def exists(self, relative: str) -> bool:
        try:
            parent, name = self._parent(relative, create=False)
        except PathRefused:
            return False
        try:
            os.stat(name, dir_fd=parent, follow_symlinks=False)
            return True
        except FileNotFoundError:
            return False
        finally:
            os.close(parent)

    def remove_tree(self, relative: str) -> None:
        """Remove a file, symlink or directory tree below the workdir without following any symlink."""
        parent, name = self._parent(relative, create=False)
        try:
            try:
                st = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                return
            if stat.S_ISDIR(st.st_mode):
                shutil.rmtree(name, dir_fd=parent)
            else:
                os.unlink(name, dir_fd=parent)                  # a symlink itself, never its target
        finally:
            os.close(parent)

    def tree_manifest(self, relative: str) -> list:
        """Deterministic description of every entry below `relative`: path, type, permission bits, and for regular files
        size and SHA-256. Symlinks and special files are reported as such, never followed or read."""
        top = self._walk(self._work_fd, _relative_parts(relative), create=False)
        entries = []

        def visit(dir_fd: int, prefix: str) -> None:
            for name in sorted(os.listdir(dir_fd)):
                st = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
                entry = {"path": prefix + name, "mode": f"{stat.S_IMODE(st.st_mode):04o}"}
                if stat.S_ISDIR(st.st_mode):
                    entries.append({**entry, "type": "dir"})
                    child = os.open(name, _DIR_FLAGS, dir_fd=dir_fd)
                    try:
                        visit(child, entry["path"] + "/")
                    finally:
                        os.close(child)
                elif stat.S_ISREG(st.st_mode):
                    fd = os.open(name, _FILE_READ, dir_fd=dir_fd)
                    try:
                        digest, size = hashlib.sha256(), 0
                        while True:
                            block = os.read(fd, 1 << 20)
                            if not block:
                                break
                            digest.update(block)
                            size += len(block)
                    finally:
                        os.close(fd)
                    entries.append({**entry, "type": "file", "size": size, "sha256": digest.hexdigest()})
                else:
                    entries.append({**entry, "type": "symlink" if stat.S_ISLNK(st.st_mode) else "other"})

        try:
            visit(top, "")
        finally:
            os.close(top)
        return entries

    def make_dir(self, relative: str) -> None:
        os.close(self._walk(self._work_fd, _relative_parts(relative), create=True))

    def external_path(self, relative: str = "", must_exist: bool = True) -> str:
        """Path string for an external program (docker CLI). Re-verified now: canonical root, no symlinked component,
        owned and private directories. See the residual note in the module docstring."""
        os.close(_open_absolute_nofollow(str(self.root)))
        if not relative:
            os.close(self._walk(self._root_fd, self._parts, create=False))
            return str(self.workdir)
        parts = _relative_parts(relative)
        os.close(self._walk(self._root_fd, self._parts + parts[:-1], create=False))
        if must_exist and not self.exists(relative):
            raise PathRefused(f"{relative}: does not exist")
        return str(self.workdir.joinpath(*parts))

    def close(self) -> None:
        for fd in (getattr(self, "_work_fd", None), getattr(self, "_root_fd", None)):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        self._work_fd = self._root_fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False
