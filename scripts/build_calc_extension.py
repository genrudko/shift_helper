"""Build the Shift-Helper LibreOffice Calc extension."""


def _main() -> int:
    from shift_helper.extension_builder import main

    return main()


if __name__ == "__main__":
    raise SystemExit(_main())
