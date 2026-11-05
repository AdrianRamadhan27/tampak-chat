"use client";

import { useState } from "react";
import { KeyRound, LockKeyhole } from "lucide-react";
import { errorMessage, post, setCsrf } from "@/lib/api";
import { Button, ErrorBanner } from "./ui";

export default function Login({
  onSessionChanged,
  purpose = "settings",
}: {
  onSessionChanged: () => Promise<void>;
  purpose?: "workspace" | "settings";
}) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await post<{ csrf: string }>("/session/login", {
        username,
        password,
      });
      setCsrf(result.csrf);
      setPassword("");
      await onSessionChanged();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-page">
      <div className="login-card">
        <div className="empty-icon">
          <KeyRound size={25} />
        </div>
        <span className="eyebrow">
          {purpose === "workspace" ? "TAMPAK-CHAT" : "TAMPAK-CHAT BACK OFFICE"}
        </span>
        <h1>
          {purpose === "workspace" ? (
            "The workings are inside."
          ) : (
            <>
              A little control
              <br />
              behind the visibility.
            </>
          )}
        </h1>
        <p>
          {purpose === "workspace"
            ? "Sign in to explore the documents, analytics and visible AI workflow."
            : "Sign in to manage model providers, keys and inference budgets."}
        </p>
        <form className="form-stack" onSubmit={submit}>
          {error && <ErrorBanner message={error} />}
          <label>
            Username
            <input
              name="username"
              autoComplete="username"
              required
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </label>
          <label>
            Password
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <Button type="submit" variant="primary" busy={busy}>
            Sign in
            <LockKeyhole size={14} />
          </Button>
        </form>
        <p className="muted small">
          {purpose === "workspace"
            ? "A private workspace. Use the credentials shared with you by the owner."
            : "Local credentials are stored in the private .env file and never bundled into the app."}
        </p>
      </div>
    </div>
  );
}
