from __future__ import annotations

import logging
import sys


# tlck go brrrrrr
def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    from .app import TlckApp

    app = TlckApp()
    sys.exit(app.run(sys.argv))


if __name__ == "__main__":
    main()
