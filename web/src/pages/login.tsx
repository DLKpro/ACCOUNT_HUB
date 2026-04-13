import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/stores/auth-store";
import { ApiError } from "@/api/client";
import { BrandLogoAnimated } from "@/components/brand-logo-animated";
import styles from "./login.module.css";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [phase, setPhase] = useState<"splash" | "transition" | "ready">("splash");
  const login = useAuthStore((s) => s.login);
  const navigate = useNavigate();

  const handleLogoComplete = () => {
    // Brief pause after logo finishes, then start the transition
    setTimeout(() => setPhase("transition"), 300);
    // After the shrink/slide finishes, show the form
    setTimeout(() => setPhase("ready"), 1100);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      navigate("/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 429) setError("Account locked. Try again later.");
        else setError(err.detail);
      } else {
        setError("Connection failed. Is the API running?");
      }
    } finally {
      setLoading(false);
    }
  };

  const isSplash = phase === "splash";
  const isTransitioning = phase === "transition";
  const isReady = phase === "ready";

  return (
    <div className={styles.page}>
      <div className={`${styles.container} ${isReady ? styles.containerReady : ""}`}>

        {/* Logo wrapper — starts centered and large, shrinks into header position */}
        <div className={`${styles.logoStage} ${isTransitioning || isReady ? styles.logoStageSettled : ""}`}>
          <div className={`${styles.logoScale} ${isTransitioning || isReady ? styles.logoScaleSettled : ""}`}>
            <BrandLogoAnimated size={120} onComplete={handleLogoComplete} />
          </div>
        </div>

        {/* Wordmark + subtitle — hidden during splash, fade in during transition */}
        <div className={`${styles.header} ${isTransitioning || isReady ? styles.headerVisible : ""}`}>
          <h1 className={styles.wordmark}>
            <span className={styles.wordmarkLight}>account</span>
            <span className={styles.wordmarkBold}>hub</span>
          </h1>
          <p className={styles.subtitle}>Sign in to your account</p>
        </div>

        {/* Form — only rendered after transition completes */}
        {isReady && (
          <>
            <form onSubmit={handleSubmit} className={`${styles.form} ${styles.fadeUp}`}>
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

              <div className={styles.field}>
                <label className={styles.label}>Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={styles.input}
                  placeholder="********"
                  required
                />
              </div>

              <div className={styles.forgotLink}>
                <Link to="/forgot-password" className={styles.link}>Forgot password?</Link>
              </div>

              <button type="submit" disabled={loading} className={styles.button}>
                {loading ? "Signing in..." : "Sign in"}
              </button>
            </form>

            <p className={`${styles.switchLink} ${styles.fadeUp} ${styles.fadeDelay2}`}>
              Don't have an account?{" "}
              <Link to="/register" className={styles.link}>Create one</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
