import Icon from "@mdi/react";
import {
  mdiHome,
  mdiSprout,
  mdiClipboardCheckOutline,
  mdiBellOutline,
} from "@mdi/js";

const TABS = [
  { id: "home",   icon: mdiHome,                   label: "Home"  },
  { id: "farm",   icon: mdiSprout,                  label: "Farm"  },
  { id: "tasks",  icon: mdiClipboardCheckOutline,   label: "Tasks" },
  { id: "alerts", icon: mdiBellOutline,              label: "Alerts"},
];

export default function BottomNav({ active, onChange, alertCount = 0, t }) {
  return (
    /* Floating pill — fixed, horizontally centred, above page content */
    <nav
      className="fixed bottom-5 left-1/2 z-50 flex items-center gap-1 px-3 py-2.5 glass"
      style={{
        transform:            "translateX(-50%)",
        background:           t.navBg,
        border:               `1px solid ${t.navBorder}`,
        borderRadius:         "40px",
        boxShadow:            "0 8px 32px rgba(0,0,0,0.32), 0 2px 8px rgba(0,0,0,0.18)",
      }}
      aria-label="Main navigation"
    >
      {TABS.map(({ id, icon, label }) => {
        const isActive = active === id;
        const showBadge = id === "alerts" && alertCount > 0;

        return (
          <button
            key={id}
            onClick={() => onChange(id)}
            aria-label={label}
            aria-current={isActive ? "page" : undefined}
            className="relative flex items-center justify-center rounded-full transition-all duration-200 no-focus-ring"
            style={{
              width:      "52px",
              height:     "44px",
              background: isActive ? "rgba(178,197,178,0.12)" : "transparent",
            }}
          >
            {/* Active background glow */}
            {isActive && (
              <span
                className="absolute inset-0 rounded-full"
                style={{
                  boxShadow: `0 0 14px ${t.navGlow}`,
                  borderRadius: "50%",
                  pointerEvents: "none",
                }}
              />
            )}

            {/* Icon */}
            <span
              style={{
                color:  isActive ? t.navActive : t.navIcon,
                filter: isActive ? `drop-shadow(0 0 6px ${t.navGlow})` : "none",
                transition: "color 0.18s ease, filter 0.18s ease",
                display: "flex",
                alignItems: "center",
              }}
            >
              <Icon path={icon} size={0.82} />
            </span>

            {/* Alert badge */}
            {showBadge && (
              <span
                className="absolute top-1.5 right-1.5 flex items-center justify-center text-white font-bold rounded-full"
                style={{
                  background:  t.red,
                  fontSize:    "9px",
                  minWidth:    "16px",
                  height:      "16px",
                  padding:     "0 4px",
                  lineHeight:  1,
                }}
              >
                {alertCount > 9 ? "9+" : alertCount}
              </span>
            )}
          </button>
        );
      })}
    </nav>
  );
}
