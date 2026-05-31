import asyncio
import threading
import uvicorn

from webhook_app import app


def run_fastapi():

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )


def run_bot():

    from bot import main

    asyncio.run(main())


if __name__ == "__main__":

    threading.Thread(
        target=run_fastapi,
        daemon=True
    ).start()

    run_bot()