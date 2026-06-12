export const menu = {
  main: {
    reply_markup: {
      keyboard: [
        ["⚡ Flash Deals", "🔥 Hot Coupons"],
        ["🎁 Rewards", "💰 Wallet"],
        ["📦 Orders", "👥 Refer & Earn"],
        ["🤖 FlashX AI", "📢 Updates"],
      ],
      resize_keyboard: true,
    },
    parse_mode: "HTML",
  },
  admin: {
    reply_markup: {
      keyboard: [
        ["📊 Dashboard", "➕ Add Coupon"],
        ["✏️ Edit Coupon", "🗑 Delete Coupon"],
        ["📣 Broadcast", "💰 Credit Wallet"],
        ["🚫 Ban User", "✅ Unban User"],
        ["📦 Logs", "🧾 Backup"],
        ["🏠 User Menu"],
      ],
      resize_keyboard: true,
    },
    parse_mode: "HTML",
  },
};

export const bootFrames = [
  "⚡ Booting FlashX Engine...",
  "🛡️ Checking Security...",
  "📡 Connecting Services...",
  "💾 Loading Profile...",
  "🎁 Loading Rewards...",
  "✅ Ready",
];

export const paymentFrames = [
  "💳 Initiating Payment...\n\n██░░░░░░░░ 20%",
  "💳 Processing...\n\n█████░░░░░ 50%",
  "🔐 Verifying...\n\n████████░░ 80%",
  "✅ Payment Complete\n\n██████████ 100%",
];

export const rewardFrames = [
  "🎁 Opening Reward...",
  "⚡ Scanning...",
  "💰 Reward Unlocked",
];

export function couponCard(coupon) {
  const expiry = coupon.expires_at ? new Date(coupon.expires_at).toLocaleString("en-IN") : "No expiry";
  const expiringSoon = coupon.expires_at && new Date(coupon.expires_at).getTime() - Date.now() < 72 * 60 * 60 * 1000;

  return [
    "┏━━━━━━━━━━━━━━━━━━━━━━┓",
    `🔥 ${escapeHtml(coupon.title).toUpperCase()}`,
    `💰 Price: ₹${coupon.price}`,
    `📦 Stock: ${coupon.stock} Left`,
    expiringSoon ? "🚨 EXPIRING SOON" : `⏳ Expires: ${escapeHtml(expiry)}`,
    "⚡ Instant Delivery",
    "💎 VERIFIED OFFER",
    "┗━━━━━━━━━━━━━━━━━━━━━━┛",
  ].join("\n");
}

export function streakBar(streak) {
  const filled = Math.max(0, Math.min(30, streak));
  return "🟩".repeat(filled) + "⬜".repeat(30 - filled);
}

export function couponKeyboard(coupon) {
  return {
    reply_markup: {
      inline_keyboard: [
        [{ text: `⚡ Buy ₹${coupon.price}`, callback_data: `buy:${coupon.id}` }],
      ],
    },
    parse_mode: "HTML",
  };
}

export function paymentKeyboard(order, paymentUrl) {
  const rows = [];
  if (paymentUrl) rows.push([{ text: "💳 Pay Now", url: paymentUrl }]);
  rows.push([{ text: "🔁 Verify Payment", callback_data: `verify:${order.order_id}` }]);
  rows.push([{ text: "📄 Invoice", callback_data: `invoice:${order.order_id}` }]);
  rows.push([{ text: "🧾 Refund Request", callback_data: `refund:${order.order_id}` }]);

  return {
    reply_markup: { inline_keyboard: rows },
    parse_mode: "HTML",
  };
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
