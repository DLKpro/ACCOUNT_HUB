import { useEffect } from "react";
import styles from "./brand-logo-animated.module.css";

interface Props {
  size?: number;
  onComplete?: () => void;
}

export function BrandLogoAnimated({ size = 80, onComplete }: Props) {
  useEffect(() => {
    if (!onComplete) return;
    // Fire after the last node animation finishes (0.9s delay + 0.3s duration)
    const timer = setTimeout(onComplete, 1200);
    return () => clearTimeout(timer);
  }, [onComplete]);

  return (
    <div className={styles.wrapper}>
      <svg
        className={styles.svg}
        width={size}
        height={size}
        viewBox="0 0 80 80"
        fill="none"
      >
        {/* Hex outline - draws in */}
        <polygon
          className={styles.hex}
          points="40,8 67.7,24 67.7,56 40,72 12.3,56 12.3,24"
          stroke="#2DD4BF"
          strokeWidth="0.6"
          fill="none"
        />

        {/* Spokes - staggered draw */}
        <line className={`${styles.spoke} ${styles.s1}`} x1="40" y1="40" x2="40" y2="8" stroke="#2DD4BF" strokeWidth="1.2" />
        <line className={`${styles.spoke} ${styles.s2}`} x1="40" y1="40" x2="67.7" y2="24" stroke="#2DD4BF" strokeWidth="1.2" />
        <line className={`${styles.spoke} ${styles.s3}`} x1="40" y1="40" x2="67.7" y2="56" stroke="#2DD4BF" strokeWidth="1.2" />
        <line className={`${styles.spoke} ${styles.s4}`} x1="40" y1="40" x2="40" y2="72" stroke="#2DD4BF" strokeWidth="1.2" />
        <line className={`${styles.spoke} ${styles.s5}`} x1="40" y1="40" x2="12.3" y2="56" stroke="#2DD4BF" strokeWidth="1.2" />
        <line className={`${styles.spoke} ${styles.s6}`} x1="40" y1="40" x2="12.3" y2="24" stroke="#2DD4BF" strokeWidth="1.2" />

        {/* Outer nodes - pop in after their spoke */}
        <circle className={`${styles.node} ${styles.n1}`} cx="40" cy="8" r="3.2" fill="#2DD4BF" />
        <circle className={`${styles.node} ${styles.n2}`} cx="67.7" cy="24" r="3.2" fill="#2DD4BF" />
        <circle className={`${styles.node} ${styles.n3}`} cx="67.7" cy="56" r="3.2" fill="#2DD4BF" />
        <circle className={`${styles.node} ${styles.n4}`} cx="40" cy="72" r="3.2" fill="#2DD4BF" />
        <circle className={`${styles.node} ${styles.n5}`} cx="12.3" cy="56" r="3.2" fill="#2DD4BF" />
        <circle className={`${styles.node} ${styles.n6}`} cx="12.3" cy="24" r="3.2" fill="#2DD4BF" />

        {/* Center hub - scales up last */}
        <circle className={styles.hub} cx="40" cy="40" r="7" fill="#2DD4BF" />
        <circle className={styles.hubInner} cx="40" cy="40" r="3" fill="#060F1E" />
      </svg>
    </div>
  );
}
