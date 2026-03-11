/**
 * preload.js — Secure IPC bridge between Electron main process and React renderer.
 * Only explicitly exposed functions are accessible from the renderer.
 */

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  getApiUrl: () => ipcRenderer.invoke("get-api-url"),
});
