"""Module-safe entrypoint for developer builds and future Windows packaging."""
from construction_docs.desktop import main

if __name__ == "__main__":
    raise SystemExit(main())
