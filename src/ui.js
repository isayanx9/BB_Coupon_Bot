export const menu = {
  main: {
    reply_markup: {
      keyboard: [
        ["⚡ Flash Deals", "🔥 Hot Coupons"],
        ["🎁 Rewards", "💰 Wallet"],
        ["📦 My Orders", "👥 Refer & Earn"],
        ["🤖 Support AI", "📢 Updates"],
      ],
      resize_keyboard: true,
    },
    parse_mode: "HTML",
  },
  admin: {
    reply_markup: {
      keyboard: [
        ["📊 Dashboard", "➕ Add Coupon"],
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

export function couponCard(coupon) {
  const expiry = coupon.expires_at ? new Date(coupon.expires_at).toLocaleString("en-IN") : "No expiry";
  return [
    "⚡ <b>FLASH DEAL</b>",
    "🔥 <b>LIMITED STOCK</b>",
    "💎 <b>VERIFIED OFFER</b>",
    "",
    `<b>${escapeHtml(coupon.title)}</b>`,
    coupon.description ? `<i>${escapeHtml(coupon.description)}</i>` : "",
    `Price: <b>₹${coupon.price}</b>`,
    `Stock: <b>${coupon.stock}</b>`,
    `Expiry: <b>${escapeHtml(expiry)}</b>`,
  ].filter(Boolean).join("\n");
}

export function couponKeyboard(coupon) {
  return {
    reply_markup: {
      inline_keyboard: [
        [{ text: `🛒 Buy ₹${coupon.price}`, callback_data: `buy:${coupon.id}` }],
      ],
    },
    parse_mode: "HTML",
  };
}

export function paymentKeyboard(order, paymentUrl) {
  const rows = [];

  if (paymentUrl) rows.push([{ text: "💳 Pay with Cashfree", url: paymentUrl }]);
  rows.push([{ text: "🔁 Verify Payment", callback_data: `verify:${order.order_id}` }]);
  rows.push([{ text: "📄 Invoice", callback_data: `invoice:${order.order_id}` }]);

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
