import { useState } from "react";
import { Link } from "react-router-dom";
import { authApi } from "@/api/auth";
import { ApiError } from "@/api/client";
import styles from "./login.module.css";

export default function ForgotPasswordPage() {
  const [username, setUsername] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [resetUrl, setResetUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess(false);
    setResetUrl(null);
    setLoading(true);
    try {
      const result = await authApi.forgotPassword(username);
      setSuccess(true);
      if (result.reset_url) {
        setResetUrl(result.reset_url);
      }
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
      else setError("Connection failed. Is the API running?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.container}>
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
              A reset link has been generated.
            </div>
            {resetUrl && (
              <Link to={resetUrl} className={styles.button}>
                Reset Password
              </Link>
            )}
            <p className={styles.switchLink}>
              <Link to="/login" className={styles.link}>Back to sign in</Link>
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className={styles.form}>
            {error && <div className={styles.error}>{error}</div>}

            <div className={styles.field}>
              <label className={styles.label}>Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className={styles.input}
                placeholder="your_username"
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
  );
}
