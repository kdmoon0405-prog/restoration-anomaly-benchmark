"""Explicitly migrate a failed cache after a checkpoint-writer-only source fix."""
from pathlib import Path
import ast
import hashlib

from .analysis_io import digest, read_json, relative_source, write_json
from .cpu_restoration_control import _checkpoint


def pixel_code_sha(path):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    writers = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_checkpoint"]
    if len(writers) != 1:
        raise ValueError("Expected one checkpoint writer")
    tree.body = [node for node in tree.body if node not in writers]
    return hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()


def migrate_writer(cache, previous_source):
    cache, previous_source = Path(cache), Path(previous_source)
    current_source = Path(__file__).with_name("cpu_restoration_control.py")
    state = read_json(cache / "status.json")
    if state["status"] not in ("FAILED", "BLOCKED_RESOURCES"):
        raise ValueError("Only a stopped incomplete cache may migrate")
    if digest(previous_source) != state["binding"]["code_sha256"]:
        raise ValueError("Previous source does not match the failed cache")
    before, after = pixel_code_sha(previous_source), pixel_code_sha(current_source)
    if before != after:
        raise ValueError("Source changed outside the checkpoint writer")
    for sample, row in state["completed"].items():
        if digest(relative_source(cache / "images", sample)) != row["output_sha256"]:
            raise ValueError("Completed RGB changed")
    snapshot = cache / "status-before-writer-migration.json"
    if snapshot.exists():
        if snapshot.read_bytes() != (cache / "status.json").read_bytes():
            raise FileExistsError("Migration snapshot differs from current failed state")
    else:
        snapshot.write_bytes((cache / "status.json").read_bytes())
    proof = dict(previous_source_sha256=digest(previous_source), current_source_sha256=digest(current_source),
        unchanged_code_except_writer_sha256=before, previous_status_sha256=digest(snapshot),
        completed_rgb_verified=len(state["completed"]), prior_error=state.pop("error", None),
        migration_tool_sha256=digest(Path(__file__)),
        scope="checkpoint replacement retries only; image/model/data functions AST-identical")
    state["checkpoint_writer_migration"] = proof
    state["binding"]["code_sha256"] = proof["current_source_sha256"]
    write_json(cache / "checkpoint-writer-migration.json", proof)
    _checkpoint(cache / "status.json", state)
    return proof
