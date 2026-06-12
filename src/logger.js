import pino from "pino";

export const logger = pino({
  level: process.env.LOG_LEVEL || "info",
  redact: ["BOT_TOKEN", "CASHFREE_CLIENT_SECRET", "DATABASE_URL", "*.authorization"],
});
