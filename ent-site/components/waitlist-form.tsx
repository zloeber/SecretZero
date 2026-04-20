"use client";

import { useState } from "react";

type SubmitState = "idle" | "submitting" | "created" | "already_registered" | "error";

export function WaitlistForm() {
  const [state, setState] = useState<SubmitState>("idle");
  const [error, setError] = useState<string>("");

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState("submitting");
    setError("");

    const form = event.currentTarget;
    const payload = {
      email: String(new FormData(form).get("email") ?? ""),
      company: String(new FormData(form).get("company") ?? ""),
      useCase: String(new FormData(form).get("useCase") ?? ""),
    };

    try {
      const response = await fetch("/api/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const data = (await response.json().catch(() => ({}))) as { error?: string };
        setState("error");
        setError(data.error ?? "Something went wrong.");
        return;
      }

      const data = (await response.json()) as { status: SubmitState };
      setState(data.status === "already_registered" ? "already_registered" : "created");
      form.reset();
    } catch {
      setState("error");
      setError("Network error. Please try again.");
    }
  }

  return (
    <section className="section block signup" id="waitlist">
      <h2>Join the enterprise waitlist</h2>
      <p className="sub">One list, early access updates, rollout invites, and private preview announcements.</p>
      <form onSubmit={onSubmit} className="signup-form">
        <label>
          Work email
          <input className="input" name="email" type="email" required />
        </label>
        <label>
          Company (optional)
          <input className="input" name="company" type="text" />
        </label>
        <label>
          What are you evaluating? (optional)
          <textarea className="input" name="useCase" rows={3} />
        </label>
        <button className="btn primary" type="submit" disabled={state === "submitting"}>
          {state === "submitting" ? "Submitting..." : "Join waitlist"}
        </button>
      </form>
      {state === "created" && <p className="ok">Added. We will follow up soon.</p>}
      {state === "already_registered" && <p className="ok">You are already on the list.</p>}
      {state === "error" && <p className="error">{error}</p>}
    </section>
  );
}
