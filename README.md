# FlashXBBbot

Production-ready Telegram coupon bot for BigBasket coupon sales with Cashfree payments, wallet credits, referrals, AI support, analytics and admin controls.

## Stack

- Node.js 20+
- PostgreSQL
- Telegram Bot API
- Cashfree PG
- Railway-ready deployment
- Docker support

## Features

- Telegram user onboarding and required channel verification
- Coupon categories, images, stock, expiry and search
- Cashfree payment sessions, webhook completion and duplicate protection
- Wallet credits and wallet usage during purchases
- Referral rewards, referral leaderboard and referral history storage
- Daily rewards and streak credits
- AI support assistant restricted to bot, coupon, wallet, referral, order and payment questions
- AI memory, support conversations and approved knowledge base tables
- Admin Telegram panel for dashboard, coupon upload, broadcast, wallet credit, ban/unban, logs and backups
- Private web admin dashboard at `/admin?token=ADMIN_WEB_TOKEN`
- Health endpoint at `/health`
- Auto database migration on startup
- Audit logs, payment logs and backup snapshots
- Basic anti-spam/rate limiting and Express rate limits

## Environment Variables

```env
BOT_TOKEN=
DATABASE_URL=
PUBLIC_BASE_URL=
CASHFREE_CLIENT_ID=
CASHFREE_CLIENT_SECRET=
ADMIN_USER_ID=
REQUIRED_CHANNELS=@FlashXDeal,@FlashXSupports
NODE_ENV=production
PORT=3000
CASHFREE_ENV=production
CASHFREE_WEBHOOK_SECRET=
ADMIN_WEB_TOKEN=
SUPPORT_USERNAME=@FlashXSupports
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

## Local Run

```bash
npm install
npm run migrate
npm start
```

## Railway Deploy

1. Create a Railway PostgreSQL database.
2. Set all required variables from `.env.example`.
3. Deploy from GitHub.
4. Set Cashfree webhook URL to:

```text
https://YOUR_PUBLIC_DOMAIN/webhook/cashfree
```

5. Open health check:

```text
https://YOUR_PUBLIC_DOMAIN/health
```

## Admin Usage

Telegram admin opens the panel with:

```text
/admin
```

Private web dashboard:

```text
https://YOUR_PUBLIC_DOMAIN/admin?token=ADMIN_WEB_TOKEN
```

## Coupon Upload Format

Inside Telegram admin panel, choose `Add Coupon` and send:

```text
category | title | code | price | stock | expiry ISO or blank | image url or blank | description
```

Example:

```text
Flash Deals | BigBasket Chocolate Coupon | BB100ICE001 | 14 | 1 | 2026-12-31T23:59:59Z | https://example.com/image.jpg | Rs 100 off verified offer
```

## Notes

- `ADMIN_USER_ID` must be your Telegram numeric user ID.
- `REQUIRED_CHANNELS` can contain multiple comma-separated channels.
- The AI assistant never answers unrelated general questions and does not modify source code.
- Wallet credits are stored as signed transactions. Referral reward is `1` credit after verified channel join.
