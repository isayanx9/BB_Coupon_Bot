import requests

TOKEN = "8204687180:AAFqmMeAPOjHuGMdDAywmGlPlxq27ttPick"

url = f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo"

print(requests.get(url).json())