import ast
import hashlib
from pathlib import Path


def test_report_payload_chunk_hashes() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    loader = (
        repo_root
        / "packaging/libreoffice_extension/Scripts/python/shift_helper_report.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(loader)
    payload = None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == "_PAYLOAD"
            for target in node.targets
        ):
            payload = ast.literal_eval(node.value)
            break
    assert isinstance(payload, bytes)
    print(f"PAYLOAD_LENGTH={len(payload)}")
    for index in range(0, len(payload), 500):
        chunk = payload[index : index + 500]
        digest = hashlib.sha256(chunk).hexdigest()
        print(f"PAYLOAD_CHUNK={index // 500}:{digest}")
    raise AssertionError("temporary payload diagnostics")
