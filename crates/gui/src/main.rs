//! Account Hub desktop GUI binary.
//!
//! Phase 0 stub — becomes a Tauri 2 app once `docs/design/05-tauri-ipc.md` is accepted.
//! For now this binary exists only to prove the workspace compiles and `core` is consumable.

fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    tracing::info!(
        version = env!("CARGO_PKG_VERSION"),
        "account-hub-gui stub — Tauri wiring lands with design doc 05"
    );
}
