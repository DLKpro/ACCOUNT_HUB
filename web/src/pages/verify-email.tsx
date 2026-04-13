import { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { authApi } from "@/api/auth";
import { ApiError } from "@/api/client";
import { BrandLogo } from "@/components/brand-logo";
import styles from "./login.module.css";

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("Invalid verification link.");
      return;
    }
    authApi.verifyEmail(token)
      .then(() => {
        setStatus("success");
        setMessage("Your email has been verified!");
      })
      .catch((err) => {
        setStatus("error");
        setMessage(err instanceof ApiError ? err.detail : "Verification failed.");
      });
  }, [token]);

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
            <p className={styles.subtitle}>Email Verification</p>
          </div>

          <div className={styles.form}>
            {status === "loading" && <p style={{ textAlign: "center", color: "var(--color-slate)" }}>Verifying...</p>}
            {status === "success" && <div className={styles.success}>{message}</div>}
            {status === "error" && <div className={styles.error}>{message}</div>}

            <Link to="/login" className={styles.button}>
              {status === "success" ? "Sign in" : "Back to login"}
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
