import platform
import sys
import sysconfig
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
lazy from collections.abc import Generator

import mahjong

lazy from validator.models import Environment


def environment_info() -> Environment:
    return {
        "validator_version": version("mahjong-validator"),
        "corpus_version": version("corpus"),
        "mahjong_version": version("mahjong"),
        "mahjong_path": str(Path(mahjong.__file__).resolve().parent),
        "python": sys.version,
        "python_executable": sys.executable,
        "python_implementation": platform.python_implementation(),
        "python_build": list(platform.python_build()),
        "platform": platform.platform(),
        "free_threaded": bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
        "rules_version": "tenhou-ranked-match-v1",
    }


def require_new_directory(output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)


@contextmanager
def result_directory(output: Path) -> Generator[Path]:
    require_new_directory(output)
    with TemporaryDirectory(
        dir=output.parent, prefix=".validator-"
    ) as temporary:
        staging = Path(temporary) / "result"
        staging.mkdir()
        yield staging
        require_new_directory(output)
        staging.rename(output)
