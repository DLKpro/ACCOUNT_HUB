import { useRef, useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import styles from "./page-transition.module.css";

interface Props {
  children: React.ReactNode;
}

export function PageTransition({ children }: Props) {
  const location = useLocation();
  const [displayChildren, setDisplayChildren] = useState(children);
  const [phase, setPhase] = useState<"enter" | "exit">("enter");
  const prevKey = useRef(location.key);

  useEffect(() => {
    if (location.key !== prevKey.current) {
      prevKey.current = location.key;
      setPhase("exit");

      const timer = setTimeout(() => {
        setDisplayChildren(children);
        setPhase("enter");
      }, 200); // matches exit animation duration

      return () => clearTimeout(timer);
    } else {
      setDisplayChildren(children);
    }
  }, [location.key, children]);

  return (
    <div className={`${styles.page} ${phase === "exit" ? styles.exit : styles.enter}`}>
      {displayChildren}
    </div>
  );
}
