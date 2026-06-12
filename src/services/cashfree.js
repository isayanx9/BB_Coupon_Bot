import axios from "axios";
import { config } from "../config.js";

function baseUrl() {
  return config.cashfreeEnv === "sandbox"
    ? "https://sandbox.cashfree.com/pg"
    : "https://api.cashfree.com/pg";
}

function headers() {
  return {
    "Content-Type": "application/json",
    "x-client-id": config.cashfreeClientId,
    "x-client-secret": config.cashfreeClientSecret,
    "x-api-version": "2023-08-01",
  };
}

export async function createCashfreeOrder(order, userId) {
  const payload = {
    order_id: order.order_id,
    order_amount: Number(order.payable_amount),
    order_currency: "INR",
    customer_details: {
      customer_id: String(userId),
      customer_name: `Telegram ${userId}`,
      customer_phone: "9999999999",
    },
    order_meta: {
      return_url: `${config.publicBaseUrl}/pay/${order.order_id}?status={order_status}`,
      notify_url: `${config.publicBaseUrl}/webhook/cashfree`,
    },
  };

  const response = await axios.post(`${baseUrl()}/orders`, payload, { headers: headers(), timeout: 20000 });
  return response.data;
}

export async function getCashfreeOrder(orderId) {
  const response = await axios.get(`${baseUrl()}/orders/${orderId}`, { headers: headers(), timeout: 20000 });
  return response.data;
}

export function validateCashfreeWebhook(req) {
  if (!config.cashfreeWebhookSecret) return true;
  const signature = req.get("x-webhook-signature") || "";
  return signature === config.cashfreeWebhookSecret;
}
