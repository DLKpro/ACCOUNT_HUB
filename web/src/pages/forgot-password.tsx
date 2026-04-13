import { useState } from "react";
import { Link } from "react-router-dom";
import { authApi } from "@/api/auth";
import { ApiError } from "@/api/client";
import { BrandLogo } from "@/components/brand-logo";
import styles from "./login.module.css";

export default function ForgotPasswordPage() {
  const [username, setUsername] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess(false);
    setLoading(true);
    try {
      await authApi.forgotPassword(username);
      setSuccess(true);
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
      else setError("Connection failed. Is the API running?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.layout}>
        <div className={styles.logo} style={{ transform: "scale(0.4)" }}>
          <BrandLogo size={140} />
        </div>
        <div className={styles.content} style={{ opacity: 1, transform: "translateY(0)" }}>
          <div className={styles.header}>
            <h1 className={styles.wordmark}>
              <span className={styles.wordmarkLight}>account</span>
              <span className={styles.wordmarkBold}>hub</span>
            </h1>
            <p className={styles.subtitle}>Reset your password</p>
          </div>

          {success ? (
            <div className={styles.form}>
              <div className={styles.success}>
                If that account exists, a reset link has been sent to the registered email.
              </div>
              <p className={styles.switchLink}>
                <Link to="/login" className={styles.link}>Back to sign in</Link>
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className={styles.form}>
              {error && <div className={styles.error}>{error}</div>}

              <div className={styles.field}>
                <label className={styles.label}>Username or email</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className={styles.input}
                  placeholder="your_username or you@example.com"
                  required
                  autoFocus
                />
              </div>

              <button type="submit" disabled={loading} className={styles.button}>
                {loading ? "Sending..." : "Send reset link"}
              </button>

              <p className={styles.switchLink}>
                Remember your password?{" "}
                <Link to="/login" className={styles.link}>Sign in</Link>
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
