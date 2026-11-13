//! Desktop shell. It holds no editor logic: it finds (or starts) the Python engine and tells the page where it is and which
//! session token to send. Everything else goes page -> engine over JSON-RPC.
use serde::Serialize;
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

#[derive(Serialize)]
struct EngineInfo { url: String, token: String, started: bool, workspace: String }

fn workspace() -> PathBuf {
    if let Ok(w) = std::env::var("FM27SE_WORKSPACE") { return PathBuf::from(w); }
    let base = std::env::var("LOCALAPPDATA").or_else(|_| std::env::var("HOME").map(|h| format!("{}/.local/share", h))).unwrap_or_default();
    PathBuf::from(base).join("FM27SkinEditor")
}

/// The engine's project folder: FM27SE_PROJECT, else the nearest parent of the executable or working directory that holds skin_editor/__main__.py.
fn project_root() -> Option<PathBuf> {
    if let Ok(p) = std::env::var("FM27SE_PROJECT") { return Some(PathBuf::from(p)); }
    let mut starts: Vec<PathBuf> = vec![];
    if let Ok(e) = std::env::current_exe() { if let Some(d) = e.parent() { starts.push(d.to_path_buf()); } }
    if let Ok(c) = std::env::current_dir() { starts.push(c); }
    for s in starts {
        let mut d: Option<&Path> = Some(s.as_path());
        while let Some(p) = d {
            if p.join("skin_editor").join("__main__.py").is_file() { return Some(p.to_path_buf()); }
            d = p.parent();
        }
    }
    None
}

fn read_last_url() -> Option<(String, u16, String)> {
    let text = std::fs::read_to_string(workspace().join("state").join("last-url")).ok()?;
    let url = text.trim().to_string();
    let rest = url.strip_prefix("http://127.0.0.1:")?;
    let (port, query) = rest.split_once("/?t=")?;
    Some((format!("http://127.0.0.1:{}", port.parse::<u16>().ok()?), port.parse().ok()?, query.to_string()))
}

fn alive(port: u16) -> bool {
    let addr: SocketAddr = ([127, 0, 0, 1], port).into();
    TcpStream::connect_timeout(&addr, Duration::from_millis(400)).is_ok()
}

/// The engine process this window started (None when it reused one that was already running: that one is not ours to stop).
struct EngineChild(Mutex<Option<Child>>);

/// Stop the engine this instance started and wait for it. On Windows the venv's python.exe starts the real interpreter as a child,
/// so the whole tree is ended (taskkill /T); another running FM Skin Studio has its own engine and is not touched.
fn stop_engine(state: &EngineChild) {
    let child = state.0.lock().ok().and_then(|mut g| g.take());
    if let Some(mut c) = child {
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            let _ = Command::new("taskkill").args(["/PID", &c.id().to_string(), "/T", "/F"]).creation_flags(0x08000000).stdout(Stdio::null()).stderr(Stdio::null()).status();
        }
        #[cfg(not(windows))]
        { let _ = c.kill(); }
        let _ = c.wait();
    }
}

/// The frozen engine (PyInstaller one-dir, see tools/freeze_engine.py): FM27SE_ENGINE, else <resource dir>/fm-skin-engine/fm-skin-engine(.exe),
/// else next to the executable. When it exists the user needs no Python at all.
fn frozen_engine(app: &tauri::AppHandle) -> Option<PathBuf> {
    use tauri::Manager;
    let exe = if cfg!(windows) { "fm-skin-engine.exe" } else { "fm-skin-engine" };
    if let Ok(p) = std::env::var("FM27SE_ENGINE") { let p = PathBuf::from(p); if p.is_file() { return Some(p); } }
    let mut dirs: Vec<PathBuf> = vec![];
    if let Ok(r) = app.path().resource_dir() { dirs.push(r); }
    if let Ok(e) = std::env::current_exe() { if let Some(d) = e.parent() { dirs.push(d.to_path_buf()); } }
    dirs.into_iter().map(|d| d.join("fm-skin-engine").join(exe)).find(|p| p.is_file())
}

#[tauri::command]
fn engine_info(app: tauri::AppHandle, state: tauri::State<EngineChild>) -> Result<EngineInfo, String> {
    if let Some((url, port, token)) = read_last_url() {
        if alive(port) { return Ok(EngineInfo { url, token, started: false, workspace: workspace().display().to_string() }); }
    }
    let before = std::fs::metadata(workspace().join("state").join("last-url")).and_then(|m| m.modified()).ok();
    let mut cmd = if let Some(frozen) = frozen_engine(&app) {
        let mut c = Command::new(&frozen);
        c.args(["serve", "--no-browser"]).current_dir(frozen.parent().unwrap_or(Path::new(".")));
        c
    } else {
        let root = project_root().ok_or("cannot find the engine (no bundled fm-skin-engine, no skin_editor/__main__.py); set FM27SE_ENGINE or FM27SE_PROJECT")?;
        let venv = root.join(".venv").join(if cfg!(windows) { "Scripts/python.exe" } else { "bin/python" });
        let python = if venv.is_file() { venv.into_os_string() } else { std::ffi::OsString::from(if cfg!(windows) { "python" } else { "python3" }) };
        let mut c = Command::new(python);
        c.args(["-m", "skin_editor", "serve", "--no-browser"]).current_dir(&root);
        c
    };
    cmd.stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null());
    #[cfg(windows)] { use std::os::windows::process::CommandExt; cmd.creation_flags(0x08000000); } // no console window
    let child = cmd.spawn().map_err(|e| format!("cannot start the engine: {e}"))?;
    *state.0.lock().map_err(|_| "engine state is locked".to_string())? = Some(child);
    let t0 = Instant::now();
    while t0.elapsed() < Duration::from_secs(25) {
        std::thread::sleep(Duration::from_millis(250));
        let now = std::fs::metadata(workspace().join("state").join("last-url")).and_then(|m| m.modified()).ok();
        if now != before || before.is_none() {
            if let Some((url, port, token)) = read_last_url() {
                if alive(port) { return Ok(EngineInfo { url, token, started: true, workspace: workspace().display().to_string() }); }
            }
        }
    }
    Err("the engine did not start within 25 seconds".into())
}

// ---- app updates (GitHub Releases, signed with the updater key; the public key and the endpoint are in tauri.conf.json)

#[derive(Serialize)]
struct UpdateInfo { version: String, current: String, notes: Option<String>, date: Option<String> }

/// FM27SE_UPDATE_URL replaces the configured endpoint (used to test an update from a local server). The signature is still checked against the
/// public key in the config, so the override cannot install anything the updater key did not sign.
fn updater(app: &tauri::AppHandle) -> Result<tauri_plugin_updater::Updater, String> {
    use tauri_plugin_updater::UpdaterExt;
    let mut b = app.updater_builder();
    if let Ok(u) = std::env::var("FM27SE_UPDATE_URL") {
        b = b.endpoints(vec![u.parse().map_err(|e| format!("FM27SE_UPDATE_URL is not a URL: {e}"))?]).map_err(|e| e.to_string())?;
    }
    b.build().map_err(|e| e.to_string())
}

/// True when the game process is running (an update must not replace files under a running game's tools, and the install closes the app).
fn game_running() -> bool {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        let out = Command::new("tasklist").args(["/FI", "IMAGENAME eq fm.exe", "/FO", "CSV", "/NH"]).creation_flags(0x08000000).output();
        return match out { Ok(o) if o.status.success() => String::from_utf8_lossy(&o.stdout).to_lowercase().contains("\"fm.exe\""), _ => true }; // cannot tell: refuse
    }
    #[cfg(not(windows))]
    { false }
}

#[tauri::command]
async fn app_update_check(app: tauri::AppHandle) -> Result<Option<UpdateInfo>, String> {
    let u = updater(&app)?.check().await.map_err(|e| e.to_string())?;
    Ok(u.map(|u| UpdateInfo { version: u.version.clone(), current: u.current_version.clone(), notes: u.body.clone(), date: u.date.map(|d| d.to_string()) }))
}

/// Download first (the engine keeps running), then stop the engine so the installer can replace its files, then install. The installer ends this
/// process and starts the new version.
#[tauri::command]
async fn app_update_install(app: tauri::AppHandle, state: tauri::State<'_, EngineChild>) -> Result<(), String> {
    if game_running() { return Err("FM27 is running: close the game before updating".into()); }
    let update = updater(&app)?.check().await.map_err(|e| e.to_string())?.ok_or("there is no update to install")?;
    let bytes = update.download(|_, _| {}, || {}).await.map_err(|e| format!("download failed: {e}"))?;
    stop_engine(&state);
    update.install(bytes).map_err(|e| format!("install failed: {e}"))?;
    app.restart()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(EngineChild(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![engine_info, app_update_check, app_update_install])
        .build(tauri::generate_context!())
        .expect("error while building FM Skin Studio")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {            // the last window is closed: end our engine and wait for it
                use tauri::Manager;
                stop_engine(&app.state::<EngineChild>());
            }
        });
}
