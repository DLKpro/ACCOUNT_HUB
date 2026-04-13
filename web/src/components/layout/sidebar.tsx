import { NavLink, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/stores/auth-store";
import { BrandLogo } from "@/components/brand-logo";
import { LayoutDashboard, Mail, Search, Trash2, Settings, LogOut } from "lucide-react";
import styles from "./sidebar.module.css";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/emails", label: "Emails", icon: Mail },
  { to: "/scan", label: "Scan", icon: Search },
  { to: "/closures", label: "Closures", icon: Trash2 },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const logout = useAuthStore((s) => s.logout);
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>
        <BrandLogo size={32} />
        <span className={styles.brandText}>
          <span className={styles.brandLight}>account</span>
          <span className={styles.brandBold}>hub</span>
        </span>
      </div>

      <nav className={styles.nav}>
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `${styles.navItem} ${isActive ? styles.navItemActive : ""}`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className={styles.footer}>
        <div className={styles.userInfo}>
          <div className={styles.username}>{user?.username}</div>
          <div className={styles.userStatus}>Active</div>
        </div>
        <button onClick={handleLogout} className={styles.logoutBtn} title="Logout">
          <LogOut size={16} />
        </button>
      </div>
    </aside>
  );
}
