// RoverControl.jsx
// YieldVision — Rover Control Panel
// For React + Electron desktop app
//
// How it works:
//   1. User enters rover IP (always 192.168.4.1 — ESP8266 AP default)
//   2. Click Connect — polls GET /status to confirm rover is reachable
//   3. Arrow buttons or WASD keys send GET /cmd?dir=X to ESP8266
//   4. ESP8266 forwards single char to Mega over Serial1
//   5. Mega executes motor command
//   6. "Take Reading" button sends 'R' — rover stops, reads all sensors, logs to SD
//
// All fetch() calls go to http://192.168.4.1/cmd?dir=X
// No backend server needed — direct HTTP to ESP8266.
//
// Install dependency: npm install lucide-react  (for icons)

import { useState, useEffect, useCallback, useRef } from "react";

// ── Rover IP is always the ESP8266 AP address ─────────────────────────────
const DEFAULT_ROVER_IP = "192.168.4.1";
const ROVER_PORT = 80;

// ── Command map ───────────────────────────────────────────────────────────
const CMD = {
  forward:  "w",
  backward: "s",
  left:     "a",
  right:    "d",
  stop:     " ",
  burnout:  "b",
  circle:   "c",
  read:     "r",   // NEW: triggers sensor reading on Mega
};

const KEY_MAP = {
  w: "forward",  W: "forward",  ArrowUp:    "forward",
  s: "backward", S: "backward", ArrowDown:  "backward",
  a: "left",     A: "left",     ArrowLeft:  "left",
  d: "right",    D: "right",    ArrowRight: "right",
  " ": "stop",
};

export default function RoverControl() {
  const [roverIp, setRoverIp]       = useState(DEFAULT_ROVER_IP);
  const [connected, setConnected]   = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [activeDir, setActiveDir]   = useState("stop");
  const [statusMsg, setStatusMsg]   = useState("Not connected");
  const [lastReading, setLastReading] = useState(null);
  const [readingPending, setReadingPending] = useState(false);
  const [roverStatus, setRoverStatus] = useState(null);

  const heldKeys = useRef(new Set());
  const pollRef  = useRef(null);

  // ── HTTP helper ──────────────────────────────────────────────────────────
  const roverUrl = useCallback(
    (path) => `http://${roverIp}:${ROVER_PORT}${path}`,
    [roverIp]
  );

  const sendCmd = useCallback(
    async (cmdChar) => {
      if (!connected) return;
      try {
        await fetch(roverUrl(`/cmd?dir=${encodeURIComponent(cmdChar)}`));
      } catch {
        // Silently drop — rover may have moved out of range momentarily
      }
    },
    [connected, roverUrl]
  );

  // ── Direction handler ────────────────────────────────────────────────────
  const drive = useCallback(
    (direction) => {
      setActiveDir(direction);
      sendCmd(CMD[direction] ?? " ");
    },
    [sendCmd]
  );

  // ── Connect / Disconnect ──────────────────────────────────────────────────
  const handleConnect = async () => {
    if (connected) {
      sendCmd(CMD.stop);
      setConnected(false);
      setActiveDir("stop");
      setStatusMsg("Disconnected");
      clearInterval(pollRef.current);
      return;
    }

    setConnecting(true);
    setStatusMsg("Connecting...");
    try {
      const res = await fetch(roverUrl("/status"), { signal: AbortSignal.timeout(3000) });
      if (res.ok) {
        const data = await res.json();
        setRoverStatus(data);
        setConnected(true);
        setStatusMsg(`Connected — ${data.clients ?? 1} device(s) on network`);
        // Start polling status every second
        pollRef.current = setInterval(pollStatus, 1000);
      } else {
        setStatusMsg(`Rover returned HTTP ${res.status}`);
      }
    } catch (e) {
      setStatusMsg(`Cannot reach rover at ${roverIp} — connected to YieldVision WiFi?`);
    } finally {
      setConnecting(false);
    }
  };

  const pollStatus = async () => {
    try {
      const res = await fetch(roverUrl("/status"), { signal: AbortSignal.timeout(1000) });
      if (res.ok) {
        const data = await res.json();
        setRoverStatus(data);
      } else {
        handleLostConnection();
      }
    } catch {
      handleLostConnection();
    }
  };

  const handleLostConnection = () => {
    setConnected(false);
    setActiveDir("stop");
    setStatusMsg("Connection lost — rover out of range?");
    clearInterval(pollRef.current);
  };

  // ── Take sensor reading ───────────────────────────────────────────────────
  const triggerRead = async () => {
    if (!connected || readingPending) return;
    setReadingPending(true);
    setStatusMsg("Requesting sensor reading...");
    try {
      await fetch(roverUrl(`/cmd?dir=r`));
      // Rover takes ~15s to read all sensors — poll after delay
      await new Promise((r) => setTimeout(r, 15000));
      setStatusMsg("Reading complete ✓ — data saved to SD card");
      setLastReading(new Date().toLocaleTimeString());
    } catch {
      setStatusMsg("Read request failed");
    } finally {
      setReadingPending(false);
    }
  };

  // ── Keyboard events ───────────────────────────────────────────────────────
  useEffect(() => {
    const onKeyDown = (e) => {
      if (!connected) return;
      const dir = KEY_MAP[e.key];
      if (!dir) return;
      e.preventDefault();
      if (!heldKeys.current.has(e.key)) {
        heldKeys.current.add(e.key);
        drive(dir);
      }
    };

    const onKeyUp = (e) => {
      const dir = KEY_MAP[e.key];
      if (!dir) return;
      heldKeys.current.delete(e.key);
      if (heldKeys.current.size === 0) {
        drive("stop");
      }
    };

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup",   onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup",   onKeyUp);
    };
  }, [connected, drive]);

  // Cleanup poll on unmount
  useEffect(() => () => clearInterval(pollRef.current), []);

  // ── Helpers ───────────────────────────────────────────────────────────────
  const dirLabel = {
    forward:  "▲ FORWARD",
    backward: "▼ BACKWARD",
    left:     "◀ LEFT",
    right:    "▶ RIGHT",
    stop:     "■ STOPPED",
  };

  const dirColor = {
    forward: "#4ade80",  backward: "#4ade80",
    left: "#60a5fa",     right: "#60a5fa",
    stop: "#9ca3af",
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0f1117",
        color: "#e5e7eb",
        fontFamily: "system-ui, sans-serif",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "24px 16px",
      }}
    >
      {/* Header */}
      <h2 style={{ margin: "0 0 4px", fontSize: 20, fontWeight: 700, color: "#4ade80" }}>
        🛰 YieldVision — Rover Control
      </h2>
      <p style={{ margin: "0 0 20px", fontSize: 12, color: "#6b7280" }}>
        Connect to <strong style={{ color: "#d1d5db" }}>YieldVision</strong> WiFi first, then click Connect
      </p>

      {/* Connection row */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap", justifyContent: "center" }}>
        <input
          value={roverIp}
          onChange={(e) => setRoverIp(e.target.value)}
          disabled={connected}
          placeholder="192.168.4.1"
          style={{
            background: "#1f2937", border: "1px solid #374151",
            borderRadius: 6, padding: "6px 10px", color: "#e5e7eb",
            fontSize: 13, width: 130,
          }}
        />
        <button
          onClick={handleConnect}
          disabled={connecting}
          style={{
            background: connected ? "#7f1d1d" : "#14532d",
            border: "none", borderRadius: 6,
            padding: "7px 18px", color: "#fff",
            fontSize: 13, fontWeight: 600, cursor: "pointer",
          }}
        >
          {connecting ? "Connecting..." : connected ? "Disconnect" : "Connect"}
        </button>
      </div>

      {/* Status */}
      <p style={{ margin: "0 0 16px", fontSize: 12, color: connected ? "#4ade80" : "#9ca3af" }}>
        {statusMsg}
      </p>

      {/* Direction indicator */}
      <div
        style={{
          fontSize: 20, fontWeight: 700, marginBottom: 20,
          color: dirColor[activeDir] ?? "#9ca3af",
          letterSpacing: 1,
        }}
      >
        {dirLabel[activeDir] ?? "■ STOPPED"}
      </div>

      {/* D-pad */}
      <DPad
        onDrive={drive}
        connected={connected}
        activeDir={activeDir}
      />

      {/* Special move buttons */}
      <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
        <CtrlBtn
          label="Burnout (B)"
          color="#7c3aed"
          hoverColor="#6d28d9"
          disabled={!connected}
          onPress={() => drive("burnout")}
          onRelease={() => drive("stop")}
        />
        <CtrlBtn
          label="Circle (C)"
          color="#0369a1"
          hoverColor="#0284c7"
          disabled={!connected}
          onPress={() => drive("circle")}
          onRelease={() => drive("stop")}
        />
      </div>

      {/* Read button */}
      <button
        onClick={triggerRead}
        disabled={!connected || readingPending}
        style={{
          marginTop: 20,
          background: readingPending ? "#374151" : "#78350f",
          border: "none", borderRadius: 8,
          padding: "10px 32px",
          color: readingPending ? "#9ca3af" : "#fcd34d",
          fontSize: 14, fontWeight: 600, cursor: connected && !readingPending ? "pointer" : "not-allowed",
          width: "100%", maxWidth: 300,
        }}
      >
        {readingPending ? "⏳ Reading sensors..." : "📡  Take Sensor Reading"}
      </button>

      {lastReading && (
        <p style={{ margin: "8px 0 0", fontSize: 11, color: "#6b7280" }}>
          Last reading at {lastReading} — check SD card / sync to server
        </p>
      )}

      {/* Rover status card */}
      {roverStatus && (
        <div
          style={{
            marginTop: 20, background: "#1f2937",
            borderRadius: 8, padding: "12px 16px",
            width: "100%", maxWidth: 300,
            fontSize: 12, color: "#9ca3af",
          }}
        >
          <div style={{ fontWeight: 600, color: "#d1d5db", marginBottom: 6 }}>Rover Status</div>
          <div>Network: <span style={{ color: "#e5e7eb" }}>{roverStatus.ssid}</span></div>
          <div>IP: <span style={{ color: "#e5e7eb" }}>{roverStatus.ip}</span></div>
          <div>Last cmd: <span style={{ color: "#fbbf24", fontWeight: 700 }}>
            {roverStatus.last_cmd === " " ? "STOP" : roverStatus.last_cmd?.toUpperCase()}
          </span></div>
          <div>Clients: <span style={{ color: "#e5e7eb" }}>{roverStatus.clients}</span></div>
        </div>
      )}

      {/* Keyboard hint */}
      <p style={{ marginTop: 20, fontSize: 11, color: "#4b5563", textAlign: "center" }}>
        WASD or Arrow keys to drive &nbsp;•&nbsp; Space to stop &nbsp;•&nbsp; Keys work while this window is focused
      </p>
    </div>
  );
}

// ── D-Pad component ───────────────────────────────────────────────────────────
function DPad({ onDrive, connected, activeDir }) {
  const btnStyle = (dir) => ({
    width: 80, height: 80,
    background: activeDir === dir ? "#166534" : "#1f2937",
    border: `2px solid ${activeDir === dir ? "#4ade80" : "#374151"}`,
    borderRadius: 10,
    color: "#e5e7eb", fontSize: 24,
    cursor: connected ? "pointer" : "not-allowed",
    opacity: connected ? 1 : 0.4,
    transition: "background 0.1s, border-color 0.1s",
    userSelect: "none",
  });

  const stopStyle = {
    ...btnStyle("stop"),
    background: activeDir === "stop" ? "#7f1d1d" : "#1f2937",
    border: `2px solid ${activeDir === "stop" ? "#f87171" : "#374151"}`,
    fontSize: 18, fontWeight: 700,
  };

  const bind = (dir) => ({
    onMouseDown:  () => connected && onDrive(dir),
    onMouseUp:    () => connected && onDrive("stop"),
    onMouseLeave: () => connected && activeDir === dir && onDrive("stop"),
    onTouchStart: (e) => { e.preventDefault(); connected && onDrive(dir); },
    onTouchEnd:   () => connected && onDrive("stop"),
  });

  return (
    <div style={{ display: "grid", gridTemplateColumns: "80px 80px 80px", gap: 8 }}>
      {/* Row 1 */}
      <div />
      <button style={btnStyle("forward")} {...bind("forward")}>▲</button>
      <div />
      {/* Row 2 */}
      <button style={btnStyle("left")}  {...bind("left")}>◀</button>
      <button style={stopStyle}         onClick={() => connected && onDrive("stop")}>■</button>
      <button style={btnStyle("right")} {...bind("right")}>▶</button>
      {/* Row 3 */}
      <div />
      <button style={btnStyle("backward")} {...bind("backward")}>▼</button>
      <div />
    </div>
  );
}

// ── Generic control button (hold to activate) ─────────────────────────────────
function CtrlBtn({ label, color, hoverColor, disabled, onPress, onRelease }) {
  const [held, setHeld] = useState(false);

  return (
    <button
      disabled={disabled}
      onMouseDown={() => { if (!disabled) { setHeld(true);  onPress(); }}}
      onMouseUp={()  => { setHeld(false); onRelease(); }}
      onMouseLeave={() => { if (held) { setHeld(false); onRelease(); }}}
      onTouchStart={(e) => { e.preventDefault(); if (!disabled) { setHeld(true); onPress(); }}}
      onTouchEnd={() => { setHeld(false); onRelease(); }}
      style={{
        background: held ? hoverColor : color,
        border: "none", borderRadius: 8,
        padding: "8px 16px", color: "#fff",
        fontSize: 12, fontWeight: 600,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.4 : 1,
        transition: "background 0.1s",
      }}
    >
      {label}
    </button>
  );
}
