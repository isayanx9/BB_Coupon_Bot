import asyncio
import os
import threading

import uvicorn

from webhook_app import app


def run_fastapi():
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
    )


def run_bot():
    from bot import main

    asyncio.run(main())


if __name__ == "__main__":
    threading.Thread(
        target=run_fastapi,
        daemon=True,
    ).start()

    run_bot()
