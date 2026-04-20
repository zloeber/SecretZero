import { NextResponse } from "next/server";
import { signupSchema } from "../../../lib/signup";
import { KVWaitlistStore } from "../../../lib/waitlist-store";

const store = new KVWaitlistStore();

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const parsed = signupSchema.safeParse(body);
    if (!parsed.success) {
      return NextResponse.json({ error: "Invalid payload." }, { status: 400 });
    }

    const result = await store.put(parsed.data);
    return NextResponse.json(result, { status: 200 });
  } catch {
    return NextResponse.json({ error: "Unable to process signup." }, { status: 500 });
  }
}
