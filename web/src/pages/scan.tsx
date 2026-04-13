import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { scanApi } from "@/api/scan";
import { Search, ArrowRight, Play } from "lucide-react";
import styles from "./scan.module.css";

export default function ScanPage() {
  const queryClient = useQueryClient();
  const [scanMessage, setScanMessage] = useState("");
  const { data: history, isLoading } = useQuery({
    queryKey: ["scan-history"],
    queryFn: () => scanApi.history(20),
  });

  const startScan = useMutation({
    mutationFn: scanApi.start,
    onSuccess: (data) => {
      setScanMessage(`Scan started (${data.status})`);
      queryClient.invalidateQueries({ queryKey: ["scan-history"] });
    },
    onError: () => setScanMessage("Failed to start scan"),
  });

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Account Scanner</h1>
          <p className={styles.subtitle}>Discover accounts linked to your emails</p>
        </div>
        <button
          onClick={() => startScan.mutate()}
          disabled={startScan.isPending}
          className={styles.scanBtn}
        >
          <Play size={16} />
          {startScan.isPending ? "Scanning..." : "Run Scan"}
        </button>
      </div>

      {scanMessage && (
        <div className={styles.message}>{scanMessage}</div>
      )}

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Scan History</h2>
        {isLoading ? (
          <div className={styles.empty}>Loading...</div>
        ) : history && history.length > 0 ? (
          <div className={styles.scanList}>
            {history.map((scan) => (
              <Link key={scan.id} to={`/scan/${scan.id}`} className={styles.scanRow}>
                <div className={styles.scanInfo}>
                  <Search size={16} className={styles.scanIcon} />
                  <div>
                    <div className={styles.scanText}>
                      {scan.emails_scanned} email{scan.emails_scanned !== 1 ? "s" : ""} scanned
                      {" \u00B7 "}
                      <span className={styles.accent}>{scan.accounts_found} accounts</span> found
                    </div>
                    <div className={styles.scanMeta}>
                      {new Date(scan.created_at).toLocaleString()} &middot;{" "}
                      <span className={scan.status === "completed" ? styles.statusDone : styles.statusPending}>
                        {scan.status}
                      </span>
                    </div>
                  </div>
                </div>
                <ArrowRight size={16} className={styles.arrow} />
              </Link>
            ))}
          </div>
        ) : (
          <div className={styles.empty}>
            No scans yet. Click "Run Scan" to discover your accounts.
          </div>
        )}
      </section>
    </div>
  );
}
