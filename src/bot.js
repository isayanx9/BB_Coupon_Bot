import { config } from "./config.js";
import { logger } from "./logger.js";
import { answerSupport } from "./services/ai.js";
import { createCashfreeOrder, getCashfreeOrder } from "./services/cashfree.js";
import {
  addCoupon,
  audit,
  backupSnapshot,
  claimDailyReward,
  completeOrder,
  createOrder,
  createReferral,
  creditWallet,
  getOrder,
  getUser,
  leaderboard,
  listCoupons,
  logPayment,
  markChannelsJoined,
  rewardReferralAfterJoin,
  setBan,
  stats,
  upsertUser,
  userOrders,
  walletBalance,
} from "./repositories.js";
import { couponCard, couponKeyboard, escapeHtml, menu, paymentKeyboard } from "./ui.js";
import { TelegramClient } from "./telegram.js";

const sessions = new Map();
const inMemoryRateLimit = new Map();

export function createBot() {
  const bot = new TelegramClient(config.botToken);
  bot.startPolling({
    onMessage: (message) => handleMessage(bot, message),
    onCallbackQuery: (callback) => handleCallback(bot, callback),
  });
  return bot;
}

async function handleMessage(bot, message) {
  try {
    if (!message.from || !message.text) return;
    if (rateLimited(message.from.id)) return;

    await upsertUser(message.from);

    const user = await getUser(message.from.id);
    if (user?.banned) {
      await bot.sendMessage(message.chat.id, "🚫 Your account is restricted.", { parse_mode: "HTML" });
      return;
    }

    const session = sessions.get(message.from.id);
    if (session) {
      await handleSession(bot, message, session);
      return;
    }

    const text = message.text.trim();

    if (text.startsWith("/start")) return start(bot, message);
    if (text === "/admin" || text === "🛠 Admin") return admin(bot, message);
    if (text === "⚡ Flash Deals") return sendCoupons(bot, message, "active");
    if (text === "🔥 Hot Coupons") return sendCoupons(bot, message, "hot");
    if (text === "📦 My Orders") return myOrders(bot, message);
    if (text === "💰 Wallet") return wallet(bot, message);
    if (text === "👥 Refer & Earn") return refer(bot, message);
    if (text === "🎁 Rewards") return rewards(bot, message);
    if (text === "🤖 Support AI") return startAi(bot, message);
    if (text === "📢 Updates") return bot.sendMessage(message.chat.id, "📢 Updates will arrive here when new stock drops.", menu.main);
    if (text === "📊 Dashboard") return dashboard(bot, message);
    if (text === "➕ Add Coupon") return beginSession(bot, message, "addCoupon");
    if (text === "📣 Broadcast") return beginSession(bot, message, "broadcast");
    if (text === "💰 Credit Wallet") return beginSession(bot, message, "creditWallet");
    if (text === "🚫 Ban User") return beginSession(bot, message, "banUser");
    if (text === "✅ Unban User") return beginSession(bot, message, "unbanUser");
    if (text === "📦 Logs") return dashboard(bot, message);
    if (text === "🧾 Backup") return backup(bot, message);
    if (text === "🏠 User Menu") return bot.sendMessage(message.chat.id, "🏠 User menu", menu.main);

    return search(bot, message, text);
  } catch (error) {
    logger.error({ error }, "Message handler failed");
    await bot.sendMessage(message.chat.id, "Something went wrong. Please try again in a moment.");
  }
}

async function start(bot, message) {
  const parts = message.text.split(" ");
  if (parts[1] && /^\d+$/.test(parts[1])) await createReferral(Number(parts[1]), message.from.id);

  await verifyRequiredChannels(bot, message.from.id);
  await bot.sendMessage(
    message.chat.id,
    "⚡ <b>FlashXBBbot</b>\n\n💎 Verified BigBasket coupon drops, instant delivery, wallet credits, referrals and AI support.",
    menu.main,
  );
}

async function verifyRequiredChannels(bot, userId) {
  if (!config.requiredChannels.length) {
    await markChannelsJoined(userId, true);
    return true;
  }

  for (const channel of config.requiredChannels) {
    const member = await bot.getChatMember(channel, userId);
    if (!["member", "administrator", "creator"].includes(member.status)) {
      await markChannelsJoined(userId, false);
      return false;
    }
  }

  await markChannelsJoined(userId, true);
  await rewardReferralAfterJoin(userId);
  return true;
}

async function sendCoupons(bot, message, mode) {
  const joined = await verifyRequiredChannels(bot, message.from.id);
  if (!joined) {
    await bot.sendMessage(message.chat.id, "Join the required channels first, then run /start again.");
    return;
  }

  const coupons = await listCoupons({ mode, limit: 8 });
  if (!coupons.length) {
    await bot.sendMessage(message.chat.id, "No active coupons right now. New arrivals will appear here.");
    return;
  }

  for (const coupon of coupons) {
    if (coupon.image_url) {
      await bot.sendPhoto(message.chat.id, coupon.image_url, {
        caption: couponCard(coupon),
        ...couponKeyboard(coupon),
      });
    } else {
      await bot.sendMessage(message.chat.id, couponCard(coupon), couponKeyboard(coupon));
    }
  }
}

async function search(bot, message, text) {
  const coupons = await listCoupons({ search: text, limit: 5 });
  if (!coupons.length) {
    await bot.sendMessage(message.chat.id, "I searched active coupons but did not find a match.");
    return;
  }
  for (const coupon of coupons) await bot.sendMessage(message.chat.id, couponCard(coupon), couponKeyboard(coupon));
}

async function handleCallback(bot, callback) {
  const data = callback.data || "";
  const chatId = callback.message.chat.id;

  try {
    if (data.startsWith("buy:")) {
      const couponId = Number(data.split(":")[1]);
      const { order } = await createOrder(callback.from.id, couponId);

      if (order.payable_amount === 0) {
        const completed = await completeOrder(order.order_id);
        await bot.sendMessage(chatId, deliveryText(completed), { parse_mode: "HTML" });
      } else {
        const cashfree = await createCashfreeOrder(order, callback.from.id);
        await import("./repositories.js").then(({ attachPaymentSession }) => attachPaymentSession(order.order_id, cashfree.payment_session_id));
        await bot.sendMessage(
          chatId,
          `📄 <b>Invoice</b>\n\n<code>${order.invoice_text}</code>\nPayable now: <b>₹${order.payable_amount}</b>`,
          paymentKeyboard(order, `${config.publicBaseUrl}/pay/${order.order_id}`),
        );
      }
    }

    if (data.startsWith("verify:")) {
      const orderId = data.split(":")[1];
      const cashfree = await getCashfreeOrder(orderId);
      await logPayment(orderId, cashfree.order_status || "CHECKED", cashfree);

      if (["PAID", "ACTIVE"].includes(cashfree.order_status)) {
        const completed = await completeOrder(orderId);
        await bot.sendMessage(chatId, deliveryText(completed), { parse_mode: "HTML" });
      } else {
        await bot.sendMessage(chatId, `Payment status: ${cashfree.order_status || "not confirmed"}`);
      }
    }

    if (data.startsWith("invoice:")) {
      const order = await getOrder(data.split(":")[1]);
      if (order) await bot.sendMessage(chatId, `<code>${escapeHtml(order.invoice_text)}</code>`, { parse_mode: "HTML" });
    }
  } catch (error) {
    logger.error({ error }, "Callback failed");
    await bot.sendMessage(chatId, "That action could not be completed. Please try again or contact support.");
  } finally {
    await bot.answerCallbackQuery(callback.id).catch(() => {});
  }
}

function deliveryText(order) {
  return [
    "🎉 <b>ORDER COMPLETED</b>",
    "",
    `Order: <code>${order.order_id}</code>`,
    `Coupon code: <code>${escapeHtml(order.coupon_code)}</code>`,
    "",
    "💎 VERIFIED OFFER delivered instantly.",
  ].join("\n");
}

async function myOrders(bot, message) {
  const orders = await userOrders(message.from.id);
  if (!orders.length) return bot.sendMessage(message.chat.id, "No orders yet.");

  const text = orders
    .map((order) => `📦 <code>${order.order_id}</code> - ${escapeHtml(order.title || "Coupon")} - <b>${order.status}</b>`)
    .join("\n");
  await bot.sendMessage(message.chat.id, text, { parse_mode: "HTML" });
}

async function wallet(bot, message) {
  const balance = await walletBalance(message.from.id);
  await bot.sendMessage(message.chat.id, `💰 Wallet balance: <b>₹${balance}</b>`, { parse_mode: "HTML" });
}

async function refer(bot, message) {
  const rows = await leaderboard();
  const link = `https://t.me/${(await bot.getMe()).username}?start=${message.from.id}`;
  const top = rows.map((row, index) => `${index + 1}. <code>${row.referrer_id}</code> - ${row.referrals}`).join("\n") || "No referrals yet.";
  await bot.sendMessage(message.chat.id, `👥 <b>Refer & Earn</b>\n\nEarn 1 credit after each verified referral.\n\n<code>${link}</code>\n\n<b>Leaderboard</b>\n${top}`, { parse_mode: "HTML" });
}

async function rewards(bot, message) {
  const result = await claimDailyReward(message.from.id);
  if (!result.claimed) {
    await bot.sendMessage(message.chat.id, `🎁 Daily reward already claimed. Current streak: ${result.streak}`);
    return;
  }
  await bot.sendMessage(message.chat.id, `🎁 Claimed ₹${result.reward}. Streak: ${result.streak}`);
}

async function startAi(bot, message) {
  sessions.set(message.from.id, { type: "ai" });
  await bot.sendMessage(message.chat.id, "🤖 Ask me about coupons, payments, referrals, wallet, orders or bot usage.");
}

async function admin(bot, message) {
  if (String(message.from.id) !== config.adminUserId) return bot.sendMessage(message.chat.id, "Admin only.");
  await bot.sendMessage(message.chat.id, "🛠 Admin dashboard opened.", menu.admin);
}

async function dashboard(bot, message) {
  if (String(message.from.id) !== config.adminUserId) return;
  const data = await stats();
  await bot.sendMessage(message.chat.id, `📊 <b>Admin Dashboard</b>\n\nUsers: ${data.users}\nOrders: ${data.orders}\nCompleted: ${data.completed_orders}\nRevenue: ₹${data.revenue}\nActive coupons: ${data.active_coupons}\nReferral conversions: ${data.referral_conversions}`, { parse_mode: "HTML" });
}

async function beginSession(bot, message, type) {
  if (String(message.from.id) !== config.adminUserId) return bot.sendMessage(message.chat.id, "Admin only.");
  sessions.set(message.from.id, { type, step: 0, data: {} });
  const prompts = {
    addCoupon: "Send coupon as: category | title | code | price | stock | expiry ISO or blank | image url or blank | description",
    broadcast: "Send broadcast message.",
    creditWallet: "Send: user_id | amount | reason",
    banUser: "Send user_id to ban.",
    unbanUser: "Send user_id to unban.",
  };
  await bot.sendMessage(message.chat.id, prompts[type] || "Send details.");
}

async function handleSession(bot, message, session) {
  const text = message.text.trim();
  sessions.delete(message.from.id);

  if (session.type === "ai") {
    const answer = await answerSupport(message.from.id, text);
    return bot.sendMessage(message.chat.id, answer, { parse_mode: "HTML" });
  }

  if (String(message.from.id) !== config.adminUserId) return;

  if (session.type === "addCoupon") {
    const [category, title, code, price, stock, expiresAt, imageUrl, ...description] = text.split("|").map((part) => part.trim());
    const coupon = await addCoupon({
      category,
      title,
      code,
      price: Number(price),
      stock: Number(stock || 1),
      expiresAt: expiresAt || null,
      imageUrl: imageUrl || null,
      description: description.join(" | "),
    });
    await audit(message.from.id, "ADD_COUPON", { couponId: coupon.id });
    return bot.sendMessage(message.chat.id, `Coupon added: ${coupon.title}`);
  }

  if (session.type === "broadcast") {
    const users = await import("./db.js").then(({ query }) => query("SELECT telegram_id FROM users WHERE banned = FALSE"));
    let sent = 0;
    for (const user of users.rows) {
      try {
        await bot.sendMessage(user.telegram_id, `📢 <b>Update</b>\n\n${escapeHtml(text)}`, { parse_mode: "HTML" });
        sent += 1;
      } catch {
        // ignore blocked users
      }
    }
    await audit(message.from.id, "BROADCAST", { sent });
    return bot.sendMessage(message.chat.id, `Broadcast sent to ${sent} users.`);
  }

  if (session.type === "creditWallet") {
    const [userId, amount, reason] = text.split("|").map((part) => part.trim());
    await creditWallet(Number(userId), Number(amount), reason || "Admin adjustment");
    await audit(message.from.id, "CREDIT_WALLET", { userId, amount });
    return bot.sendMessage(message.chat.id, "Wallet credited.");
  }

  if (session.type === "banUser" || session.type === "unbanUser") {
    await setBan(Number(text), session.type === "banUser");
    await audit(message.from.id, session.type.toUpperCase(), { userId: text });
    return bot.sendMessage(message.chat.id, "User status updated.");
  }
}

async function backup(bot, message) {
  if (String(message.from.id) !== config.adminUserId) return;
  await backupSnapshot();
  await audit(message.from.id, "BACKUP", {});
  await bot.sendMessage(message.chat.id, "Backup snapshot saved in PostgreSQL.");
}

function rateLimited(userId) {
  const now = Date.now();
  const state = inMemoryRateLimit.get(userId) || { count: 0, started: now };
  if (now - state.started > 10_000) {
    inMemoryRateLimit.set(userId, { count: 1, started: now });
    return false;
  }
  state.count += 1;
  inMemoryRateLimit.set(userId, state);
  return state.count > 12;
}
