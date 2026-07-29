from __future__ import annotations

import os
from pathlib import Path

from waitress import serve

from shift_helper import create_app


def main() -> None:
    data_root = Path(os.environ.get("SHIFT_HELPER_TEST_DATA_ROOT", ".ui-v2-test-data"))
    port = int(os.environ.get("SHIFT_HELPER_PORT", "17944"))
    app = create_app(testing=True, data_root=data_root)
    serve(app, host="127.0.0.1", port=port, threads=4, clear_untrusted_proxy_headers=True)


if __name__ == "__main__":
    main()
