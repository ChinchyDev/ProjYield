/**
 * Spinner — brand-aligned growing seedling loader
 */
export default function Spinner({ size = 32, t }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12">
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        style={{
          animation:   "spin 1.1s linear infinite",
          color:       t?.accent || "#6B8E4E",
        }}
        aria-hidden="true"
      >
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        <circle
          cx="12"
          cy="12"
          r="9"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeDasharray="42 14"
          strokeLinecap="round"
        />
      </svg>
      <span style={{ fontSize: "0.8rem", color: t?.textSub || "#888", fontWeight: 500 }}>
        Loading…
      </span>
    </div>
  );
}
