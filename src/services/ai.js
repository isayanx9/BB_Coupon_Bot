import axios from "axios";
import { config } from "../config.js";
import { approvedKnowledge, getMemory, saveSupportConversation } from "../repositories.js";

const allowedTopics = [
  "coupon",
  "order",
  "payment",
  "referral",
  "wallet",
  "bot",
  "cashfree",
  "support",
  "reward",
  "channel",
  "admin",
  "flash",
];

export function isBotQuestion(text) {
  const normalized = text.toLowerCase();
  return allowedTopics.some((topic) => normalized.includes(topic));
}

export async function answerSupport(userId, text) {
  if (!isBotQuestion(text)) {
    const answer = "I'm designed to help with FlashX coupons, payments, referrals and orders.";
    await saveSupportConversation(userId, text, answer);
    return answer;
  }

  const knowledge = await approvedKnowledge();
  const memory = await getMemory(userId);
  const context = [
    "You are Cutie, the FlashXBBbot support assistant.",
    "Only answer questions about FlashX coupons, payments, referrals, wallet, orders, rewards and bot usage.",
    "Never expose private user information. Never modify source code automatically.",
    `Approved knowledge: ${JSON.stringify(knowledge)}`,
    `User memory: ${JSON.stringify(memory)}`,
  ].join("\n");

  if (!config.openAiApiKey) {
    const answer = localAnswer(text);
    await saveSupportConversation(userId, text, answer);
    return answer;
  }

  try {
    const response = await axios.post(
      "https://api.openai.com/v1/chat/completions",
      {
        model: config.openAiModel,
        messages: [
          { role: "system", content: context },
          { role: "user", content: text },
        ],
        temperature: 0.25,
      },
      {
        headers: { Authorization: `Bearer ${config.openAiApiKey}` },
        timeout: 20000,
      },
    );
    const answer = response.data.choices?.[0]?.message?.content?.trim() || localAnswer(text);
    await saveSupportConversation(userId, text, answer);
    return answer;
  } catch {
    const answer = localAnswer(text);
    await saveSupportConversation(userId, text, answer);
    return answer;
  }
}

function localAnswer(text) {
  const normalized = text.toLowerCase();

  if (normalized.includes("payment") || normalized.includes("cashfree")) {
    return "Payments are handled by Cashfree. Open My Orders, tap recheck if you paid, and contact support with your order ID if delivery is delayed.";
  }
  if (normalized.includes("referral")) {
    return "Share your Refer & Earn link. A referral earns 1 credit after the invited user starts the bot and joins the required channels.";
  }
  if (normalized.includes("wallet")) {
    return "Wallet credits are worth rupee value inside the bot. Credits can come from referrals, daily rewards, lucky rewards, or admin adjustments.";
  }
  if (normalized.includes("coupon") || normalized.includes("order")) {
    return "Use Flash Deals or Hot Coupons, choose a coupon card, pay if needed, and the code is delivered instantly after verification.";
  }
  return "I can help with FlashX coupons, orders, payments, referrals, wallet, rewards and bot usage.";
}
