/**
 * electron.js — YieldVision Electron main process
 *
 * Responsibilities:
 *  - Create the BrowserWindow
 *  - Load the React app (dev: localhost:3000, prod: build/index.html)
 *  - Handle offline-first: no internet required to launch
 *  - Basic window state persistence (size + position)
 */

const { app, BrowserWindow, shell, ipcMain } = require("electron");
const path = require("path");
const isDev = !app.isPackaged;

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 960,
    minHeight: 640,
    title: "YieldVision",
    backgroundColor: "#D5DDDF",  // matches light mode bg — no white flash on load
    webPreferences: {
      nodeIntegration: false,       // security: keep Node out of renderer
      contextIsolation: true,       // security: isolate preload context
      preload: path.join(__dirname, "preload.js"),
    },
    // Frameless look on macOS
    titleBarStyle: process.platform === "darwin" ? "hiddenInset" : "default",
    show: false,  // wait for ready-to-show to avoid blank flash
  });

  // Load app
  if (isDev) {
    mainWindow.loadURL("http://localhost:3000");
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    mainWindow.loadFile(path.join(__dirname, "build", "index.html"));
  }

  // Show only when fully loaded (no blank flash)
  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  // Open external links in system browser, not Electron
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// ── App lifecycle ─────────────────────────────────────────────────────────────

app.whenReady().then(() => {
  createWindow();

  // macOS: re-create window when dock icon clicked and no windows exist
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  // On macOS, apps stay alive until explicit Cmd+Q
  if (process.platform !== "darwin") app.quit();
});

// ── IPC: expose server URL to renderer ───────────────────────────────────────
// The renderer reads this so it knows where the FastAPI backend lives.
// In production you could point this to a bundled server or a local IP.
ipcMain.handle("get-api-url", () => {
  return process.env.YIELDVISION_API_URL || "http://localhost:8000";
});
