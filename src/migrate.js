import { pool, query } from "./db.js";
import { logger } from "./logger.js";

export async function migrate() {
  await query(`
    CREATE TABLE IF NOT EXISTS users (
      id BIGSERIAL PRIMARY KEY,
      telegram_id BIGINT UNIQUE NOT NULL,
      username TEXT,
      first_name TEXT,
      joined_required_channels BOOLEAN DEFAULT FALSE,
      banned BOOLEAN DEFAULT FALSE,
      daily_streak INT DEFAULT 0,
      last_daily_claim DATE,
      created_at TIMESTAMPTZ DEFAULT NOW(),
      updated_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS categories (
      id BIGSERIAL PRIMARY KEY,
      name TEXT UNIQUE NOT NULL,
      image_url TEXT,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS coupons (
      id BIGSERIAL PRIMARY KEY,
      category_id BIGINT REFERENCES categories(id),
      title TEXT NOT NULL,
      code TEXT UNIQUE NOT NULL,
      description TEXT DEFAULT '',
      image_url TEXT,
      price INT NOT NULL DEFAULT 0,
      stock INT NOT NULL DEFAULT 1,
      sold_count INT NOT NULL DEFAULT 0,
      expires_at TIMESTAMPTZ,
      active BOOLEAN DEFAULT TRUE,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS orders (
      id BIGSERIAL PRIMARY KEY,
      order_id TEXT UNIQUE NOT NULL,
      user_id BIGINT REFERENCES users(telegram_id),
      coupon_id BIGINT REFERENCES coupons(id),
      amount INT NOT NULL,
      wallet_used INT DEFAULT 0,
      payable_amount INT NOT NULL,
      status TEXT NOT NULL DEFAULT 'PENDING',
      payment_session_id TEXT,
      coupon_code TEXT,
      invoice_text TEXT,
      created_at TIMESTAMPTZ DEFAULT NOW(),
      completed_at TIMESTAMPTZ
    );

    CREATE TABLE IF NOT EXISTS wallet_transactions (
      id BIGSERIAL PRIMARY KEY,
      user_id BIGINT REFERENCES users(telegram_id),
      amount INT NOT NULL,
      type TEXT NOT NULL,
      reason TEXT,
      order_id TEXT,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS referrals (
      id BIGSERIAL PRIMARY KEY,
      referrer_id BIGINT REFERENCES users(telegram_id),
      referred_id BIGINT UNIQUE REFERENCES users(telegram_id),
      reward_credited BOOLEAN DEFAULT FALSE,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS payment_logs (
      id BIGSERIAL PRIMARY KEY,
      order_id TEXT,
      provider TEXT DEFAULT 'cashfree',
      status TEXT,
      payload JSONB,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS refund_requests (
      id BIGSERIAL PRIMARY KEY,
      order_id TEXT,
      user_id BIGINT,
      reason TEXT,
      status TEXT DEFAULT 'OPEN',
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS support_conversations (
      id BIGSERIAL PRIMARY KEY,
      user_id BIGINT REFERENCES users(telegram_id),
      message TEXT,
      answer TEXT,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS ai_memories (
      id BIGSERIAL PRIMARY KEY,
      user_id BIGINT REFERENCES users(telegram_id),
      key TEXT NOT NULL,
      value TEXT NOT NULL,
      created_at TIMESTAMPTZ DEFAULT NOW(),
      UNIQUE(user_id, key)
    );

    CREATE TABLE IF NOT EXISTS knowledge_base (
      id BIGSERIAL PRIMARY KEY,
      question TEXT NOT NULL,
      answer TEXT NOT NULL,
      approved BOOLEAN DEFAULT FALSE,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
      id BIGSERIAL PRIMARY KEY,
      admin_id BIGINT,
      action TEXT NOT NULL,
      details JSONB,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS backups (
      id BIGSERIAL PRIMARY KEY,
      kind TEXT NOT NULL,
      payload JSONB NOT NULL,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS activity_feed (
      id BIGSERIAL PRIMARY KEY,
      user_id BIGINT,
      event TEXT NOT NULL,
      details JSONB,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS rate_limits (
      id BIGSERIAL PRIMARY KEY,
      user_id BIGINT,
      action TEXT,
      count INT DEFAULT 1,
      window_start TIMESTAMPTZ DEFAULT NOW(),
      UNIQUE(user_id, action)
    );

    CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
    CREATE INDEX IF NOT EXISTS idx_coupons_active ON coupons(active, expires_at);
    CREATE INDEX IF NOT EXISTS idx_wallet_user ON wallet_transactions(user_id);
    CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_feed(created_at DESC);
  `);

  logger.info("Database migration complete");
}

if (import.meta.url === `file://${process.argv[1]}`) {
  migrate()
    .then(() => pool.end())
    .catch((error) => {
      logger.error({ error }, "Migration failed");
      process.exit(1);
    });
}
