import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { closuresApi } from "@/api/closures";
import { Trash2, CheckCircle, Clock, ExternalLink } from "lucide-react";
import styles from "./closures.module.css";

export default function ClosuresPage() {
  const queryClient = useQueryClient();
  const { data: closures, isLoading } = useQuery({
    queryKey: ["closures"],
    queryFn: closuresApi.list,
  });

  const complete = useMutation({
    mutationFn: closuresApi.complete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["closures"] }),
  });

  const pending = closures?.filter((c) => c.status === "pending") ?? [];
  const completed = closures?.filter((c) => c.status === "completed") ?? [];

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Account Closures</h1>
        <p className={styles.subtitle}>Track and complete account deletion requests</p>
      </div>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>
          <Clock size={14} /> Pending ({pending.length})
        </h2>
        {isLoading ? (
          <div className={styles.empty}>Loading...</div>
        ) : pending.length > 0 ? (
          <div className={styles.closureList}>
            {pending.map((c) => (
              <div key={c.id} className={styles.closureRow}>
                <div className={styles.closureInfo}>
                  <Trash2 size={16} className={styles.closureIcon} />
                  <div>
                    <div className={styles.closureName}>{c.service_name}</div>
                    <div className={styles.closureMeta}>
                      {c.method}
                      {c.notes && ` \u00B7 ${c.notes}`}
                    </div>
                  </div>
                </div>
                <div className={styles.closureActions}>
                  {c.deletion_url && (
                    <a href={c.deletion_url} target="_blank" rel="noopener noreferrer" className={styles.linkBtn}>
                      <ExternalLink size={14} /> Open
                    </a>
                  )}
                  <button
                    onClick={() => complete.mutate(c.id)}
                    className={styles.completeBtn}
                  >
                    <CheckCircle size={14} /> Mark done
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className={styles.empty}>No pending closure requests.</div>
        )}
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>
          <CheckCircle size={14} /> Completed ({completed.length})
        </h2>
        {completed.length > 0 ? (
          <div className={styles.closureList}>
            {completed.map((c) => (
              <div key={c.id} className={`${styles.closureRow} ${styles.closureCompleted}`}>
                <div className={styles.closureInfo}>
                  <CheckCircle size={16} className={styles.completedIcon} />
                  <div>
                    <div className={styles.closureName}>{c.service_name}</div>
                    <div className={styles.closureMeta}>
                      Completed {c.completed_at ? new Date(c.completed_at).toLocaleDateString() : ""}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className={styles.empty}>No completed closures yet.</div>
        )}
      </section>
    </div>
  );
}
