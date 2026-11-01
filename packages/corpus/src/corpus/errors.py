"""Errors with record field and optional file position."""

from pathlib import Path


class CorpusError(ValueError):
    def __init__(
        self,
        field: str,
        message: str,
        *,
        path: Path | None = None,
        line: int | None = None,
    ) -> None:
        self.field = field
        self.message = message
        self.path = path
        self.line = line
        location = str(path) if path is not None else ""
        if line is not None:
            location += f":{line}"
        super().__init__(
            f"{location + ': ' if location else ''}{field}: {message}"
        )
