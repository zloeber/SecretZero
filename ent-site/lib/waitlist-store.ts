import { kv } from "@vercel/kv";
import crypto from "node:crypto";

export type SignupInput = {
  email: string;
  company?: string;
  useCase?: string;
};

export type SignupResult = {
  status: "created" | "already_registered";
};

export interface WaitlistStore {
  put(input: SignupInput): Promise<SignupResult>;
}

function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

function emailKey(email: string): string {
  const hash = crypto.createHash("sha256").update(normalizeEmail(email)).digest("hex");
  return `waitlist:${hash}`;
}

export class KVWaitlistStore implements WaitlistStore {
  async put(input: SignupInput): Promise<SignupResult> {
    const key = emailKey(input.email);
    const exists = await kv.exists(key);
    if (exists) {
      return { status: "already_registered" };
    }

    await kv.hset(key, {
      email: normalizeEmail(input.email),
      company: input.company ?? "",
      use_case: input.useCase ?? "",
      created_at: new Date().toISOString(),
    });
    return { status: "created" };
  }
}
