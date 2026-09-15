import { useState, type FormEvent } from "react";
import { ArrowUpRight, LoaderCircle } from "lucide-react";
import { request, setToken } from "../lib/api";
import type { User } from "../lib/types";
export function Brand() {
  return (
    <span className="brand">
      <span className="brand-mark" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      Convene<span className="brand-dot">.</span>
    </span>
  );
}
export default function Auth({ onLogin }: { onLogin: (user: User) => void }) {
  const [signup, setSignup] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(e.currentTarget);
    try {
      const result = await request<{ token: string; user: User }>(
        `/auth/${signup ? "register" : "login"}`,
        { method: "POST", body: JSON.stringify(Object.fromEntries(form)) },
      );
      setToken(result.token);
      onLogin(result.user);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Unable to connect. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth-page">
      <div className="auth-story">
        <Brand />
        <div>
          <span className="eyebrow">A little collective intelligence</span>
          <h1>
            Better answers.
            <br />
            More perspective.
          </h1>
          <p>
            A thoughtful space to explore ideas, compare perspectives, and find
            a clearer way forward.
          </p>
          <div className="orbit" aria-hidden="true">
            <span />
            <span />
            <span />
            <b>c.</b>
          </div>
        </div>
        <span className="quiet">
          Independent thinking. Shared understanding.
        </span>
      </div>
      <div className="auth-panel">
        <form onSubmit={submit} className="auth-form">
          <span className="eyebrow">Your thinking space</span>
          <h2>{signup ? "Make yourself at home." : "Welcome back."}</h2>
          <p>
            {signup
              ? "Create your Convene account to get started."
              : "Sign in to pick up where you left off."}
          </p>
          <label>
            Email address
            <input
              name="email"
              type="email"
              autoComplete="email"
              required
              placeholder="you@example.com"
              maxLength={254}
            />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              autoComplete={signup ? "new-password" : "current-password"}
              minLength={10}
              maxLength={256}
              required
              placeholder="At least 10 characters"
            />
          </label>
          {signup && (
            <label>
              Invite code{" "}
              <span className="quiet">if your host provided one</span>
              <input
                name="invite_code"
                autoComplete="off"
                maxLength={256}
                placeholder="Your invitation"
              />
            </label>
          )}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button className="primary" disabled={busy}>
            {busy ? (
              <LoaderCircle className="spin" size={18} />
            ) : (
              <ArrowUpRight size={18} />
            )}
            {signup ? "Create account" : "Sign in"}
          </button>
          <p className="auth-switch">
            {signup ? "Already have an account?" : "New to Convene?"}{" "}
            <button
              type="button"
              className="text-button"
              onClick={() => {
                setSignup(!signup);
                setError("");
              }}
            >
              {signup ? "Sign in" : "Create an account"}
            </button>
          </p>
        </form>
        <small className="quiet">
          Your conversations stay in your workspace.
        </small>
      </div>
    </main>
  );
}
