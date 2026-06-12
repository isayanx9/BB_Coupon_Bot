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
  createRefundRequest,
  creditWallet,
  deactivateCoupon,
  getOrder,
  getUser,
  leaderboard,
  listCoupons,
  liveActivity,
  logPayment,
  markChannelsJoined,
  referralHistory,
  rewardReferralAfterJoin,
  setBan,
  stats,
  updateCoupon,
  upsertUser,
  userOrders,
  walletBalance,
} from "./repositories.js";
import {
  bootFrames,
  couponCard,
  couponKeyboard,
  escapeHtml,
  menu,
  paymentFrames,
  paymentKeyboard,
  rewardFrames,
  streakBar,
} from "./ui.js";
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
    if (text === "/profile") return profile(bot, message);
    if (text === "⚡ Flash Deals") return sendCoupons(bot, message, "active");
    if (text === "🔥 Hot Coupons") return sendCoupons(bot, message, "hot");
    if (text === "📦 Orders") return myOrders(bot, message);
    if (text === "💰 Wallet") return wallet(bot, message);
    if (text === "👥 Refer & Earn") return refer(bot, message);
    if (text === "🎁 Rewards") return rewards(bot, message);
    if (text === "🤖 FlashX AI") return startAi(bot, message);
    if (text === "📢 Updates") return updates(bot, message);
    if (text === "📊 Dashboard") return dashboard(bot, message);
    if (text === "➕ Add Coupon") return beginSession(bot, message, "addCoupon");
    if (text === "✏️ Edit Coupon") return beginSession(bot, message, "editCoupon");
    if (text === "🗑 Delete Coupon") return beginSession(bot, message, "deleteCoupon");
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

  const joined = await verifyRequiredChannels(bot, message.from.id);
  await bootAnimation(bot, message.chat.id);

  if (!joined) {
    await bot.sendMessage(
      message.chat.id,
      "⚡ <b>FlashXBBbot</b>\n\nJoin the required channels first, then press /start again.",
      { parse_mode: "HTML" },
    );
    return;
  }

  await bot.sendMessage(
    message.chat.id,
    "⚡ <b>FlashXBBbot</b>\n\n<b>BLACK / DARK GRAY / ELECTRIC YELLOW</b>\n\n💎 Verified BigBasket coupon drops, instant delivery, wallet credits, referrals and FlashX AI support.",
    menu.main,
  );
}

async function bootAnimation(bot, chatId) {
  const message = await bot.sendMessage(chatId, bootFrames[0]);
  for (const frame of bootFrames.slice(1)) {
    await delay(350);
    await bot.editMessageText(chatId, message.message_id, frame).catch(() => {});
  }
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
        await paymentAnimation(bot, chatId);
        const cashfree = await createCashfreeOrder(order, callback.from.id);
        await import("./repositories.js").then(({ attachPaymentSession }) => attachPaymentSession(order.order_id, cashfree.payment_session_id));
        const paymentUrl =
          cashfree.payment_link ||
          cashfree.payments?.url ||
          cashfree.payment_url ||
          `${config.publicBaseUrl}/pay/${order.order_id}`;
        await bot.sendMessage(
          chatId,
          `📄 <b>Invoice</b>\n\n<code>${order.invoice_text}</code>\nPayable now: <b>₹${order.payable_amount}</b>`,
          paymentKeyboard(order, paymentUrl),
        );
      }
    }

    if (data.startsWith("verify:")) {
      const orderId = data.split(":")[1];
      const cashfree = await getCashfreeOrder(orderId);
      const orderStatus = String(cashfree.order_status || cashfree.payment_status || "").toUpperCase();
      await logPayment(orderId, orderStatus || "CHECKED", cashfree);

      if (["PAID", "SUCCESS", "ACTIVE"].includes(orderStatus)) {
        const completed = await completeOrder(orderId);
        await bot.sendMessage(chatId, deliveryText(completed), { parse_mode: "HTML" });
      } else {
        await bot.sendMessage(chatId, `Payment status: ${orderStatus || "not confirmed"}`);
      }
    }

    if (data.startsWith("invoice:")) {
      const order = await getOrder(data.split(":")[1]);
      if (order) await bot.sendMessage(chatId, `<code>${escapeHtml(order.invoice_text)}</code>`, { parse_mode: "HTML" });
    }

    if (data.startsWith("refund:")) {
      const orderId = data.split(":")[1];
      await createRefundRequest(orderId, callback.from.id, "User requested refund from invoice controls");
      await bot.sendMessage(chatId, `🧾 Refund request opened for <code>${orderId}</code>.`, { parse_mode: "HTML" });
    }
  } catch (error) {
    logger.error({ error }, "Callback failed");
    await bot.sendMessage(chatId, "That action could not be completed. Please try again or contact support.");
  } finally {
    await bot.answerCallbackQuery(callback.id).catch(() => {});
  }
}

async function paymentAnimation(bot, chatId) {
  const message = await bot.sendMessage(chatId, paymentFrames[0]);
  for (const frame of paymentFrames.slice(1)) {
    await delay(400);
    await bot.editMessageText(chatId, message.message_id, frame).catch(() => {});
  }
}

function deliveryText(order) {
  return [
    "✅ <b>Payment Complete</b>",
    "",
    "██████████ 100%",
    "",
    `Order: <code>${order.order_id}</code>`,
    `Coupon code: <code>${escapeHtml(order.coupon_code)}</code>`,
    "",
    "⚡ Instant Delivery",
    "💎 VERIFIED OFFER",
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
  const history = await referralHistory(message.from.id);
  const link = `https://t.me/${(await bot.getMe()).username}?start=${message.from.id}`;
  const top = rows.map((row, index) => `${index + 1}. <code>${row.referrer_id}</code> - ${row.referrals}`).join("\n") || "No referrals yet.";
  const recent = history.map((row) => `<code>${row.referred_id}</code> - ${row.reward_credited ? "Rewarded" : "Pending"}`).join("\n") || "No referral history yet.";

  await bot.sendMessage(
    message.chat.id,
    `👥 <b>Refer & Earn</b>\n\n1 successful referral = <b>1 credit</b> = <b>₹1</b>\nReferral counts after required channel join.\n\n<code>${link}</code>\n\n<b>Leaderboard</b>\n${top}\n\n<b>Your History</b>\n${recent}`,
    { parse_mode: "HTML" },
  );
}

async function rewards(bot, message) {
  const result = await claimDailyReward(message.from.id);
  if (!result.claimed) {
    await bot.sendMessage(message.chat.id, `🎁 Daily reward already claimed.\n\n⚡ DAILY STREAK\nDay ${result.streak} / 30\n\n${streakBar(result.streak)}`);
    return;
  }

  await rewardAnimation(bot, message.chat.id);
  await bot.sendMessage(
    message.chat.id,
    `⚡ <b>DAILY STREAK</b>\nDay ${result.streak} / 30\n\n${streakBar(result.streak)}\n\n💰 Reward Unlocked\n+₹${result.reward} Credits${result.freeCoupon ? "\n🎟 Day 30 Free Coupon Reward unlocked" : ""}`,
    { parse_mode: "HTML" },
  );
}

async function rewardAnimation(bot, chatId) {
  const message = await bot.sendMessage(chatId, rewardFrames[0]);
  for (const frame of rewardFrames.slice(1)) {
    await delay(400);
    await bot.editMessageText(chatId, message.message_id, frame).catch(() => {});
  }
}

async function startAi(bot, message) {
  sessions.set(message.from.id, { type: "ai" });
  await bot.sendMessage(message.chat.id, "🤖 <b>FlashX AI</b>\n\nAsk me about coupons, payments, referrals, rewards, wallet, orders or bot usage.", { parse_mode: "HTML" });
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

async function profile(bot, message) {
  const user = await getUser(message.from.id);
  const balance = await walletBalance(message.from.id);
  await bot.sendMessage(
    message.chat.id,
    `⚡ <b>Profile</b>\n\nID: <code>${message.from.id}</code>\nUsername: <b>${escapeHtml(message.from.username || "none")}</b>\nWallet: <b>₹${balance}</b>\nStreak: <b>${user?.daily_streak || 0}</b>`,
    { parse_mode: "HTML" },
  );
}

async function beginSession(bot, message, type) {
  if (String(message.from.id) !== config.adminUserId) return bot.sendMessage(message.chat.id, "Admin only.");
  sessions.set(message.from.id, { type, step: 0, data: {} });
  const prompts = {
    addCoupon: "Send coupon as: category | title | code | price | stock | expiry ISO or blank | image url or blank | description",
    editCoupon: "Send: coupon_id | title | price | stock | active true/false",
    deleteCoupon: "Send coupon_id to deactivate.",
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

  if (session.type === "editCoupon") {
    const [id, title, price, stock, active] = text.split("|").map((part) => part.trim());
    const coupon = await updateCoupon(Number(id), {
      title,
      price: price ? Number(price) : null,
      stock: stock ? Number(stock) : null,
      active: active ? active.toLowerCase() === "true" : null,
    });
    await audit(message.from.id, "EDIT_COUPON", { id });
    return bot.sendMessage(message.chat.id, coupon ? `Coupon updated: ${coupon.title}` : "Coupon not found.");
  }

  if (session.type === "deleteCoupon") {
    const coupon = await deactivateCoupon(Number(text));
    await audit(message.from.id, "DELETE_COUPON", { id: text });
    return bot.sendMessage(message.chat.id, coupon ? "Coupon deactivated." : "Coupon not found.");
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

async function updates(bot, message) {
  const rows = await liveActivity();
  const labels = {
    COUPON_PURCHASED: "🔥 Coupon Purchased",
    PAYMENT_VERIFIED: "⚡ Payment Verified",
    REWARD_CLAIMED: "🎁 Reward Claimed",
    REFERRAL_REWARDED: "💰 Wallet Credited",
    REFUND_REQUESTED: "🧾 Refund Requested",
  };
  const feed = rows.map((row) => labels[row.event] || `⚡ ${row.event}`).join("\n") || "No live activity yet.";
  await bot.sendMessage(message.chat.id, `📢 <b>Live Activity Feed</b>\n\n${feed}`, { parse_mode: "HTML" });
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

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
