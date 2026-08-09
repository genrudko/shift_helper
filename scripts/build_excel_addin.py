from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from shift_helper.excel_builder import build_excel_addin


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Shift-Helper Microsoft Excel XLAM")
    parser.add_argument("--output", type=Path, default=Path("dist/Shift-Helper-Excel.xlam"))
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    output = build_excel_addin(repo_root, args.output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_suffix(output.suffix + ".sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="ascii")
    print(f"built={output}")
    print(f"sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
