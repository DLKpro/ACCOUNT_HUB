//! Account Hub desktop GUI binary.
//!
//! Phase 0: opens the existing React SPA (`web/`) in a Tauri 2 window. IPC handlers land
//! with Phase 3 per `docs/design/05-tauri-ipc.md`; for now, `tauri::Builder::default()` is
//! enough to prove the dev loop works end-to-end.

// Prevent Windows from spawning a terminal window alongside the GUI in release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    tracing::info!(
        version = env!("CARGO_PKG_VERSION"),
        "account-hub-gui starting"
    );

    tauri::Builder::default()
        .run(tauri::generate_context!())
        .map_err(|e| anyhow::anyhow!("Tauri failed to start: {e}"))?;

    Ok(())
}
