import { useState } from "react";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import { authApi } from "@/api/auth";
import { ApiError } from "@/api/client";
import { BrandLogo } from "@/components/brand-logo";
import styles from "./login.module.css";
import registerStyles from "./register.module.css";

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const navigate = useNavigate();

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  if (!token) {
    return (
      <div className={styles.page}>
        <div className={styles.container}>
          <div className={styles.header}>
            <h1 className={styles.wordmark}>
              <span className={styles.wordmarkLight}>account</span>
              <span className={styles.wordmarkBold}>hub</span>
            </h1>
            <p className={styles.subtitle}>Invalid reset link</p>
          </div>
          <div className={styles.form}>
            <div className={styles.error}>
              This reset link is invalid or has expired.
            </div>
            <Link to="/forgot-password" className={styles.button}>
              Request a new link
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < 8) { setError("Password must be at least 8 characters"); return; }
    if (password !== confirm) { setError("Passwords do not match"); return; }
    setLoading(true);
    try {
      await authApi.resetPassword(token, password);
      setSuccess(true);
      setTimeout(() => navigate("/login"), 2000);
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
          <BrandLogo size={56} />
          <h1 className={styles.wordmark}>
            <span className={styles.wordmarkLight}>account</span>
            <span className={styles.wordmarkBold}>hub</span>
          </h1>
          <p className={styles.subtitle}>Set your new password</p>
        </div>

        {success ? (
          <div className={styles.form}>
            <div className={styles.success}>
              Password reset successfully! Redirecting to login...
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className={styles.form}>
            {error && <div className={styles.error}>{error}</div>}

            <div className={styles.field}>
              <label className={styles.label}>New Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={styles.input}
                placeholder="********"
                required
                minLength={8}
                autoFocus
              />
              <p className={registerStyles.hint}>At least 8 characters</p>
            </div>

            <div className={styles.field}>
              <label className={styles.label}>Confirm Password</label>
              <input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className={styles.input}
                placeholder="********"
                required
              />
            </div>

            <button type="submit" disabled={loading} className={styles.button}>
              {loading ? "Resetting..." : "Reset password"}
            </button>

            <p className={styles.switchLink}>
              <Link to="/login" className={styles.link}>Back to sign in</Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
