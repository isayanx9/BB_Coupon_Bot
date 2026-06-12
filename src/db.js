import pg from "pg";
import { config } from "./config.js";
import { logger } from "./logger.js";

export const pool = new pg.Pool({
  connectionString: config.databaseUrl,
  connectionTimeoutMillis: 10000,
  query_timeout: 10000,
  ssl: config.databaseUrl.includes("railway") || config.databaseUrl.includes("postgres")
    ? { rejectUnauthorized: false }
    : false,
});

pool.on("error", (error) => {
  logger.error({ error }, "Unexpected PostgreSQL pool error");
});

export async function query(text, params = []) {
  return pool.query(text, params);
}

export async function withTransaction(fn) {
  const client = await pool.connect();

  try {
    await client.query("BEGIN");
    const result = await fn(client);
    await client.query("COMMIT");
    return result;
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}
