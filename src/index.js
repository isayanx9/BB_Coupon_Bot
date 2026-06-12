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
const app = express();
let bot = null;
let bootstrapReady = false;
let bootstrapRunning = false;

app.use(helmet({ contentSecurityPolicy: false }));
app.use("/webhook/cashfree", express.raw({ type: "*/*", limit: "1mb" }));
app.use(express.json({ limit: "1mb" }));
app.use(rateLimit({ windowMs: 60_000, max: 120 }));

function asyncRoute(handler) {
  return (req, res, next) => Promise.resolve(handler(req, res, next)).catch(next);
}

async function bootstrap() {
  if (bootstrapRunning || bootstrapReady) return;
  bootstrapRunning = true;

  try {
    await migrate();
    bot = createBot();
    bootstrapReady = true;
    logger.info("FlashXBBbot migration and Telegram polling started");
  } catch (error) {
    logger.error({ error }, "FlashXBBbot bootstrap failed; retrying shortly");
    setTimeout(bootstrap, 15000);
  } finally {
    bootstrapRunning = false;
  }
}

app.get("/", (_req, res) => {
  res.json({ ok: true, service: "FlashXBBbot", theme: "black-yellow-cyber", mode: process.env.NODE_ENV || "development" });
});

app.get("/health", (_req, res) => {
  res.json({ ok: true, app: true, bot: Boolean(bot), ready: bootstrapReady });
});

app.get("/ready", asyncRoute(async (_req, res) => {
  try {
    await pool.query("SELECT 1");
    res.json({ ok: true, app: true, database: true, bot: Boolean(bot), ready: bootstrapReady });
  } catch (error) {
    logger.error({ error }, "Health database check failed");
    res.status(503).json({ ok: false, app: true, database: false, bot: Boolean(bot), ready: bootstrapReady });
  }
}));

app.get("/admin", asyncRoute(async (req, res) => {
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
}));

app.get("/pay/:orderId", asyncRoute(async (req, res) => {
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
}));

function webhookBody(req) {
  if (!Buffer.isBuffer(req.body)) return req.body || {};
  if (!req.body.length) return {};

  try {
    return JSON.parse(req.body.toString("utf8"));
  } catch (_error) {
    return {};
  }
}

app.all("/webhook/cashfree", asyncRoute(async (req, res) => {
  if (["GET", "HEAD", "OPTIONS"].includes(req.method)) {
    res.set("Allow", "GET,HEAD,OPTIONS,POST");
    res.json({ ok: true, provider: "cashfree", service: "FlashXBBbot webhook active" });
    return;
  }

  if (req.method !== "POST") {
    res.status(405).json({ ok: false, error: "Method not allowed" });
    return;
  }

  const body = webhookBody(req);
  const orderId = body?.data?.order?.order_id || body?.order_id;
  const status = body?.data?.payment?.payment_status || body?.order_status;

  if (!orderId) {
    res.json({ ok: true, provider: "cashfree", received: true });
    return;
  }

  if (!validateCashfreeWebhook(req)) {
    res.status(401).json({ ok: false });
    return;
  }

  await logPayment(orderId, status || "WEBHOOK", body);

  if (["SUCCESS", "PAID", "ACTIVE"].includes(String(status).toUpperCase())) {
    const order = await completeOrder(orderId);
    await bot?.sendMessage(
      order.user_id,
      `✅ <b>Payment Complete</b>\n\n██████████ 100%\n\nOrder: <code>${order.order_id}</code>\nCoupon: <code>${order.coupon_code}</code>`,
      { parse_mode: "HTML" },
    );
  }

  res.json({ ok: true, provider: "cashfree", service: "FlashXBBbot webhook active" });
}));

app.use((error, _req, res, _next) => {
  logger.error({ error }, "HTTP request failed");
  res.status(500).json({ ok: false, error: "Internal server error" });
});

app.listen(config.port, "0.0.0.0", () => {
  logger.info({ host: "0.0.0.0", port: config.port }, "FlashXBBbot server started");
  bootstrap();
});
