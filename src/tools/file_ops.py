"""File Operations Tool.

Provides safe file read/write operations for the multi-agent workflow.
Includes path validation, directory creation, and error handling to prevent
accidental writes outside designated directories.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Configuration ────────────────────────────────────────────────────

# Allowed base directories for file operations
ALLOWED_BASES: list[Path] = []

# Default working directory (project root)
DEFAULT_WORKING_DIR: Path = Path(__file__).resolve().parent.parent.parent


def set_allowed_bases(*paths: str | Path) -> None:
    """Register directories that file operations are allowed to write to.

    Args:
        *paths: One or more directory paths to allow.
    """
    for p in paths:
        resolved = Path(p).resolve()
        if resolved not in ALLOWED_BASES:
            ALLOWED_BASES.append(resolved)
            logger.info("Added allowed base: %s", resolved)


# Initialize with default working directory
set_allowed_bases(DEFAULT_WORKING_DIR)


# ── Path Validation ──────────────────────────────────────────────────

def _is_path_safe(target: Path) -> tuple[bool, str]:
    """Validate that a target path is within allowed directories.

    Args:
        target: The resolved path to validate.

    Returns:
        Tuple of (is_safe, error_message). If safe, error_message is empty.
    """
    # Ensure the path is absolute and resolved
    if not target.is_absolute():
        return False, f"Path must be absolute: {target}"

    resolved = target.resolve()

    # Check against allowed bases
    for base in ALLOWED_BASES:
        try:
            resolved.relative_to(base)
            return True, ""
        except ValueError:
            continue

    return False, f"Path {resolved} is outside allowed directories: {[str(b) for b in ALLOWED_BASES]}"


def _sanitize_path(filepath: str | Path, working_dir: Optional[Path] = None) -> Path:
    """Sanitize a file path to prevent directory traversal attacks.

    Args:
        filepath: The file path to sanitize (relative or absolute).
        working_dir: Base directory to resolve relative paths against.

    Returns:
        Resolved, sanitized Path object.

    Raises:
        ValueError: If the path contains traversal attempts or is outside allowed dirs.
    """
    # Convert to Path if string
    path = Path(filepath)

    # Reject absolute paths that try to escape (e.g., /etc/passwd)
    if path.is_absolute():
        # Allow if within a working directory context
        if working_dir:
            base = working_dir
        else:
            base = DEFAULT_WORKING_DIR
    else:
        # Relative path — resolve against working directory
        base = working_dir or DEFAULT_WORKING_DIR

    resolved = (base / path).resolve()

    # Check for directory traversal attempts in the original path
    if ".." in Path(filepath).parts:
        raise ValueError(f"Path traversal detected in: {filepath}")

    # Validate safety
    is_safe, error_msg = _is_path_safe(resolved)
    if not is_safe:
        raise ValueError(error_msg)

    return resolved


# ── Write Operations ─────────────────────────────────────────────────

def write_file(
    filepath: str | Path,
    content: str,
    working_dir: Optional[Path] = None,
    encoding: str = "utf-8",
    create_parents: bool = True,
) -> Path:
    """Write content to a file with safety validation.

    Args:
        filepath: Path to write to (relative or absolute).
        content: String content to write.
        working_dir: Base directory for relative paths.
        encoding: File encoding (default: utf-8).
        create_parents: Create parent directories if they don't exist.

    Returns:
        The resolved path of the written file.

    Raises:
        ValueError: If the path is unsafe or traversal is detected.
        OSError: If the file cannot be written.
    """
    resolved = _sanitize_path(filepath, working_dir)

    # Create parent directories if needed
    if create_parents:
        resolved.parent.mkdir(parents=True, exist_ok=True)

    # Write content
    with open(resolved, "w", encoding=encoding) as f:
        f.write(content)

    logger.info("Wrote file: %s (%d bytes)", resolved, len(content))
    return resolved


def write_files(
    files: dict[str | Path, str],
    working_dir: Optional[Path] = None,
    encoding: str = "utf-8",
) -> list[Path]:
    """Write multiple files safely.

    Args:
        files: Dict mapping filepath to content.
        working_dir: Base directory for relative paths.
        encoding: File encoding (default: utf-8).

    Returns:
        List of resolved paths that were written.

    Raises:
        ValueError: If any path is unsafe.
    """
    written: list[Path] = []
    errors: list[str] = []

    for filepath, content in files.items():
        try:
            path = write_file(filepath, content, working_dir, encoding)
            written.append(path)
        except Exception as exc:
            error_msg = f"Failed to write {filepath}: {exc}"
            logger.error(error_msg)
            errors.append(error_msg)

    if errors:
        logger.warning("Wrote %d/%d files (%d errors)", len(written), len(files), len(errors))
    else:
        logger.info("Successfully wrote %d files", len(written))

    return written


# ── Read Operations ──────────────────────────────────────────────────

def read_file(
    filepath: str | Path,
    working_dir: Optional[Path] = None,
    encoding: str = "utf-8",
) -> str:
    """Read content from a file with safety validation.

    Args:
        filepath: Path to read from (relative or absolute).
        working_dir: Base directory for relative paths.
        encoding: File encoding (default: utf-8).

    Returns:
        File content as string.

    Raises:
        ValueError: If the path is unsafe.
        FileNotFoundError: If the file doesn't exist.
    """
    resolved = _sanitize_path(filepath, working_dir)

    with open(resolved, "r", encoding=encoding) as f:
        content = f.read()

    logger.debug("Read file: %s (%d bytes)", resolved, len(content))
    return content


# ── Utility Functions ────────────────────────────────────────────────

def ensure_directory(dirpath: str | Path, working_dir: Optional[Path] = None) -> Path:
    """Ensure a directory exists, creating it if necessary.

    Args:
        dirpath: Directory path to ensure.
        working_dir: Base directory for relative paths.

    Returns:
        Resolved directory path.
    """
    resolved = _sanitize_path(dirpath, working_dir)
    resolved.mkdir(parents=True, exist_ok=True)
    logger.info("Ensured directory exists: %s", resolved)
    return resolved


def list_files(
    directory: str | Path,
    pattern: str = "*",
    working_dir: Optional[Path] = None,
) -> list[Path]:
    """List files in a directory matching a glob pattern.

    Args:
        directory: Directory to search.
        pattern: Glob pattern (default: "*" for all files).
        working_dir: Base directory for relative paths.

    Returns:
        List of matching file paths.
    """
    resolved = _sanitize_path(directory, working_dir)
    files = list(resolved.glob(pattern))
    logger.debug("Listed %d files in %s matching '%s'", len(files), resolved, pattern)
    return files


def delete_file(filepath: str | Path, working_dir: Optional[Path] = None) -> bool:
    """Delete a file with safety validation.

    Args:
        filepath: Path to the file to delete.
        working_dir: Base directory for relative paths.

    Returns:
        True if deleted successfully, False if file didn't exist.

    Raises:
        ValueError: If the path is unsafe.
    """
    resolved = _sanitize_path(filepath, working_dir)

    if not resolved.exists():
        logger.warning("File does not exist, nothing to delete: %s", resolved)
        return False

    resolved.unlink()
    logger.info("Deleted file: %s", resolved)
    return True


def file_exists(filepath: str | Path, working_dir: Optional[Path] = None) -> bool:
    """Check if a file exists with safety validation.

    Args:
        filepath: Path to check.
        working_dir: Base directory for relative paths.

    Returns:
        True if the file exists, False otherwise.
    """
    try:
        resolved = _sanitize_path(filepath, working_dir)
        return resolved.exists()
    except ValueError:
        return False


def get_file_info(filepath: str | Path, working_dir: Optional[Path] = None) -> dict[str, Any]:
    """Get file metadata with safety validation.

    Args:
        filepath: Path to the file.
        working_dir: Base directory for relative paths.

    Returns:
        Dict with file metadata (size, modified time, etc.).
    """
    resolved = _sanitize_path(filepath, working_dir)

    stat = resolved.stat()
    return {
        "path": str(resolved),
        "size_bytes": stat.st_size,
        "modified": stat.st_mtime,
        "is_file": resolved.is_file(),
        "is_dir": resolved.is_dir(),
        "exists": resolved.exists(),
    }
