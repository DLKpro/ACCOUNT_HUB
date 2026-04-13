import { Outlet } from "react-router-dom";
import { Sidebar } from "./sidebar";
import styles from "./app-layout.module.css";

export function AppLayout() {
  return (
    <div className={styles.layout}>
      <Sidebar />
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}
