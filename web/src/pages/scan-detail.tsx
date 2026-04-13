import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { scanApi } from "@/api/scan";
import { closuresApi } from "@/api/closures";
import { ArrowLeft, Download, Shield, Trash2 } from "lucide-react";
import styles from "./scan-detail.module.css";

export default function ScanDetailPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const queryClient = useQueryClient();
  const { data: scan, isLoading } = useQuery({
    queryKey: ["scan", sessionId],
    queryFn: () => scanApi.detail(sessionId!),
    enabled: !!sessionId,
  });

  const requestClosure = useMutation({
    mutationFn: closuresApi.request,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["closures"] });
    },
  });

  const handleExport = async () => {
    if (!sessionId) return;
    const csv = await scanApi.exportCsv(sessionId);
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `scan_${sessionId.slice(0, 8)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) return <div className={styles.page}>Loading...</div>;
  if (!scan) return <div className={styles.page}>Scan not found</div>;

  return (
    <div className={styles.page}>
      <Link to="/scan" className={styles.back}><ArrowLeft size={16} /> Back to scans</Link>

      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Scan Results</h1>
          <p className={styles.subtitle}>
            {scan.emails_scanned} email{scan.emails_scanned !== 1 ? "s" : ""} scanned &middot;{" "}
            <span className={styles.accent}>{scan.accounts_found} accounts</span> discovered
          </p>
        </div>
        <button onClick={handleExport} className={styles.exportBtn}>
          <Download size={16} /> Export CSV
        </button>
      </div>

      {scan.results.length > 0 ? (
        <div className={styles.resultList}>
          {scan.results.map((account) => (
            <div key={account.id} className={styles.resultRow}>
              <div className={styles.resultInfo}>
                <Shield size={16} className={styles.resultIcon} />
                <div>
                  <div className={styles.resultName}>{account.service_name}</div>
                  <div className={styles.resultMeta}>
                    {account.email_address}
                    {account.service_domain && ` \u00B7 ${account.service_domain}`}
                    {" \u00B7 "}
                    <span className={
                      account.confidence === "confirmed" ? styles.confirmed :
                      account.confidence === "likely" ? styles.likely : styles.possible
                    }>{account.confidence}</span>
                  </div>
                </div>
              </div>
              <button
                onClick={() => requestClosure.mutate(account.id)}
                className={styles.closeBtn}
                title="Request closure"
              >
                <Trash2 size={14} /> Close
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className={styles.empty}>No accounts discovered in this scan.</div>
      )}
    </div>
  );
}
