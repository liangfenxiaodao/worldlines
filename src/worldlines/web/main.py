"""Entry point for the Worldlines web server."""

from __future__ import annotations

import logging

import uvicorn

from worldlines.web.app import create_app
from worldlines.web.config import load_web_config


def main() -> None:
    """Load config, create the FastAPI app, and run via uvicorn."""
    config = load_web_config()

    # Only configure logging if no handlers are set (avoids double-setup
    # when the main scheduler entry point has already configured logging).
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=config.log_level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )

    app = create_app(config)
    uvicorn.run(app, host=config.web_host, port=config.web_port)


if __name__ == "__main__":
    main()
