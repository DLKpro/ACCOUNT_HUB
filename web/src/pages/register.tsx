import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/stores/auth-store";
import { ApiError } from "@/api/client";
import { BrandLogo } from "@/components/brand-logo";
import styles from "./login.module.css";
import registerStyles from "./register.module.css";

export default function RegisterPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const register = useAuthStore((s) => s.register);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < 8) { setError("Password must be at least 8 characters"); return; }
    if (password !== confirm) { setError("Passwords do not match"); return; }
    setLoading(true);
    try {
      await register(username, password);
      navigate("/dashboard");
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
          <p className={styles.subtitle}>Create your account</p>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          {error && <div className={styles.error}>{error}</div>}

          <div className={styles.field}>
            <label className={styles.label}>Username</label>
            <input type="text" value={username} onChange={(e) => setUsername(e.target.value)}
              className={styles.input} placeholder="your_username" required autoFocus />
            <p className={registerStyles.hint}>3-64 characters, lowercase letters, numbers, underscores</p>
          </div>

          <div className={styles.field}>
            <label className={styles.label}>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              className={styles.input} placeholder="********" required minLength={8} />
          </div>

          <div className={styles.field}>
            <label className={styles.label}>Confirm Password</label>
            <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)}
              className={styles.input} placeholder="********" required />
          </div>

          <button type="submit" disabled={loading} className={styles.button}>
            {loading ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className={styles.switchLink}>
          Already have an account?{" "}
          <Link to="/login" className={styles.link}>Sign in</Link>
        </p>
      </div>
    </div>
  );
}
