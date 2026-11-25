import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from corpus import file_sha256, read_dataset, read_manifest

from validator.batch import measure_batch, run_batch
from validator.preparation import prepare_calls
from validator.selection import Selection, SelectionScan

if TYPE_CHECKING:
    from validator.models import BenchmarkSample


def _run() -> BenchmarkSample:
    request = json.load(sys.stdin)
    dataset = Path(request["dataset"])
    selection_args = request["selection"]
    selection = Selection(
        selection_args["player_count"],
        tuple(selection_args["case_ids"]),
        selection_args["limit"],
    )
    manifest = dataset / "manifest.json"
    manifest_sha256 = file_sha256(manifest)
    case_type = read_manifest(manifest)["case_type"]
    scan = SelectionScan(selection, case_type)
    selected = list(scan.select(read_dataset(dataset)))
    if (
        manifest_sha256 != request["manifest_sha256"]
        or case_type != request["case_type"]
        or scan.selection_sha256 != request["selection_sha256"]
    ):
        msg = "benchmark worker selected a different dataset or case sequence"
        raise ValueError(msg)

    run_batch(prepare_calls(selected))
    return measure_batch(prepare_calls(selected))


if __name__ == "__main__":
    sys.stdout.write(json.dumps(_run()) + "\n")
