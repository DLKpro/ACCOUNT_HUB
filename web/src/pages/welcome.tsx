import { Link } from "react-router-dom";
import { BrandLogoAnimated } from "@/components/brand-logo-animated";
import styles from "./welcome.module.css";
import { useState } from "react";

export default function WelcomePage() {
  const [settled, setSettled] = useState(false);

  return (
    <div className={styles.page}>
      <div className={styles.layout}>
        <div className={`${styles.logo} ${settled ? styles.logoSettled : ""}`}>
          <BrandLogoAnimated size={140} onComplete={() => setTimeout(() => setSettled(true), 400)} />
        </div>

        <div className={`${styles.content} ${settled ? styles.contentVisible : ""}`}>
          <h1 className={styles.wordmark}>
            <span className={styles.wordmarkLight}>account</span>
            <span className={styles.wordmarkBold}>hub</span>
          </h1>
          <p className={styles.tagline}>Unified account management platform</p>

          {settled && (
            <div className={styles.actions}>
              <Link to="/register" className={styles.primaryBtn}>Create account</Link>
              <Link to="/login" className={styles.secondaryBtn}>Sign in</Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
