# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Run the demo service: ``python -m fastapi_basic``."""

import uvicorn

from fastapi_basic.api import app


def main() -> None:
    """Start the FastAPI app on http://127.0.0.1:8000."""
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
