import crypto from "crypto";
import { query, withTransaction } from "./db.js";

export async function upsertUser(user) {
  await query(
    `INSERT INTO users (telegram_id, username, first_name, updated_at)
     VALUES ($1, $2, $3, NOW())
     ON CONFLICT (telegram_id)
     DO UPDATE SET username = EXCLUDED.username, first_name = EXCLUDED.first_name, updated_at = NOW()`,
    [user.id, user.username || null, user.first_name || null],
  );
}

export async function markChannelsJoined(userId, joined = true) {
  await query("UPDATE users SET joined_required_channels = $2, updated_at = NOW() WHERE telegram_id = $1", [
    userId,
    joined,
  ]);
}

export async function getUser(userId) {
  const result = await query("SELECT * FROM users WHERE telegram_id = $1", [userId]);
  return result.rows[0] || null;
}

export async function setBan(userId, banned) {
  await query("UPDATE users SET banned = $2, updated_at = NOW() WHERE telegram_id = $1", [userId, banned]);
}

export async function createReferral(referrerId, referredId) {
  if (!referrerId || String(referrerId) === String(referredId)) return false;

  const result = await query(
    `INSERT INTO referrals (referrer_id, referred_id)
     VALUES ($1, $2)
     ON CONFLICT (referred_id) DO NOTHING`,
    [referrerId, referredId],
  );
  return result.rowCount > 0;
}

export async function rewardReferralAfterJoin(referredId) {
  return withTransaction(async (client) => {
    const referral = await client.query(
      "SELECT * FROM referrals WHERE referred_id = $1 AND reward_credited = FALSE",
      [referredId],
    );

    if (!referral.rows[0]) return false;

    await client.query("UPDATE referrals SET reward_credited = TRUE WHERE id = $1", [referral.rows[0].id]);
    await client.query(
      `INSERT INTO wallet_transactions (user_id, amount, type, reason)
       VALUES ($1, 1, 'REFERRAL', 'Successful referral reward')`,
      [referral.rows[0].referrer_id],
    );
    await client.query(
      "INSERT INTO activity_feed (user_id, event, details) VALUES ($1, 'REFERRAL_REWARDED', $2)",
      [referral.rows[0].referrer_id, { referredId, credits: 1 }],
    );
    return true;
  });
}

export async function walletBalance(userId) {
  const result = await query(
    "SELECT COALESCE(SUM(amount), 0)::INT AS balance FROM wallet_transactions WHERE user_id = $1",
    [userId],
  );
  return result.rows[0]?.balance || 0;
}

export async function creditWallet(userId, amount, reason, type = "ADMIN") {
  await query(
    "INSERT INTO wallet_transactions (user_id, amount, type, reason) VALUES ($1, $2, $3, $4)",
    [userId, amount, type, reason],
  );
}

export async function addCategory(name, imageUrl = null) {
  const result = await query(
    `INSERT INTO categories (name, image_url)
     VALUES ($1, $2)
     ON CONFLICT (name) DO UPDATE SET image_url = COALESCE(EXCLUDED.image_url, categories.image_url)
     RETURNING *`,
    [name, imageUrl],
  );
  return result.rows[0];
}

export async function addCoupon(data) {
  const category = await addCategory(data.category || "Flash Deals", data.categoryImageUrl || null);
  const result = await query(
    `INSERT INTO coupons (category_id, title, code, description, image_url, price, stock, expires_at)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
     RETURNING *`,
    [
      category.id,
      data.title,
      data.code,
      data.description || "",
      data.imageUrl || null,
      data.price,
      data.stock || 1,
      data.expiresAt || null,
    ],
  );
  return result.rows[0];
}

export async function updateCoupon(id, data) {
  const result = await query(
    `UPDATE coupons
     SET title = COALESCE($2, title),
         price = COALESCE($3, price),
         stock = COALESCE($4, stock),
         active = COALESCE($5, active)
     WHERE id = $1
     RETURNING *`,
    [id, data.title || null, data.price ?? null, data.stock ?? null, data.active ?? null],
  );
  return result.rows[0] || null;
}

export async function deactivateCoupon(id) {
  const result = await query("UPDATE coupons SET active = FALSE WHERE id = $1 RETURNING *", [id]);
  return result.rows[0] || null;
}

export async function listCoupons({ search = "", mode = "active", limit = 10 } = {}) {
  const clauses = ["c.active = TRUE", "(c.expires_at IS NULL OR c.expires_at > NOW())", "c.stock > 0"];
  const params = [];

  if (search) {
    params.push(`%${search}%`);
    clauses.push(`(c.title ILIKE $${params.length} OR c.description ILIKE $${params.length})`);
  }

  let order = "c.created_at DESC";
  if (mode === "trending" || mode === "hot") order = "c.sold_count DESC, c.created_at DESC";
  if (mode === "expiring") order = "c.expires_at ASC NULLS LAST";

  params.push(limit);
  const result = await query(
    `SELECT c.*, cat.name AS category
     FROM coupons c
     LEFT JOIN categories cat ON cat.id = c.category_id
     WHERE ${clauses.join(" AND ")}
     ORDER BY ${order}
     LIMIT $${params.length}`,
    params,
  );
  return result.rows;
}

export async function getCoupon(id) {
  const result = await query(
    `SELECT c.*, cat.name AS category FROM coupons c
     LEFT JOIN categories cat ON cat.id = c.category_id
     WHERE c.id = $1`,
    [id],
  );
  return result.rows[0] || null;
}

export async function createOrder(userId, couponId) {
  return withTransaction(async (client) => {
    const couponResult = await client.query(
      "SELECT * FROM coupons WHERE id = $1 AND active = TRUE AND stock > 0 FOR UPDATE",
      [couponId],
    );
    const coupon = couponResult.rows[0];
    if (!coupon) throw new Error("Coupon unavailable");

    const balanceResult = await client.query(
      "SELECT COALESCE(SUM(amount), 0)::INT AS balance FROM wallet_transactions WHERE user_id = $1",
      [userId],
    );
    const balance = balanceResult.rows[0]?.balance || 0;
    const walletUsed = Math.min(balance, coupon.price);
    const payableAmount = coupon.price - walletUsed;
    const orderId = `FXBB${crypto.randomUUID().replaceAll("-", "").slice(0, 14).toUpperCase()}`;
    const status = payableAmount === 0 ? "PAID" : "PENDING";

    if (walletUsed > 0) {
      await client.query(
        `INSERT INTO wallet_transactions (user_id, amount, type, reason, order_id)
         VALUES ($1, $2, 'PURCHASE', 'Wallet used for order', $3)`,
        [userId, -walletUsed, orderId],
      );
    }

    const order = await client.query(
      `INSERT INTO orders (order_id, user_id, coupon_id, amount, wallet_used, payable_amount, status, invoice_text)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
       RETURNING *`,
      [
        orderId,
        userId,
        coupon.id,
        coupon.price,
        walletUsed,
        payableAmount,
        status,
        `Invoice ${orderId}: ${coupon.title} for Rs ${coupon.price}`,
      ],
    );

    return { order: order.rows[0], coupon };
  });
}

export async function attachPaymentSession(orderId, sessionId) {
  await query("UPDATE orders SET payment_session_id = $2 WHERE order_id = $1", [orderId, sessionId]);
}

export async function getOrder(orderId) {
  const result = await query(
    `SELECT o.*, c.title, c.code, c.image_url, c.price
     FROM orders o
     LEFT JOIN coupons c ON c.id = o.coupon_id
     WHERE o.order_id = $1`,
    [orderId],
  );
  return result.rows[0] || null;
}

export async function completeOrder(orderId) {
  return withTransaction(async (client) => {
    const orderResult = await client.query(
      `SELECT o.*, c.code, c.id AS coupon_real_id
       FROM orders o
       JOIN coupons c ON c.id = o.coupon_id
       WHERE o.order_id = $1 FOR UPDATE`,
      [orderId],
    );
    const order = orderResult.rows[0];
    if (!order) throw new Error("Order not found");
    if (order.status === "COMPLETED") return order;

    await client.query(
      `UPDATE coupons SET stock = GREATEST(stock - 1, 0), sold_count = sold_count + 1 WHERE id = $1`,
      [order.coupon_real_id],
    );
    const completed = await client.query(
      `UPDATE orders
       SET status = 'COMPLETED', coupon_code = $2, completed_at = NOW()
       WHERE order_id = $1
       RETURNING *`,
      [orderId, order.code],
    );
    await client.query(
      "INSERT INTO payment_logs (order_id, status, payload) VALUES ($1, 'COMPLETED', $2)",
      [orderId, { source: "completeOrder" }],
    );
    await client.query(
      "INSERT INTO activity_feed (user_id, event, details) VALUES ($1, 'COUPON_PURCHASED', $2)",
      [order.user_id, { orderId, couponCode: order.code }],
    );
    return completed.rows[0];
  });
}

export async function logPayment(orderId, status, payload) {
  await query("INSERT INTO payment_logs (order_id, status, payload) VALUES ($1, $2, $3)", [
    orderId,
    status,
    payload,
  ]);
}

export async function userOrders(userId, limit = 10) {
  const result = await query(
    `SELECT o.*, c.title FROM orders o
     LEFT JOIN coupons c ON c.id = o.coupon_id
     WHERE o.user_id = $1
     ORDER BY o.created_at DESC
     LIMIT $2`,
    [userId, limit],
  );
  return result.rows;
}

export async function claimDailyReward(userId) {
  return withTransaction(async (client) => {
    const userResult = await client.query("SELECT * FROM users WHERE telegram_id = $1 FOR UPDATE", [userId]);
    const user = userResult.rows[0];
    const today = new Date().toISOString().slice(0, 10);
    const yesterday = new Date(Date.now() - 86_400_000).toISOString().slice(0, 10);

    if (user?.last_daily_claim && user.last_daily_claim.toISOString().slice(0, 10) === today) {
      return { claimed: false, streak: user.daily_streak, reward: 0, freeCoupon: false };
    }

    const lastClaim = user?.last_daily_claim ? user.last_daily_claim.toISOString().slice(0, 10) : null;
    const streak = lastClaim === yesterday ? (user?.daily_streak || 0) + 1 : 1;
    const milestoneRewards = { 7: 5, 14: 10, 21: 20 };
    const reward = milestoneRewards[streak] || 1;
    const freeCoupon = streak === 30;

    await client.query(
      "UPDATE users SET daily_streak = $2, last_daily_claim = $3 WHERE telegram_id = $1",
      [userId, streak, today],
    );
    await client.query(
      "INSERT INTO wallet_transactions (user_id, amount, type, reason) VALUES ($1, $2, 'DAILY', $3)",
      [userId, reward, `Daily reward streak ${streak}`],
    );
    await client.query(
      "INSERT INTO activity_feed (user_id, event, details) VALUES ($1, 'REWARD_CLAIMED', $2)",
      [userId, { streak, reward, freeCoupon }],
    );
    return { claimed: true, streak, reward, freeCoupon };
  });
}

export async function leaderboard() {
  const result = await query(
    `SELECT referrer_id, COUNT(*)::INT AS referrals
     FROM referrals
     WHERE reward_credited = TRUE
     GROUP BY referrer_id
     ORDER BY referrals DESC
     LIMIT 10`,
  );
  return result.rows;
}

export async function referralHistory(userId, limit = 10) {
  const result = await query(
    `SELECT referred_id, reward_credited, created_at
     FROM referrals
     WHERE referrer_id = $1
     ORDER BY created_at DESC
     LIMIT $2`,
    [userId, limit],
  );
  return result.rows;
}

export async function liveActivity(limit = 8) {
  const result = await query(
    `SELECT event, details, created_at
     FROM activity_feed
     ORDER BY created_at DESC
     LIMIT $1`,
    [limit],
  );
  return result.rows;
}

export async function logActivity(userId, event, details = {}) {
  await query("INSERT INTO activity_feed (user_id, event, details) VALUES ($1, $2, $3)", [
    userId,
    event,
    details,
  ]);
}

export async function createRefundRequest(orderId, userId, reason) {
  const result = await query(
    `INSERT INTO refund_requests (order_id, user_id, reason)
     VALUES ($1, $2, $3)
     RETURNING *`,
    [orderId, userId, reason],
  );
  await logActivity(userId, "REFUND_REQUESTED", { orderId });
  return result.rows[0];
}

export async function saveSupportConversation(userId, message, answer) {
  await query("INSERT INTO support_conversations (user_id, message, answer) VALUES ($1, $2, $3)", [
    userId,
    message,
    answer,
  ]);
}

export async function approvedKnowledge() {
  const result = await query("SELECT question, answer FROM knowledge_base WHERE approved = TRUE ORDER BY id DESC LIMIT 50");
  return result.rows;
}

export async function setMemory(userId, key, value) {
  await query(
    `INSERT INTO ai_memories (user_id, key, value)
     VALUES ($1, $2, $3)
     ON CONFLICT (user_id, key) DO UPDATE SET value = EXCLUDED.value`,
    [userId, key, value],
  );
}

export async function getMemory(userId) {
  const result = await query("SELECT key, value FROM ai_memories WHERE user_id = $1", [userId]);
  return result.rows;
}

export async function stats() {
  const result = await query(`
    SELECT
      (SELECT COUNT(*)::INT FROM users) AS users,
      (SELECT COUNT(*)::INT FROM orders) AS orders,
      (SELECT COUNT(*)::INT FROM orders WHERE status = 'COMPLETED') AS completed_orders,
      (SELECT COALESCE(SUM(amount), 0)::INT FROM orders WHERE status = 'COMPLETED') AS revenue,
      (SELECT COUNT(*)::INT FROM coupons WHERE active = TRUE AND stock > 0) AS active_coupons,
      (SELECT COUNT(*)::INT FROM referrals WHERE reward_credited = TRUE) AS referral_conversions
  `);
  return result.rows[0];
}

export async function audit(adminId, action, details = {}) {
  await query("INSERT INTO audit_logs (admin_id, action, details) VALUES ($1, $2, $3)", [
    adminId,
    action,
    details,
  ]);
}

export async function backupSnapshot() {
  const payload = {};
  for (const table of ["users", "coupons", "orders", "wallet_transactions", "referrals"]) {
    const result = await query(`SELECT * FROM ${table} ORDER BY id DESC LIMIT 500`);
    payload[table] = result.rows;
  }
  await query("INSERT INTO backups (kind, payload) VALUES ('manual', $1)", [payload]);
  return payload;
}
