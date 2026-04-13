import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/auth-store";
import { emailsApi } from "@/api/emails";
import { scanApi } from "@/api/scan";
import { closuresApi } from "@/api/closures";
import { Mail, Search, Trash2, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import styles from "./dashboard.module.css";

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user);
  const { data: emails } = useQuery({ queryKey: ["emails"], queryFn: emailsApi.list });
  const { data: scans } = useQuery({ queryKey: ["scan-history"], queryFn: () => scanApi.history(1) });
  const { data: closures } = useQuery({ queryKey: ["closures"], queryFn: closuresApi.list });

  const latestScan = scans?.[0];
  const pendingClosures = closures?.filter((c) => c.status === "pending") ?? [];

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>
          Welcome back, <span className={styles.accent}>{user?.username}</span>
        </h1>
        <p className={styles.subtitle}>Your digital footprint overview</p>
      </div>

      <div className={styles.stats}>
        <Link to="/emails" className={styles.statCard}>
          <div className={styles.statIcon}><Mail size={20} /></div>
          <div>
            <div className={styles.statValue}>{emails?.length ?? 0}</div>
            <div className={styles.statLabel}>Emails linked</div>
          </div>
        </Link>
        <Link to="/scan" className={styles.statCard}>
          <div className={styles.statIcon}><Search size={20} /></div>
          <div>
            <div className={styles.statValue}>{latestScan?.accounts_found ?? 0}</div>
            <div className={styles.statLabel}>Accounts discovered</div>
          </div>
        </Link>
        <Link to="/closures" className={styles.statCard}>
          <div className={styles.statIcon}><Trash2 size={20} /></div>
          <div>
            <div className={styles.statValue}>{pendingClosures.length}</div>
            <div className={styles.statLabel}>Pending closures</div>
          </div>
        </Link>
      </div>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Recent Scan</h2>
        {latestScan ? (
          <div className={styles.card}>
            <div className={styles.cardRow}>
              <div>
                <div className={styles.cardText}>
                  {latestScan.emails_scanned} email{latestScan.emails_scanned !== 1 ? "s" : ""} scanned
                  {" \u00B7 "}
                  <span className={styles.accent}>{latestScan.accounts_found} accounts</span> found
                </div>
                <div className={styles.cardMeta}>{new Date(latestScan.created_at).toLocaleDateString()}</div>
              </div>
              <Link to={`/scan/${latestScan.id}`} className={styles.cardLink}>
                View results <ArrowRight size={14} />
              </Link>
            </div>
          </div>
        ) : (
          <div className={styles.emptyCard}>
            <p className={styles.emptyText}>No scans yet</p>
            <Link to="/scan" className={styles.emptyLink}>Run your first scan</Link>
          </div>
        )}
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Linked Emails</h2>
        {emails && emails.length > 0 ? (
          <div className={styles.emailList}>
            {emails.map((email) => (
              <div key={email.id} className={styles.emailRow}>
                <div className={styles.emailInfo}>
                  <Mail size={16} className={styles.emailIcon} />
                  <span className={styles.emailAddress}>{email.email_address}</span>
                </div>
                <span className={styles.emailBadge}>{email.provider}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className={styles.emptyCard}>
            <p className={styles.emptyText}>No linked emails</p>
            <Link to="/emails" className={styles.emptyLink}>Link your first email</Link>
          </div>
        )}
      </section>
    </div>
  );
}
