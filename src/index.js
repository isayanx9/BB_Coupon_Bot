import express from "express";
import helmet from "helmet";
import rateLimit from "express-rate-limit";
import { assertConfig, config } from "./config.js";
import { pool } from "./db.js";
import { migrate } from "./migrate.js";
import { logger } from "./logger.js";
import { createBot } from "./bot.js";
import { completeOrder, getOrder, logPayment, stats } from "./repositories.js";
import { validateCashfreeWebhook } from "./services/cashfree.js";

assertConfig();
await migrate();

const bot = createBot();
const app = express();

app.use(helmet({ contentSecurityPolicy: false }));
app.use(express.json({ limit: "1mb" }));
app.use(rateLimit({ windowMs: 60_000, max: 120 }));

app.get("/", (_req, res) => {
  res.json({ ok: true, service: "FlashXBBbot", theme: "black-yellow-cyber", mode: process.env.NODE_ENV || "development" });
});

app.get("/health", async (_req, res) => {
  await pool.query("SELECT 1");
  res.json({ ok: true, database: true });
});

app.get("/admin", async (req, res) => {
  if (!config.adminWebToken || req.query.token !== config.adminWebToken) {
    res.status(403).send("Admin token required");
    return;
  }

  const data = await stats();
  res.type("html").send(`
    <!doctype html>
    <html>
    <head>
      <title>FlashXBB Admin</title>
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <style>
        body { margin: 0; font-family: ui-sans-serif, Segoe UI, Arial; background: #09090b; color: #facc15; }
        header { background: #18181b; color: #facc15; padding: 28px; border-bottom: 1px solid #3f3f46; }
        main { padding: 24px; display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; }
        section { background: #18181b; border: 1px solid #3f3f46; border-left: 4px solid #facc15; border-radius: 8px; padding: 18px; color: #f4f4f5; }
        b { color: #facc15; font-size: 28px; display: block; margin-top: 8px; }
      </style>
    </head>
    <body>
      <header><h1>⚡ FlashXBB Admin</h1><p>Black / Dark Gray / Electric Yellow control room</p></header>
      <main>
        <section>Total users <b>${data.users}</b></section>
        <section>Total orders <b>${data.orders}</b></section>
        <section>Completed <b>${data.completed_orders}</b></section>
        <section>Revenue <b>₹${data.revenue}</b></section>
        <section>Active coupons <b>${data.active_coupons}</b></section>
        <section>Referral conversions <b>${data.referral_conversions}</b></section>
      </main>
    </body>
    </html>
  `);
});

app.get("/pay/:orderId", async (req, res) => {
  const order = await getOrder(req.params.orderId);
  if (!order) {
    res.status(404).send("Order not found");
    return;
  }

  res.type("html").send(`
    <!doctype html>
    <html>
    <head>
      <title>FlashX Payment</title>
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <script src="https://sdk.cashfree.com/js/v3/cashfree.js"></script>
      <style>
        body { display: grid; place-items: center; min-height: 100vh; margin: 0; font-family: Arial; background: #09090b; color: #facc15; }
        main { max-width: 520px; background: #18181b; border: 1px solid #3f3f46; border-left: 5px solid #facc15; border-radius: 8px; padding: 28px; box-shadow: 0 20px 60px rgba(250, 204, 21, .12); }
        code { color: #fef08a; font-weight: 700; }
      </style>
    </head>
    <body>
      <main>
        <h1>⚡ FlashX Secure Checkout</h1>
        <p>Order <code>${order.order_id}</code></p>
        <p>Redirecting to Cashfree...</p>
      </main>
      <script>
        const cashfree = Cashfree({ mode: "${config.cashfreeEnv === "sandbox" ? "sandbox" : "production"}" });
        cashfree.checkout({ paymentSessionId: "${order.payment_session_id}", redirectTarget: "_self" });
      </script>
    </body>
    </html>
  `);
});

app.post("/webhook/cashfree", async (req, res) => {
  if (!validateCashfreeWebhook(req)) {
    res.status(401).json({ ok: false });
    return;
  }

  const orderId = req.body?.data?.order?.order_id || req.body?.order_id;
  const status = req.body?.data?.payment?.payment_status || req.body?.order_status;
  await logPayment(orderId, status || "WEBHOOK", req.body);

  if (orderId && ["SUCCESS", "PAID", "ACTIVE"].includes(String(status).toUpperCase())) {
    const order = await completeOrder(orderId);
    await bot.sendMessage(
      order.user_id,
      `✅ <b>Payment Complete</b>\n\n██████████ 100%\n\nOrder: <code>${order.order_id}</code>\nCoupon: <code>${order.coupon_code}</code>`,
      { parse_mode: "HTML" },
    );
  }

  res.json({ ok: true });
});

app.listen(config.port, () => {
  logger.info({ port: config.port }, "FlashXBBbot server started");
});
