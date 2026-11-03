"""Desktop entry point. Lazy imports keep the CLI/core testable without Qt."""


def main() -> None:
    from .app import launch

    launch()


if __name__ == "__main__":
    main()
