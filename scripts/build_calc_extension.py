"""Build the Shift-Helper LibreOffice Calc extension."""


def _main() -> int:
    from shift_helper.extension_builder import main
    from shift_helper.extension_builder_payload import install_payload_copy

    install_payload_copy()
    return main()


if __name__ == "__main__":
    raise SystemExit(_main())
