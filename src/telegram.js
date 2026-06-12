import axios from "axios";
import { logger } from "./logger.js";

export class TelegramClient {
  constructor(token) {
    this.token = token;
    this.api = axios.create({
      baseURL: `https://api.telegram.org/bot${token}`,
      timeout: 30000,
    });
    this.offset = 0;
    this.running = false;
  }

  async request(method, payload = {}) {
    const response = await this.api.post(`/${method}`, payload);
    if (!response.data.ok) throw new Error(response.data.description || `Telegram ${method} failed`);
    return response.data.result;
  }

  async sendMessage(chatId, text, options = {}) {
    return this.request("sendMessage", {
      chat_id: chatId,
      text,
      ...options,
    });
  }

  async sendPhoto(chatId, photo, options = {}) {
    return this.request("sendPhoto", {
      chat_id: chatId,
      photo,
      ...options,
    });
  }

  async editMessageText(chatId, messageId, text, options = {}) {
    return this.request("editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text,
      ...options,
    });
  }

  async answerCallbackQuery(callbackQueryId, options = {}) {
    return this.request("answerCallbackQuery", {
      callback_query_id: callbackQueryId,
      ...options,
    });
  }

  async getChatMember(chatId, userId) {
    return this.request("getChatMember", {
      chat_id: chatId,
      user_id: userId,
    });
  }

  async getMe() {
    return this.request("getMe");
  }

  async startPolling({ onMessage, onCallbackQuery }) {
    this.running = true;

    while (this.running) {
      try {
        const updates = await this.request("getUpdates", {
          offset: this.offset,
          timeout: 25,
          allowed_updates: ["message", "callback_query"],
        });

        for (const update of updates) {
          this.offset = update.update_id + 1;
          if (update.message) await onMessage(update.message);
          if (update.callback_query) await onCallbackQuery(update.callback_query);
        }
      } catch (error) {
        logger.error({ error }, "Telegram polling failed");
        await new Promise((resolve) => setTimeout(resolve, 3000));
      }
    }
  }

  stop() {
    this.running = false;
  }
}
