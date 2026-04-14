//! Account Hub CLI binary.
//!
//! Phase 0 stub — becomes a clap-based CLI once the OAuth provider design and the CLI command
//! surface are specified. For now this binary exists to prove the workspace compiles and
//! `core` is consumable by a non-Tauri bin.

fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    tracing::info!(
        version = env!("CARGO_PKG_VERSION"),
        "account-hub CLI stub — clap wiring lands alongside the CLI command surface spec"
    );
}
