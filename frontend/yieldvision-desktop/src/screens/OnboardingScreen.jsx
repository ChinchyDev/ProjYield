import { useState } from "react";
import Icon from "@mdi/react";
import {
  mdiLeaf,
  mdiArrowRight,
  mdiArrowLeft,
  mdiSprout,
  mdiAccount,
  mdiRobotMower,
  mdiMapMarkerOutline,
  mdiCheckCircle,
  mdiAlertCircleOutline,
  mdiReload,
} from "@mdi/js";
import { registerFarm, getFarmSummary } from "../api";

export default function OnboardingScreen({ onLogin, t }) {
  const [mode,  setMode]  = useState("welcome");   // welcome | register | signin
  const [step,  setStep]  = useState(0);            // register step index

  // Form fields
  const [farmName,   setFarmName]   = useState("");
  const [ownerName,  setOwnerName]  = useState("");
  const [location,   setLocation]   = useState("");
  const [roverId,    setRoverId]    = useState("");
  const [farmId,     setFarmId]     = useState("");  // sign-in field

  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState("");
  const [result,  setResult]  = useState(null);

  // ── Helpers ─────────────────────────────────────────────────────────────
  function inputStyle(focused = false) {
    return {
      width:        "100%",
      padding:      "12px 14px",
      borderRadius: "12px",
      background:   t.bgInput,
      border:       `1.5px solid ${focused ? t.accentBorder : t.border}`,
      color:        t.textPrimary,
      fontSize:     "0.9rem",
      outline:      "none",
      transition:   "border-color 0.15s",
    };
  }

  function btnPrimary(disabled = false) {
    return {
      display:       "flex",
      alignItems:    "center",
      justifyContent:"center",
      gap:           "8px",
      width:         "100%",
      padding:       "13px 20px",
      borderRadius:  "12px",
      background:    disabled ? t.panelLight : t.accent,
      color:         disabled ? t.textMuted : t.accentText,
      fontWeight:    700,
      fontSize:      "0.92rem",
      border:        "none",
      cursor:        disabled ? "not-allowed" : "pointer",
      transition:    "opacity 0.15s",
      opacity:       disabled ? 0.6 : 1,
    };
  }

  function btnGhost() {
    return {
      display:       "flex",
      alignItems:    "center",
      justifyContent:"center",
      gap:           "6px",
      padding:       "11px 20px",
      borderRadius:  "12px",
      background:    "transparent",
      color:         t.textSub,
      fontWeight:    600,
      fontSize:      "0.88rem",
      border:        `1.5px solid ${t.border}`,
      cursor:        "pointer",
      transition:    "opacity 0.15s",
    };
  }

  // ── Register submit ───────────────────────────────────────────────────────
  async function handleRegister() {
    if (!farmName.trim() || !ownerName.trim()) {
      setError("Please fill in farm name and your name.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await registerFarm({
        farm_name:   farmName.trim(),
        owner_name:  ownerName.trim(),
        location:    location.trim() || null,
        rover_id:    roverId.trim()  || null,
      });
      setResult(data);
      setStep(2);
    } catch (e) {
      setError("Could not register farm. Check your connection and try again.");
    } finally {
      setLoading(false);
    }
  }

  // ── Sign in submit ────────────────────────────────────────────────────────
  async function handleSignIn() {
    if (!farmId.trim()) { setError("Enter your Farm ID."); return; }
    setLoading(true);
    setError("");
    try {
      const data = await getFarmSummary(farmId.trim());
      onLogin({
        farm_id:    farmId.trim(),
        farm_name:  data.farm_name || "My Farm",
        owner_name: data.owner_name || "Farmer",
      });
    } catch {
      setError("Farm not found. Check your Farm ID and try again.");
    } finally {
      setLoading(false);
    }
  }

  // ── Done screen ───────────────────────────────────────────────────────────
  function handleEnterFarm() {
    if (!result) return;
    onLogin({
      farm_id:    result.farm_id,
      farm_name:  result.farm_name  || farmName,
      owner_name: result.owner_name || ownerName,
    });
  }

  // ── Layout wrapper ────────────────────────────────────────────────────────
  return (
    <div
      className="flex items-center justify-center h-screen w-screen"
      style={{ background: t.bg }}
    >
      <div
        className="flex flex-col rounded-3xl overflow-hidden shadow-2xl"
        style={{
          width:      "420px",
          background: t.bgCard,
          border:     `1px solid ${t.border}`,
          backdropFilter: "blur(20px)",
        }}
      >
        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div
          className="flex flex-col items-center gap-3 py-8 px-8"
          style={{ background: t.panel }}
        >
          <div
            className="flex items-center justify-center rounded-2xl"
            style={{ width: "52px", height: "52px", background: "rgba(255,255,255,0.12)" }}
          >
            <Icon path={mdiLeaf} size={1.3} color="rgba(255,255,255,0.85)" />
          </div>
          <div className="text-center">
            <div className="font-bold text-lg" style={{ color: "#fff" }}>YieldVision</div>
            <div className="text-sm mt-0.5" style={{ color: t.panelMuted }}>
              Precision farming for every farmer
            </div>
          </div>
        </div>

        {/* ── Body ───────────────────────────────────────────────────────── */}
        <div className="p-7 flex flex-col gap-4">

          {/* ── Welcome ── */}
          {mode === "welcome" && (
            <>
              <h2 className="text-lg font-bold text-center" style={{ color: t.textPrimary }}>
                Welcome
              </h2>
              <p className="text-sm text-center" style={{ color: t.textSub }}>
                Set up your farm to get precision farming recommendations from your rover.
              </p>

              <button style={btnPrimary()} onClick={() => { setMode("register"); setStep(0); }}>
                Register new farm
                <Icon path={mdiArrowRight} size={0.65} />
              </button>

              <button style={btnGhost()} onClick={() => setMode("signin")}>
                Sign in with existing Farm ID
              </button>
            </>
          )}

          {/* ── Register — Step 0: Details ── */}
          {mode === "register" && step === 0 && (
            <>
              <div className="flex items-center gap-2 mb-1">
                <Icon path={mdiSprout} size={0.75} color={t.accent} />
                <span className="font-bold text-base" style={{ color: t.textPrimary }}>
                  Your Farm
                </span>
                <span className="ml-auto text-xs" style={{ color: t.textMuted }}>Step 1 of 2</span>
              </div>

              <FieldRow icon={mdiSprout} label="Farm name" placeholder="e.g. Kamau's Farm">
                <input
                  value={farmName}
                  onChange={e => setFarmName(e.target.value)}
                  placeholder="e.g. Kamau's Farm"
                  style={inputStyle()}
                />
              </FieldRow>

              <FieldRow icon={mdiAccount} label="Your name" placeholder="e.g. John Kamau">
                <input
                  value={ownerName}
                  onChange={e => setOwnerName(e.target.value)}
                  placeholder="e.g. John Kamau"
                  style={inputStyle()}
                />
              </FieldRow>

              <FieldRow icon={mdiMapMarkerOutline} label="Location (optional)" placeholder="e.g. Nakuru, Kenya">
                <input
                  value={location}
                  onChange={e => setLocation(e.target.value)}
                  placeholder="e.g. Nakuru, Kenya"
                  style={inputStyle()}
                />
              </FieldRow>

              {error && <ErrorRow message={error} t={t} />}

              <button
                style={btnPrimary(!farmName.trim() || !ownerName.trim())}
                disabled={!farmName.trim() || !ownerName.trim()}
                onClick={() => { setError(""); setStep(1); }}
              >
                Continue
                <Icon path={mdiArrowRight} size={0.65} />
              </button>

              <button style={btnGhost()} onClick={() => setMode("welcome")}>
                <Icon path={mdiArrowLeft} size={0.6} />
                Back
              </button>
            </>
          )}

          {/* ── Register — Step 1: Rover ID ── */}
          {mode === "register" && step === 1 && (
            <>
              <div className="flex items-center gap-2 mb-1">
                <Icon path={mdiRobotMower} size={0.75} color={t.accent} />
                <span className="font-bold text-base" style={{ color: t.textPrimary }}>
                  Link Your Rover
                </span>
                <span className="ml-auto text-xs" style={{ color: t.textMuted }}>Step 2 of 2</span>
              </div>

              <p className="text-sm" style={{ color: t.textSub }}>
                Find the Rover ID on the sticker on your rover device. You can skip this and add it later.
              </p>

              <FieldRow icon={mdiRobotMower} label="Rover ID" placeholder="e.g. RVR-2024-001A">
                <input
                  value={roverId}
                  onChange={e => setRoverId(e.target.value)}
                  placeholder="e.g. RVR-2024-001A"
                  style={inputStyle()}
                />
              </FieldRow>

              {error && <ErrorRow message={error} t={t} />}

              <button
                style={btnPrimary(loading)}
                disabled={loading}
                onClick={handleRegister}
              >
                {loading ? "Registering…" : "Register Farm"}
                {!loading && <Icon path={mdiArrowRight} size={0.65} />}
              </button>

              <button style={btnGhost()} onClick={() => setStep(0)}>
                <Icon path={mdiArrowLeft} size={0.6} />
                Back
              </button>
            </>
          )}

          {/* ── Done ── */}
          {mode === "register" && step === 2 && result && (
            <>
              <div className="flex flex-col items-center gap-3 py-2">
                <Icon path={mdiCheckCircle} size={2} color={t.accent} />
                <h2 className="font-bold text-lg text-center" style={{ color: t.textPrimary }}>
                  Farm registered!
                </h2>
                <p className="text-sm text-center" style={{ color: t.textSub }}>
                  Your Farm ID is:
                </p>
                <div
                  className="rounded-xl px-4 py-2 font-mono text-sm font-bold"
                  style={{ background: t.accentMuted, color: t.accent }}
                >
                  {result.farm_id}
                </div>
                <p className="text-xs text-center" style={{ color: t.textMuted }}>
                  Save this ID — you'll need it to sign in from another device.
                </p>
              </div>

              <button style={btnPrimary()} onClick={handleEnterFarm}>
                Enter my farm
                <Icon path={mdiArrowRight} size={0.65} />
              </button>
            </>
          )}

          {/* ── Sign in ── */}
          {mode === "signin" && (
            <>
              <div className="flex items-center gap-2 mb-1">
                <Icon path={mdiSprout} size={0.75} color={t.accent} />
                <span className="font-bold text-base" style={{ color: t.textPrimary }}>
                  Sign In
                </span>
              </div>

              <p className="text-sm" style={{ color: t.textSub }}>
                Enter your Farm ID to access your farm data.
              </p>

              <FieldRow icon={mdiSprout} label="Farm ID" placeholder="e.g. farm_abc123">
                <input
                  value={farmId}
                  onChange={e => setFarmId(e.target.value)}
                  placeholder="e.g. farm_abc123"
                  style={inputStyle()}
                />
              </FieldRow>

              {error && <ErrorRow message={error} t={t} />}

              <button
                style={btnPrimary(!farmId.trim() || loading)}
                disabled={!farmId.trim() || loading}
                onClick={handleSignIn}
              >
                {loading
                  ? <><Icon path={mdiReload} size={0.65} /> Connecting…</>
                  : <>Sign in <Icon path={mdiArrowRight} size={0.65} /></>
                }
              </button>

              <button style={btnGhost()} onClick={() => { setMode("welcome"); setError(""); }}>
                <Icon path={mdiArrowLeft} size={0.6} />
                Back
              </button>
            </>
          )}

        </div>
      </div>
    </div>
  );
}

function FieldRow({ icon, label, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-semibold" style={{ color: "rgba(100,120,110,0.8)" }}>
        {label}
      </label>
      {children}
    </div>
  );
}

function ErrorRow({ message, t }) {
  return (
    <div
      className="flex items-center gap-2 rounded-xl px-3 py-2.5"
      style={{ background: t.redMuted }}
    >
      <Icon path={mdiAlertCircleOutline} size={0.65} color={t.red} />
      <span style={{ fontSize: "0.82rem", color: t.red }}>{message}</span>
    </div>
  );
}
