from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()


@app.get("/")
async def home():

    return {
        "status": "running",
        "service": "BB Coupon Bot Webhook"
    }


@app.post("/webhook/cashfree")
async def cashfree_webhook():

    return JSONResponse(
        {
            "success": True
        }
    )