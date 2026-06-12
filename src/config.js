import dotenv from "dotenv";

dotenv.config();

const required = [
  "BOT_TOKEN",
  "DATABASE_URL",
];

function normalizeBaseUrl(value) {
  if (!value) return "";
  const trimmed = value.replace(/\/$/, "");
  return /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
}

const inferredPublicBaseUrl = normalizeBaseUrl(
  process.env.PUBLIC_BASE_URL || process.env.RAILWAY_PUBLIC_DOMAIN || process.env.RAILWAY_STATIC_URL || "",
);

export const config = {
  botToken: process.env.BOT_TOKEN || "",
  databaseUrl: process.env.DATABASE_URL || "",
  publicBaseUrl: inferredPublicBaseUrl,
  cashfreeClientId: process.env.CASHFREE_CLIENT_ID || "",
  cashfreeClientSecret: process.env.CASHFREE_CLIENT_SECRET || "",
  cashfreeEnv: process.env.CASHFREE_ENV || "production",
  cashfreeWebhookSecret: process.env.CASHFREE_WEBHOOK_SECRET || "",
  adminUserId: String(process.env.ADMIN_USER_ID || process.env.ADMIN_ID || ""),
  requiredChannels: (process.env.REQUIRED_CHANNELS || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean),
  supportUsername: process.env.SUPPORT_USERNAME || "@FlashXSupports",
  port: Number(process.env.PORT || 3000),
  adminWebToken: process.env.ADMIN_WEB_TOKEN || "",
  openAiApiKey: process.env.OPENAI_API_KEY || "",
  openAiModel: process.env.OPENAI_MODEL || "gpt-4o-mini",
};

export function assertConfig() {
  const missing = required.filter((key) => !process.env[key]);

  if (!config.adminUserId) {
    missing.push("ADMIN_USER_ID or ADMIN_ID");
  }

  if (missing.length) {
    throw new Error(`Missing required environment variables: ${[...new Set(missing)].join(", ")}`);
  }
}
