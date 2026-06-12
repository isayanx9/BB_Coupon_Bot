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
  `);

  await query(`
    ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name TEXT;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS joined_required_channels BOOLEAN DEFAULT FALSE;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS banned BOOLEAN DEFAULT FALSE;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_streak INT DEFAULT 0;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS last_daily_claim DATE;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
    ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

    ALTER TABLE coupons ADD COLUMN IF NOT EXISTS category_id BIGINT;
    ALTER TABLE coupons ADD COLUMN IF NOT EXISTS title TEXT;
    ALTER TABLE coupons ADD COLUMN IF NOT EXISTS code TEXT;
    ALTER TABLE coupons ADD COLUMN IF NOT EXISTS description TEXT DEFAULT '';
    ALTER TABLE coupons ADD COLUMN IF NOT EXISTS image_url TEXT;
    ALTER TABLE coupons ADD COLUMN IF NOT EXISTS price INT DEFAULT 0;
    ALTER TABLE coupons ADD COLUMN IF NOT EXISTS stock INT DEFAULT 1;
    ALTER TABLE coupons ADD COLUMN IF NOT EXISTS sold_count INT DEFAULT 0;
    ALTER TABLE coupons ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
    ALTER TABLE coupons ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE;
    ALTER TABLE coupons ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

    ALTER TABLE coupons ADD COLUMN IF NOT EXISTS coupon_name TEXT;
    ALTER TABLE coupons ADD COLUMN IF NOT EXISTS coupon_code TEXT;
    ALTER TABLE coupons ADD COLUMN IF NOT EXISTS selling_price INT;
    ALTER TABLE coupons ADD COLUMN IF NOT EXISTS sold BOOLEAN DEFAULT FALSE;

    ALTER TABLE orders ADD COLUMN IF NOT EXISTS coupon_id BIGINT;
    ALTER TABLE orders ADD COLUMN IF NOT EXISTS coupon_name TEXT;
    ALTER TABLE orders ADD COLUMN IF NOT EXISTS amount INT DEFAULT 0;
    ALTER TABLE orders ADD COLUMN IF NOT EXISTS wallet_used INT DEFAULT 0;
    ALTER TABLE orders ADD COLUMN IF NOT EXISTS payable_amount INT DEFAULT 0;
    ALTER TABLE orders ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'PENDING';
    ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_session_id TEXT;
    ALTER TABLE orders ADD COLUMN IF NOT EXISTS coupon_code TEXT;
    ALTER TABLE orders ADD COLUMN IF NOT EXISTS invoice_text TEXT;
    ALTER TABLE orders ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
    ALTER TABLE orders ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;

    ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_status TEXT;
    ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_status TEXT;

    INSERT INTO categories (name)
    VALUES ('Flash Deals')
    ON CONFLICT (name) DO NOTHING;

    UPDATE users
    SET joined_required_channels = COALESCE(joined_required_channels, FALSE),
        banned = COALESCE(banned, FALSE),
        daily_streak = COALESCE(daily_streak, 0),
        updated_at = COALESCE(updated_at, NOW());

    UPDATE coupons
    SET title = COALESCE(title, coupon_name, 'BigBasket Coupon'),
        code = COALESCE(code, coupon_code, CONCAT('LEGACY-', id)),
        price = COALESCE(NULLIF(price, 0), selling_price, 0),
        stock = CASE
          WHEN COALESCE(sold, FALSE) THEN 0
          ELSE GREATEST(COALESCE(stock, 1), 1)
        END,
        sold_count = CASE
          WHEN COALESCE(sold, FALSE) THEN GREATEST(COALESCE(sold_count, 0), 1)
          ELSE COALESCE(sold_count, 0)
        END,
        category_id = COALESCE(category_id, (SELECT id FROM categories WHERE name = 'Flash Deals' LIMIT 1)),
        active = COALESCE(active, TRUE);

    UPDATE orders
    SET status = COALESCE(status, payment_status, 'PENDING'),
        payable_amount = COALESCE(NULLIF(payable_amount, 0), amount, 0),
        wallet_used = COALESCE(wallet_used, 0),
        invoice_text = COALESCE(invoice_text, CONCAT('Invoice ', order_id, ': ', COALESCE(coupon_name, 'Coupon'), ' for Rs ', COALESCE(amount, 0)));

    UPDATE orders o
    SET coupon_id = c.id,
        coupon_code = COALESCE(o.coupon_code, c.code)
    FROM coupons c
    WHERE o.coupon_id IS NULL
      AND (
        o.coupon_name = c.title
        OR o.coupon_name = c.coupon_name
        OR o.coupon_code = c.code
        OR o.coupon_code = c.coupon_code
      );
  `);

  await query(`
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
