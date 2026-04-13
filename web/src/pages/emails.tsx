import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { emailsApi } from "@/api/emails";
import { apiFetch } from "@/api/client";
import type { InitiateResponse } from "@/types/api";
import { Mail, Trash2, Plus, Loader2 } from "lucide-react";
import styles from "./emails.module.css";

function useLinkEmail() {
  const queryClient = useQueryClient();
  const [linking, setLinking] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [deviceCode, setDeviceCode] = useState<{
    userCode: string;
    verificationUri: string;
    deviceCode: string;
    provider: string;
    interval: number;
  } | null>(null);

  const startLink = async (provider: string) => {
    setError("");
    setLinking(provider);
    setDeviceCode(null);
    try {
      const result = await apiFetch<InitiateResponse>("/oauth/initiate", {
        method: "POST",
        body: JSON.stringify({ provider }),
      });

      if (result.device_code && result.user_code && result.verification_uri) {
        // Device code flow (Microsoft)
        setDeviceCode({
          userCode: result.user_code,
          verificationUri: result.verification_uri,
          deviceCode: result.device_code,
          provider,
          interval: result.interval ?? 5,
        });
        window.open(result.verification_uri, "_blank");
      } else if (result.auth_url) {
        // Loopback flow - open in popup, user completes OAuth there
        // The callback needs to be handled by the CLI for now
        window.open(result.auth_url, "_blank", "width=500,height=700");
        setError("Complete the sign-in in the popup window, then use the CLI to finish linking.");
        setLinking(null);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to start OAuth");
      setLinking(null);
    }
  };

  const pollDeviceCode = async () => {
    if (!deviceCode) return;
    try {
      const result = await apiFetch<{ status?: string; email_address?: string }>("/oauth/poll", {
        method: "POST",
        body: JSON.stringify({ provider: deviceCode.provider, device_code: deviceCode.deviceCode }),
      });
      if (result.status === "pending") {
        return false; // still waiting
      }
      // Success
      setDeviceCode(null);
      setLinking(null);
      queryClient.invalidateQueries({ queryKey: ["emails"] });
      return true;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Polling failed");
      setDeviceCode(null);
      setLinking(null);
      return false;
    }
  };

  return { linking, error, deviceCode, startLink, pollDeviceCode, setError, setDeviceCode, setLinking };
}

export default function EmailsPage() {
  const queryClient = useQueryClient();
  const { data: emails, isLoading } = useQuery({ queryKey: ["emails"], queryFn: emailsApi.list });
  const { linking, error, deviceCode, startLink, pollDeviceCode, setDeviceCode, setLinking, setError } = useLinkEmail();
  const [polling, setPolling] = useState(false);

  const unlink = useMutation({
    mutationFn: emailsApi.unlink,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["emails"] }),
  });

  const handlePoll = async () => {
    setPolling(true);
    const done = await pollDeviceCode();
    if (!done) {
      // Poll again after interval
      setTimeout(async () => {
        const done2 = await pollDeviceCode();
        setPolling(false);
        if (!done2) setError("Still waiting for authorization. Try clicking 'Check status' again.");
      }, (deviceCode?.interval ?? 5) * 1000);
    } else {
      setPolling(false);
    }
  };

  const providers = [
    { id: "google", name: "Google", color: "#EA4335" },
    { id: "microsoft", name: "Microsoft", color: "#00A4EF" },
    { id: "apple", name: "Apple", color: "#A2AAAD" },
    { id: "meta", name: "Meta", color: "#0668E1" },
  ];

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Linked Emails</h1>
        <p className={styles.subtitle}>Connect email accounts to discover associated services</p>
      </div>

      {error && <div className={styles.error}>{error}</div>}

      {deviceCode && (
        <div className={styles.deviceCodeCard}>
          <h3 className={styles.deviceCodeTitle}>Complete sign-in for {linking}</h3>
          <p className={styles.deviceCodeText}>
            Go to <a href={deviceCode.verificationUri} target="_blank" rel="noopener noreferrer" className={styles.deviceCodeLink}>{deviceCode.verificationUri}</a> and enter this code:
          </p>
          <div className={styles.deviceCodeValue}>{deviceCode.userCode}</div>
          <div className={styles.deviceCodeActions}>
            <button onClick={handlePoll} disabled={polling} className={styles.pollBtn}>
              {polling ? <><Loader2 size={14} className={styles.spin} /> Checking...</> : "Check status"}
            </button>
            <button onClick={() => { setDeviceCode(null); setLinking(null); }} className={styles.cancelBtn}>
              Cancel
            </button>
          </div>
        </div>
      )}

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Link a new email</h2>
        <div className={styles.providerGrid}>
          {providers.map((p) => (
            <button
              key={p.id}
              onClick={() => startLink(p.id)}
              disabled={!!linking}
              className={styles.providerCard}
            >
              <div className={styles.providerDot} style={{ backgroundColor: p.color }} />
              <span>{p.name}</span>
              {linking === p.id ? <Loader2 size={14} className={`${styles.providerArrow} ${styles.spin}`} /> : <Plus size={14} className={styles.providerArrow} />}
            </button>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Your emails</h2>
        {isLoading ? (
          <div className={styles.empty}>Loading...</div>
        ) : emails && emails.length > 0 ? (
          <div className={styles.emailList}>
            {emails.map((email) => (
              <div key={email.id} className={styles.emailRow}>
                <div className={styles.emailInfo}>
                  <Mail size={16} className={styles.emailIcon} />
                  <div>
                    <div className={styles.emailAddress}>{email.email_address}</div>
                    <div className={styles.emailMeta}>
                      {email.provider} &middot; {email.is_verified ? "Verified" : "Unverified"}
                      {email.linked_at && ` \u00B7 Linked ${new Date(email.linked_at).toLocaleDateString()}`}
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => { if (confirm("Unlink this email?")) unlink.mutate(email.id); }}
                  className={styles.unlinkBtn}
                  title="Unlink email"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className={styles.empty}>
            No linked emails yet. Link one above to get started.
          </div>
        )}
      </section>
    </div>
  );
}
