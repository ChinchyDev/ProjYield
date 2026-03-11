/**
 * RoverControlPanel.jsx
 *
 * Slide-down rover control HUD mounted between the header and main content.
 * Talks directly to the ESP8266 WiFi AP at 192.168.4.1 (the "YieldVision" hotspot).
 *
 * Control flow:
 *   React UI  ──HTTP GET──►  ESP8266 (192.168.4.1)  ──Serial.print──►  Mega Serial1  ──►  motors
 *
 * Commands forwarded: W/S/A/D (movement), B (burnout), C (circle), R (scan), SPACE (stop)
 */

import { useState, useEffect, useRef, useCallback } from "react";
import Icon from "@mdi/react";
import {
  mdiArrowUp,
  mdiArrowDown,
  mdiArrowLeft,
  mdiArrowRight,
  mdiStop,
  mdiWifi,
  mdiWifiOff,
  mdiRefresh,
  mdiFlash,
  mdiSync,
  mdiMagnify,
  mdiRobotMower,
  mdiClose,
} from "@mdi/js";
import { roverCommand, roverStatus } from "../api";

const CMD_LABELS = {
  W: "Forward", S: "Backward", A: "Left", D: "Right",
  " ": "Stop", R: "Scan", B: "Burnout", C: "Circle",
};

export default function RoverControlPanel({ t, onClose }) {
  const [roverIp,    setRoverIp]    = useState("192.168.4.1");
  const [editIp,     setEditIp]     = useState(false);
  const [ipDraft,    setIpDraft]    = useState("192.168.4.1");
  const [connected,  setConnected]  = useState(false);
  const [roverInfo,  setRoverInfo]  = useState(null);
  const [lastCmd,    setLastCmd]    = useState(null);
  const [lastTs,     setLastTs]     = useState(null);
  const [keysHeld,   setKeysHeld]   = useState(new Set());
  const [joyPos,     setJoyPos]     = useState({ x: 0, y: 0 });
  const [cmdAge,     setCmdAge]     = useState(null);

  const joyRef      = useRef(null);
  const dragging    = useRef(false);
  const joyCmd      = useRef(null);

  // ── Poll ESP8266 /status every 3 s ────────────────────────────────────────
  const poll = useCallback(async () => {
    try {
      const data = await roverStatus(roverIp);
      setConnected(true);
      setRoverInfo(data);
    } catch {
      setConnected(false);
      setRoverInfo(null);
    }
  }, [roverIp]);

  useEffect(() => {
    poll();
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, [poll]);

  // ── Update "Xs ago" display every second ──────────────────────────────────
  useEffect(() => {
    const id = setInterval(() => {
      if (lastTs) setCmdAge(Math.round((Date.now() - lastTs) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [lastTs]);

  // ── Send a single command character ───────────────────────────────────────
  const send = useCallback(async (dir) => {
    setLastCmd(dir);
    setLastTs(Date.now());
    setCmdAge(0);
    await roverCommand(dir, roverIp);
  }, [roverIp]);

  // ── Keyboard capture (WASD + arrows) ──────────────────────────────────────
  useEffect(() => {
    const KEY_MAP = {
      w: "W", W: "W", ArrowUp:    "W",
      s: "S", S: "S", ArrowDown:  "S",
      a: "A", A: "A", ArrowLeft:  "A",
      d: "D", D: "D", ArrowRight: "D",
    };
    const held = new Set();

    function onDown(e) {
      const cmd = KEY_MAP[e.key];
      if (!cmd) return;
      e.preventDefault();
      if (held.has(cmd)) return;
      held.add(cmd);
      setKeysHeld(new Set(held));
      send(cmd);
    }
    function onUp(e) {
      const cmd = KEY_MAP[e.key];
      if (!cmd) return;
      e.preventDefault();
      held.delete(cmd);
      setKeysHeld(new Set(held));
      if (held.size === 0) send(" ");
    }

    window.addEventListener("keydown", onDown);
    window.addEventListener("keyup",   onUp);
    return () => {
      window.removeEventListener("keydown", onDown);
      window.removeEventListener("keyup",   onUp);
      // Stop on unmount if any keys were held
      if (held.size > 0) roverCommand(" ", roverIp).catch(() => {});
    };
  }, [send, roverIp]);

  // ── Virtual joystick helpers ───────────────────────────────────────────────
  function getJoystickCommand(dx, dy, maxR) {
    const thresh = maxR * 0.30;
    if (Math.sqrt(dx * dx + dy * dy) < thresh) return " ";
    return Math.abs(dy) >= Math.abs(dx) ? (dy < 0 ? "W" : "S") : (dx < 0 ? "A" : "D");
  }

  function handleJoyMove(clientX, clientY) {
    if (!dragging.current || !joyRef.current) return;
    const rect = joyRef.current.getBoundingClientRect();
    const cx = rect.left + rect.width  / 2;
    const cy = rect.top  + rect.height / 2;
    const dx = clientX - cx;
    const dy = clientY - cy;
    const maxR = rect.width / 2 - 14;
    const dist  = Math.sqrt(dx * dx + dy * dy);
    const scale = dist > maxR ? maxR / dist : 1;
    const nx = dx * scale;
    const ny = dy * scale;
    setJoyPos({ x: nx, y: ny });

    const newCmd = getJoystickCommand(dx, dy, maxR);
    if (newCmd !== joyCmd.current) {
      joyCmd.current = newCmd;
      send(newCmd);
    }
  }

  function startJoy(e) {
    dragging.current = true;
    const pt = e.touches ? e.touches[0] : e;
    handleJoyMove(pt.clientX, pt.clientY);
  }
  function moveJoy(e) {
    if (!dragging.current) return;
    const pt = e.touches ? e.touches[0] : e;
    handleJoyMove(pt.clientX, pt.clientY);
  }
  function endJoy() {
    if (!dragging.current) return;
    dragging.current = false;
    joyCmd.current = null;
    setJoyPos({ x: 0, y: 0 });
    send(" ");
  }

  // ── D-pad buttons ──────────────────────────────────────────────────────────
  const DPAD = [
    { cmd: "W", icon: mdiArrowUp,    col: 2, row: 1 },
    { cmd: "A", icon: mdiArrowLeft,  col: 1, row: 2 },
    { cmd: " ", icon: mdiStop,       col: 2, row: 2 },
    { cmd: "D", icon: mdiArrowRight, col: 3, row: 2 },
    { cmd: "S", icon: mdiArrowDown,  col: 2, row: 3 },
  ];

  const isActive = (cmd) => cmd !== " " && keysHeld.has(cmd);

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        background:   t.bgCard,
        borderBottom: `1px solid ${t.border}`,
        boxShadow:    "0 6px 28px rgba(0,0,0,0.16)",
        padding:      "10px 20px 14px",
        display:      "flex",
        alignItems:   "center",
        gap:          24,
        flexWrap:     "wrap",
        userSelect:   "none",
      }}
      onMouseMove={moveJoy}
      onMouseUp={endJoy}
      onMouseLeave={endJoy}
    >
      {/* ── Header + connection info ─────────────────────────────────────── */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 180, flex: "0 0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Icon path={mdiRobotMower} size={0.72} color={connected ? t.accent : t.textMuted} />
          <span style={{ fontSize: "0.8rem", fontWeight: 700, color: t.textPrimary, letterSpacing: "0.04em" }}>
            ROVER CONTROL
          </span>
          {/* Live indicator */}
          <div style={{
            width: 7, height: 7, borderRadius: "50%",
            background: connected ? t.green : t.red,
            boxShadow: connected ? `0 0 5px ${t.green}` : "none",
            flexShrink: 0,
          }} />
          <span style={{ fontSize: "0.68rem", fontWeight: 600, color: connected ? t.green : t.red }}>
            {connected ? "Connected" : "No signal"}
          </span>
          <button
            onClick={onClose}
            className="no-focus-ring"
            style={{
              marginLeft: "auto", background: "none", border: "none",
              cursor: "pointer", padding: 2, borderRadius: 6,
              display: "flex", alignItems: "center",
            }}
          >
            <Icon path={mdiClose} size={0.6} color={t.textMuted} />
          </button>
        </div>

        {/* IP config */}
        {editIp ? (
          <div style={{ display: "flex", gap: 5 }}>
            <input
              value={ipDraft}
              onChange={e => setIpDraft(e.target.value)}
              onKeyDown={e => {
                if (e.key === "Enter")  { setRoverIp(ipDraft); setEditIp(false); }
                if (e.key === "Escape") { setEditIp(false); }
                e.stopPropagation();
              }}
              style={{
                flex: 1, fontSize: "0.72rem", padding: "3px 8px",
                borderRadius: 8, border: `1px solid ${t.accent}`,
                background: t.bg, color: t.textPrimary, outline: "none",
              }}
              placeholder="192.168.4.1"
              autoFocus
            />
            <button
              onClick={() => { setRoverIp(ipDraft); setEditIp(false); }}
              className="no-focus-ring"
              style={{
                fontSize: "0.7rem", padding: "3px 10px", borderRadius: 8,
                background: t.accent, color: t.accentText, border: "none", cursor: "pointer",
              }}
            >
              Set
            </button>
          </div>
        ) : (
          <button
            onClick={() => { setIpDraft(roverIp); setEditIp(true); }}
            className="no-focus-ring"
            style={{
              display: "flex", alignItems: "center", gap: 6,
              background: "none", border: `1px solid ${t.border}`,
              borderRadius: 8, padding: "3px 8px", cursor: "pointer",
              color: t.textSub, fontSize: "0.7rem",
            }}
          >
            <Icon path={connected ? mdiWifi : mdiWifiOff} size={0.42}
              color={connected ? t.green : t.textMuted} />
            <span>{roverIp}</span>
            {roverInfo?.clients != null && (
              <span style={{ color: t.textMuted }}>
                · {roverInfo.clients} client{roverInfo.clients !== 1 ? "s" : ""}
              </span>
            )}
          </button>
        )}

        {/* Last command / keyboard hint */}
        <div>
          {lastCmd ? (
            <p style={{ margin: 0, fontSize: "0.63rem", color: t.textMuted }}>
              Last:&nbsp;
              <strong style={{ color: t.textSub }}>{CMD_LABELS[lastCmd] ?? lastCmd}</strong>
              {cmdAge != null && <span> ({cmdAge}s ago)</span>}
            </p>
          ) : (
            <p style={{ margin: 0, fontSize: "0.63rem", color: t.textMuted }}>
              Hold WASD or arrow keys · click D-pad · drag joystick
            </p>
          )}
          {roverInfo?.mock && (
            <p style={{ margin: "2px 0 0", fontSize: "0.6rem", color: t.amber }}>
              ⚠ Mock mode — no real rover connected
            </p>
          )}
        </div>
      </div>

      {/* ── D-Pad ─────────────────────────────────────────────────────────── */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(3, 40px)",
        gridTemplateRows:    "repeat(3, 40px)",
        gap: 3,
        flexShrink: 0,
      }}>
        {DPAD.map(btn => {
          const active = isActive(btn.cmd);
          return (
            <button
              key={btn.cmd}
              className="no-focus-ring"
              style={{
                gridColumn: btn.col, gridRow: btn.row,
                background: active ? t.accent : t.panelLight,
                color:      active ? t.accentText : t.textSub,
                border:     `1.5px solid ${active ? t.accent : t.border}`,
                borderRadius: 10, cursor: "pointer",
                display: "flex", alignItems: "center", justifyContent: "center",
                transition: "background 0.08s, border-color 0.08s",
              }}
              onMouseDown={() => send(btn.cmd)}
              onMouseUp={() => { if (btn.cmd !== " ") send(" "); }}
              onMouseLeave={() => { if (btn.cmd !== " " && active) send(" "); }}
            >
              <Icon path={btn.icon} size={0.6} color={active ? t.accentText : t.textSub} />
            </button>
          );
        })}
      </div>

      {/* ── Analog Joystick ───────────────────────────────────────────────── */}
      <div
        ref={joyRef}
        style={{
          width: 96, height: 96, borderRadius: "50%",
          background: t.panelLight,
          border: `2px solid ${t.border}`,
          position: "relative", flexShrink: 0, cursor: "grab",
          touchAction: "none",
        }}
        onMouseDown={startJoy}
        onTouchStart={startJoy}
        onTouchMove={moveJoy}
        onTouchEnd={endJoy}
      >
        {/* Cross-hair */}
        <div style={{
          position: "absolute", top: "50%", left: "50%",
          transform: "translate(-50%,-50%)",
          width: 1, height: 20, background: t.border,
        }} />
        <div style={{
          position: "absolute", top: "50%", left: "50%",
          transform: "translate(-50%,-50%)",
          width: 20, height: 1, background: t.border,
        }} />
        {/* Nub */}
        <div style={{
          position: "absolute",
          top:  `calc(50% + ${joyPos.y}px)`,
          left: `calc(50% + ${joyPos.x}px)`,
          transform: "translate(-50%,-50%)",
          width: 30, height: 30, borderRadius: "50%",
          background: (joyPos.x !== 0 || joyPos.y !== 0) ? t.accent : t.panel,
          border: `2.5px solid ${t.accent}`,
          boxShadow: (joyPos.x !== 0 || joyPos.y !== 0) ? `0 0 10px ${t.accent}66` : "none",
          transition: dragging.current ? "none" : "all 0.15s cubic-bezier(.34,1.56,.64,1)",
        }} />
      </div>

      {/* ── Special commands ──────────────────────────────────────────────── */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6, flexShrink: 0 }}>
        <p style={{ margin: 0, fontSize: "0.6rem", color: t.textMuted, fontWeight: 700, letterSpacing: "0.06em" }}>
          SPECIAL
        </p>
        {[
          { cmd: "R", label: "Scan",    icon: mdiMagnify,  col: t.accent },
          { cmd: "B", label: "Burnout", icon: mdiFlash,    col: t.amber  },
          { cmd: "C", label: "Circle",  icon: mdiSync,     col: t.green  },
        ].map(btn => (
          <button
            key={btn.cmd}
            onMouseDown={() => send(btn.cmd)}
            className="no-focus-ring"
            style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "5px 10px", borderRadius: 9,
              background: btn.col + "1a",
              border: `1.5px solid ${btn.col}40`,
              color: btn.col, cursor: "pointer",
              fontSize: "0.72rem", fontWeight: 600,
            }}
          >
            <Icon path={btn.icon} size={0.5} color={btn.col} />
            {btn.label}
            <span style={{ opacity: 0.55, fontSize: "0.6rem" }}>({btn.cmd})</span>
          </button>
        ))}
        <button
          onClick={poll}
          className="no-focus-ring"
          style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "5px 10px", borderRadius: 9,
            background: t.panelLight, border: `1.5px solid ${t.border}`,
            color: t.textSub, cursor: "pointer",
            fontSize: "0.72rem", fontWeight: 600,
          }}
        >
          <Icon path={mdiRefresh} size={0.5} color={t.textSub} />
          Reconnect
        </button>
      </div>

      {/* ── Connection guide ──────────────────────────────────────────────── */}
      <div style={{
        marginLeft: "auto",
        fontSize: "0.63rem", color: t.textMuted, lineHeight: 1.6,
        borderLeft: `2px solid ${t.border}`, paddingLeft: 14,
      }}>
        <p style={{ margin: 0, fontWeight: 700, color: t.textSub }}>Connection guide</p>
        <p style={{ margin: "2px 0 0" }}>1. Power on rover</p>
        <p style={{ margin: 0 }}>2. Connect laptop to <strong style={{ color: t.textSub }}>YieldVision</strong> WiFi</p>
        <p style={{ margin: 0 }}>3. Default IP: <strong style={{ color: t.accent }}>192.168.4.1</strong></p>
        <p style={{ margin: 0 }}>4. Password: <strong style={{ color: t.textSub }}>rover1234</strong></p>
      </div>
    </div>
  );
}
