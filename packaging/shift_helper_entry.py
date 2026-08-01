"""PyInstaller entry point for portable Shift-Helper builds."""

from shift_helper.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
