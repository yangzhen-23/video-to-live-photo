# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import sys


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "convert":
        from .cli import main as cli_main

        return cli_main(sys.argv[1:])
    from .app import main as app_main

    return app_main(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
