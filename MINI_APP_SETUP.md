# BB Coupon Shop Mini App

The Mini App is served at `/mini` and can be opened from the button users see
after accepting the bot terms.

## One-time Telegram configuration

1. Open `@BotFather` and select `@FlashXBBbot`.
2. Choose **Bot Settings → Menu Button → Configure menu button**.
3. Set the button label to `Open Shop` and its URL to:
   `https://bbcouponbot-production.up.railway.app/mini`
4. To make the app launchable directly from the bot profile, configure it as
   the bot's **Main Mini App** in BotFather. Telegram will then expose an
   `Open App` profile button and the direct link
   `https://t.me/FlashXBBbot?startapp`.

## Cashfree configuration

In the Cashfree merchant dashboard, whitelist:

`https://bbcouponbot-production.up.railway.app`

The storefront creates Cashfree orders with the configured payment expiry.
The client timer is visual only; Cashfree's order expiry and the server-side
order state prevent an expired payment from delivering a coupon.
