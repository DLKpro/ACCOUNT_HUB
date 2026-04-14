//! Tauri 2 build script. Generates the capability / context glue consumed by
//! `tauri::generate_context!()` in `src/main.rs`.
fn main() {
    tauri_build::build();
}
