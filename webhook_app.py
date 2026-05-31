from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()


@app.get("/")
async def home():

    return {
        "status": "running",
        "service": "BB Coupon Bot Webhook"
    }


@app.post("/webhook/cashfree")
async def cashfree_webhook(request: Request):

    data = await request.json()

    print("CASHFREE WEBHOOK:")
    print(data)

    return JSONResponse(
        {
            "success": True
        }
    )