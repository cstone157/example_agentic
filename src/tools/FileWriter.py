import logging
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def write_file(file_path: str, content: str) -> str:
    """Write content to a file on the local filesystem.

    Creates any missing parent directories automatically.
    Overwrites the file if it already exists.

    Args:
        file_path: Absolute or relative path to the file to write.
        content: The text content to write into the file.

    Returns:
        A message confirming success or describing the error.
    """
    try:
        path = Path(file_path)
        if not path.is_absolute():
            # Resolve relative paths against the project root (parent of src/)
            path = Path(__file__).resolve().parent.parent.parent / file_path

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        logger.info("File written: %s (%d bytes)", path, len(content))
        return f"Successfully wrote {len(content)} characters to {path}"

    except Exception as exc:
        error_msg = f"Error writing file '{file_path}': {exc}"
        logger.error(error_msg)
        return error_msg


def get_tools() -> list[Any]:
    """Return a list of available tools for the workflow."""
    return [write_file]
