"""
YieldVision Precision Farming — Desktop App
HCI-grounded design for Kenyan smallholder farmers.
Principles: Norman UCD · Hick's Law · Fitts's Law · Nielsen Heuristics · Progressive Disclosure
Hub-and-Spoke navigation, plain farming language, colour-coded status, large touch targets.
"""

import tkinter as tk
from tkinter import messagebox
import requests
import threading
from datetime import datetime

# ── Colour palette (UI Plan §2) ────────────────────────────────────────────
C = {
    "bg":       "#F7F4EE",   # off-white cream  (outdoor-legible)
    "soil":     "#1A1208",   # deep soil brown  (primary text)
    "green":    "#2D6A4F",   # earth green      (brand / positive action)
    "green_lt": "#52B788",   # leaf green       (healthy status)
    "amber":    "#E9A826",   # warm amber       (attention / harvest)
    "orange":   "#F4A261",   # warm orange      (warning card bg)
    "red":      "#D62828",   # strong red       (critical alert)
    "blue":     "#3A86FF",   # sky blue         (interactive / water)
    "slate":    "#6C8EBF",   # slate blue       (neutral info)
    "white":    "#FFFFFF",
    "card":     "#FFFFFF",
    "border":   "#DDD8CE",
    "nav_bg":   "#2D6A4F",
    "nav_sel":  "#E9A826",
}

# ── Typography (Hick's Law: large, unambiguous) ────────────────────────────
F = {
    "h1":   ("Segoe UI", 20, "bold"),
    "h2":   ("Segoe UI", 15, "bold"),
    "h3":   ("Segoe UI", 12, "bold"),
    "body": ("Segoe UI", 11),
    "sm":   ("Segoe UI", 10),
    "big":  ("Segoe UI", 30, "bold"),
    "nav":  ("Segoe UI", 12, "bold"),
    "mono": ("Courier New", 12, "bold"),
}

# ── Plain-language translators (Nielsen: match system to real world) ───────
def moisture_label(v):
    if v is None:   return "No sensor data", C["slate"]
    if v < 20:      return "💧 Soil is DRY — needs water today", C["red"]
    if v < 30:      return "💧 Soil is a bit dry", C["orange"]
    if v <= 50:     return "✅ Moisture is just right", C["green_lt"]
    return "🌊 Too much water in soil", C["slate"]

def nitrogen_label(v):
    if v is None:   return "No sensor data", C["slate"]
    if v < 40:      return "🌿 Nitrogen is LOW — needs fertiliser", C["red"]
    if v < 80:      return "🌿 Nitrogen is moderate", C["orange"]
    return "✅ Nitrogen is good", C["green_lt"]

def ph_label(v):
    if v is None:        return "No sensor data", C["slate"]
    if v < 5.5:          return "⚠️  Too acidic — add lime", C["red"]
    if v > 7.8:          return "⚠️  Too alkaline", C["orange"]
    if 6.0 <= v <= 7.0:  return "✅ Soil acidity is just right", C["green_lt"]
    return "🔸 Soil acidity is acceptable", C["amber"]

def zone_health(m, n, p):
    scores = []
    if m is not None: scores.append(0 if m < 20 else (1 if m < 30 else 2))
    if n is not None: scores.append(0 if n < 40 else (1 if n < 80 else 2))
    if p is not None: scores.append(0 if p < 5.5 or p > 7.8 else (1 if p < 6.0 or p > 7.0 else 2))
    if not scores:    return "unknown", C["slate"],    "❓ No data"
    avg = sum(scores) / len(scores)
    if avg < 0.7:  return "danger",  C["red"],       "❌ Needs action now"
    if avg < 1.5:  return "average", C["amber"],     "⚠️  Watch closely"
    return "good", C["green_lt"], "✅ Healthy"


# ═══════════════════════════════════════════════════════════════════════════
#  Reusable widgets
# ═══════════════════════════════════════════════════════════════════════════

class Card(tk.Frame):
    """White card with a subtle border."""
    def __init__(self, parent, bg=None, **kw):
        super().__init__(parent, bg=bg or C["card"],
                         highlightbackground=C["border"],
                         highlightthickness=1, relief="flat", **kw)

    def body(self, padx=16, pady=12):
        f = tk.Frame(self, bg=self["bg"])
        f.pack(fill="both", expand=True, padx=padx, pady=pady)
        return f


class BigBtn(tk.Button):
    """Fitts-compliant large action button (≥48 px target)."""
    def __init__(self, parent, text, command, bg=None, fg=None, **kw):
        super().__init__(parent, text=text, command=command,
                         font=F["h3"], bg=bg or C["green"],
                         fg=fg or C["white"],
                         activebackground=C["amber"],
                         activeforeground=C["soil"],
                         relief="flat", cursor="hand2",
                         padx=18, pady=12, **kw)


class NavItem(tk.Frame):
    """Left-sidebar nav button — full-width, large click target."""
    def __init__(self, parent, icon, label, on_click):
        super().__init__(parent, bg=C["nav_bg"], cursor="hand2")
        self._on = on_click
        self._selected = False
        self._lbl = tk.Label(self, text=f"  {icon}  {label}",
                             font=F["nav"], bg=C["nav_bg"],
                             fg=C["white"], anchor="w",
                             padx=10, pady=14)
        self._lbl.pack(fill="x")
        for w in (self, self._lbl):
            w.bind("<Button-1>", lambda _e: self._on())
            w.bind("<Enter>",    lambda _e: self._hover(True))
            w.bind("<Leave>",    lambda _e: self._hover(False))

    def select(self, on: bool):
        self._selected = on
        c  = C["nav_sel"] if on else C["nav_bg"]
        fg = C["soil"]    if on else C["white"]
        self.config(bg=c)
        self._lbl.config(bg=c, fg=fg)

    def _hover(self, on):
        if not self._selected:
            c = "#245a41" if on else C["nav_bg"]
            self.config(bg=c); self._lbl.config(bg=c)


# ═══════════════════════════════════════════════════════════════════════════
#  Main application
# ═══════════════════════════════════════════════════════════════════════════

NAV = [
    ("🏠", "Dashboard"),
    ("🌱", "My Farm"),
    ("📋", "Today's Tasks"),
    ("📊", "Reports"),
    ("🔔", "Alerts"),
]


class YieldVisionApp:
    """
    Hub-and-spoke desktop app.
    ≤5 nav items (Hick's Law). Plain language throughout.
    Colour always paired with icon + text (accessibility).
    """

    SERVER = "http://localhost:8000"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("YieldVision — Precision Farming")
        self.root.geometry("1280x800")
        self.root.minsize(960, 640)
        self.root.configure(bg=C["bg"])

        self._zones: list = []
        self._selected_zone: dict = {}
        self._tasks: list = []
        self._online = False
        self._nav_btns: list = []
        self._screens: dict = {}
        self._current = ""

        self._build()
        self._show("Dashboard")
        self._tick()
        self._refresh()

    # ── Layout ────────────────────────────────────────────────────────────

    def _build(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Sidebar
        self._sidebar = tk.Frame(self.root, bg=C["nav_bg"], width=210)
        self._sidebar.grid(row=0, column=0, sticky="ns")
        self._sidebar.pack_propagate(False)
        self._build_sidebar()

        # Main area
        right = tk.Frame(self.root, bg=C["bg"])
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        # Top bar
        self._topbar = tk.Frame(right, bg=C["green"], height=46)
        self._topbar.grid(row=0, column=0, sticky="ew")
        self._topbar.pack_propagate(False)
        self._screen_lbl = tk.Label(self._topbar, text="",
                                    font=F["h2"], bg=C["green"],
                                    fg=C["white"], padx=20, pady=8)
        self._screen_lbl.pack(side="left")
        self._time_lbl = tk.Label(self._topbar, text="",
                                  font=F["body"], bg=C["green"],
                                  fg=C["white"], padx=20)
        self._time_lbl.pack(side="right")

        # Content pane (stacked frames)
        self._pane = tk.Frame(right, bg=C["bg"])
        self._pane.grid(row=1, column=0, sticky="nsew")
        self._pane.columnconfigure(0, weight=1)
        self._pane.rowconfigure(0, weight=1)

        for _, name in NAV:
            f = tk.Frame(self._pane, bg=C["bg"])
            f.grid(row=0, column=0, sticky="nsew")
            f.columnconfigure(0, weight=1)
            f.rowconfigure(0, weight=1)
            self._screens[name] = f

        self._build_dashboard()
        self._build_farm()
        self._build_tasks()
        self._build_reports()
        self._build_alerts()

    def _build_sidebar(self):
        tk.Label(self._sidebar, text="🌾 YieldVision",
                 font=F["h2"], bg=C["nav_bg"], fg=C["amber"],
                 pady=20).pack(fill="x")
        tk.Frame(self._sidebar, bg="#1f4d38", height=1).pack(fill="x")

        for icon, label in NAV:
            btn = NavItem(self._sidebar, icon, label,
                          on_click=lambda l=label: self._show(l))
            btn.pack(fill="x")
            self._nav_btns.append((label, btn))

        tk.Frame(self._sidebar, bg=C["nav_bg"]).pack(fill="both", expand=True)
        tk.Frame(self._sidebar, bg="#1f4d38", height=1).pack(fill="x")

        self._conn_lbl = tk.Label(self._sidebar, text="● Offline",
                                  font=F["sm"], bg=C["nav_bg"],
                                  fg=C["red"], pady=8)
        self._conn_lbl.pack()

        tk.Button(self._sidebar, text="🔄  Sync Now",
                  font=F["nav"], bg=C["amber"], fg=C["soil"],
                  relief="flat", cursor="hand2", pady=10,
                  command=self._refresh).pack(fill="x", padx=10, pady=(0, 14))

    def _show(self, name: str):
        self._current = name
        self._screens[name].tkraise()
        self._screen_lbl.config(text=name)
        for label, btn in self._nav_btns:
            btn.select(label == name)

    # ── Clock tick ────────────────────────────────────────────────────────

    def _tick(self):
        self._time_lbl.config(text=datetime.now().strftime("%a %d %b  %H:%M"))
        self.root.after(10_000, self._tick)

    # ── Data refresh ──────────────────────────────────────────────────────

    def _refresh(self):
        threading.Thread(target=self._fetch_data, daemon=True).start()

    def _fetch_data(self):
        try:
            r = requests.get(f"{self.SERVER}/api/precision/zones/summary", timeout=5)
            if r.status_code == 200:
                self._zones = r.json().get("zones", [])
                self._online = True
                self.root.after(0, self._update_all_screens)
            else:
                self._online = False
        except Exception:
            self._online = False
        self.root.after(0, self._update_conn_label)

    def _update_conn_label(self):
        if self._online:
            self._conn_lbl.config(text="● Online", fg=C["green_lt"])
        else:
            self._conn_lbl.config(text="● Offline", fg=C["red"])

    def _update_all_screens(self):
        self._update_dashboard()
        self._populate_farm_list()
        self._populate_tasks()
        self._populate_alerts()

    # ═══════════════════════════════════════════════════════════════════════
    #  SCREEN 1 — Dashboard  (Hub)
    # ═══════════════════════════════════════════════════════════════════════

    def _build_dashboard(self):
        p = self._screens["Dashboard"]
        p.columnconfigure((0, 1, 2), weight=1)
        p.rowconfigure(2, weight=1)

        # Greeting row
        greet = tk.Frame(p, bg=C["bg"])
        greet.grid(row=0, column=0, columnspan=3, sticky="ew", padx=20, pady=(18, 4))
        self._greet_lbl = tk.Label(greet, text="Good morning 🌤️",
                                   font=F["h1"], bg=C["bg"], fg=C["soil"])
        self._greet_lbl.pack(side="left")
        tk.Label(greet, text=datetime.now().strftime("%A, %d %B %Y"),
                 font=F["body"], bg=C["bg"], fg=C["slate"]).pack(side="right")

        # Priority alert card (amber / red depending on urgency)
        self._priority_card = Card(p, bg=C["orange"])
        self._priority_card.grid(row=1, column=0, columnspan=3,
                                 sticky="ew", padx=20, pady=(8, 0))
        pc = self._priority_card.body(padx=20, pady=14)
        pc.columnconfigure(1, weight=1)
        tk.Label(pc, text="⚠️", font=("Segoe UI", 28),
                 bg=C["orange"]).grid(row=0, column=0, rowspan=2, padx=(0, 14))
        self._pri_title = tk.Label(pc, text="Loading your farm data…",
                                   font=F["h2"], bg=C["orange"], fg=C["soil"])
        self._pri_title.grid(row=0, column=1, sticky="w")
        self._pri_sub = tk.Label(pc, text="Please wait a moment.",
                                 font=F["body"], bg=C["orange"], fg=C["soil"])
        self._pri_sub.grid(row=1, column=1, sticky="w")
        self._pri_btn = BigBtn(pc, "Act Now →", self._act_on_priority,
                               bg=C["red"])
        self._pri_btn.grid(row=0, column=2, rowspan=2, padx=(14, 0))

        # Summary count cards
        row3 = tk.Frame(p, bg=C["bg"])
        row3.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=20, pady=12)
        row3.columnconfigure((0, 1, 2), weight=1)
        row3.rowconfigure(0, weight=1)

        self._count_lbls: dict = {}
        defs = [
            ("good",    "🟢 Healthy zones",   C["green_lt"]),
            ("average", "🟡 Need attention",  C["amber"]),
            ("danger",  "🔴 Urgent zones",    C["red"]),
        ]
        for col, (key, title, colour) in enumerate(defs):
            card = Card(row3)
            card.grid(row=0, column=col, sticky="nsew", padx=6)
            b = card.body(padx=20, pady=18)
            tk.Label(b, text=title, font=F["h3"],
                     bg=C["card"], fg=C["slate"]).pack(anchor="w")
            num = tk.Label(b, text="—", font=F["big"],
                           bg=C["card"], fg=colour)
            num.pack(anchor="w")
            tk.Label(b, text="zones", font=F["sm"],
                     bg=C["card"], fg=C["slate"]).pack(anchor="w")
            BigBtn(b, "See Farm →",
                   lambda k=key: (setattr(self, '_farm_filter', k), self._show("My Farm"), self._populate_farm_list()),
                   bg=C["green"]).pack(anchor="w", pady=(10, 0))
            self._count_lbls[key] = num

    def _update_dashboard(self):
        counts = {"good": 0, "average": 0, "danger": 0, "unknown": 0}
        worst_zone = None
        worst_score = 3

        for z in self._zones:
            m  = z.get("soil_moisture_20cm")
            n  = z.get("nitrogen_ppm")
            ph = z.get("ph_level")
            st, _, _ = zone_health(m, n, ph)
            counts[st] = counts.get(st, 0) + 1
            score = {"danger": 0, "average": 1, "good": 2, "unknown": 3}.get(st, 3)
            if score < worst_score:
                worst_score = score
                worst_zone  = z

        for key, lbl in self._count_lbls.items():
            lbl.config(text=str(counts.get(key, 0)))

        if worst_zone:
            lbl_name = worst_zone.get("zone_label", worst_zone.get("zone_id", "?"))
            m  = worst_zone.get("soil_moisture_20cm")
            n  = worst_zone.get("nitrogen_ppm")
            ph = worst_zone.get("ph_level")
            st, col, tag = zone_health(m, n, ph)

            if st == "danger":
                title = f"Zone {lbl_name} needs action today"
                if m is not None and m < 20:
                    sub = f"Soil is DRY ({m:.0f}%). Apply water now."
                elif n is not None and n < 40:
                    sub = f"Nitrogen LOW ({n:.0f} ppm). Add fertiliser."
                else:
                    sub = f"Multiple issues detected — tap 'Act Now' for details."
                bg = C["red"]
            elif st == "average":
                title = f"Zone {lbl_name} needs attention soon"
                sub   = "Conditions are below optimal — check recommendations."
                bg    = C["orange"]
            else:
                title = "All zones look healthy today 🎉"
                sub   = "Keep up the great work! Check Reports for trends."
                bg    = C["green_lt"]

            self._pri_title.config(text=title, bg=bg)
            self._pri_sub.config(text=sub, bg=bg)
            self._priority_card.config(bg=bg)
            self._priority_card.body()
            self._pri_btn.config(state="normal" if st in ("danger","average") else "disabled")
        else:
            self._pri_title.config(text="No zone data yet")
            self._pri_sub.config(text="Make sure the rover is running and sending data.")

        hour = datetime.now().hour
        greeting = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")
        self._greet_lbl.config(text=f"{greeting} 🌤️")

    def _act_on_priority(self):
        self._show("My Farm")

    # ═══════════════════════════════════════════════════════════════════════
    #  SCREEN 2 — My Farm  (zone grid + detail panel)
    # ═══════════════════════════════════════════════════════════════════════

    def _build_farm(self):
        p = self._screens["My Farm"]
        p.columnconfigure(0, weight=1)
        p.columnconfigure(1, weight=2)
        p.rowconfigure(1, weight=1)

        self._farm_filter = None

        # Toolbar
        tb = tk.Frame(p, bg=C["bg"])
        tb.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(14, 0))
        tk.Label(tb, text="Your farm zones", font=F["h2"],
                 bg=C["bg"], fg=C["soil"]).pack(side="left")
        for lbl, key in [("All", None), ("🟢 Good", "good"),
                         ("🟡 Watch", "average"), ("🔴 Urgent", "danger")]:
            tk.Button(tb, text=lbl, font=F["sm"],
                      bg=C["card"], fg=C["soil"], relief="flat",
                      cursor="hand2", padx=8, pady=4,
                      command=lambda k=key: self._set_farm_filter(k)
                      ).pack(side="left", padx=3)
        BigBtn(tb, "🔄 Refresh", self._refresh, bg=C["green"]).pack(side="right")

        # Zone list
        list_card = Card(p)
        list_card.grid(row=1, column=0, sticky="nsew", padx=(20, 6), pady=12)
        list_card.rowconfigure(0, weight=1)
        list_card.columnconfigure(0, weight=1)

        self._zone_lb = tk.Listbox(list_card, font=F["body"],
                                   bg=C["card"], fg=C["soil"],
                                   selectbackground=C["green"],
                                   selectforeground=C["white"],
                                   relief="flat", activestyle="none",
                                   borderwidth=0, highlightthickness=0)
        sb = tk.Scrollbar(list_card, command=self._zone_lb.yview)
        self._zone_lb.config(yscrollcommand=sb.set)
        self._zone_lb.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        sb.grid(row=0, column=1, sticky="ns")
        self._zone_lb.bind("<<ListboxSelect>>", self._on_zone_select)

        # Detail panel (right)
        detail_card = Card(p)
        detail_card.grid(row=1, column=1, sticky="nsew", padx=(6, 20), pady=12)
        self._detail_card = detail_card
        self._detail_inner = detail_card.body(padx=20, pady=16)
        self._detail_inner.columnconfigure(0, weight=1)
        tk.Label(self._detail_inner,
                 text="← Tap a zone to see details",
                 font=F["h3"], bg=C["card"], fg=C["slate"]).pack(pady=50)

    def _set_farm_filter(self, key):
        self._farm_filter = key
        self._populate_farm_list()

    def _populate_farm_list(self):
        self._zone_lb.delete(0, "end")
        self._visible_zones = []
        for z in self._zones:
            m  = z.get("soil_moisture_20cm")
            n  = z.get("nitrogen_ppm")
            ph = z.get("ph_level")
            st, _, tag = zone_health(m, n, ph)
            if self._farm_filter and st != self._farm_filter:
                continue
            lbl = z.get("zone_label", z.get("zone_id", "?"))
            self._zone_lb.insert("end", f"  {lbl}   {tag}")
            self._visible_zones.append(z)

    def _on_zone_select(self, _e):
        sel = self._zone_lb.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self._visible_zones):
            self._selected_zone = self._visible_zones[idx]
            self._render_zone_detail(self._selected_zone)

    def _render_zone_detail(self, zone: dict):
        for w in self._detail_inner.winfo_children():
            w.destroy()
        inn = self._detail_inner

        lbl  = zone.get("zone_label", zone.get("zone_id", "?"))
        m    = zone.get("soil_moisture_20cm")
        n    = zone.get("nitrogen_ppm")
        ph   = zone.get("ph_level")
        st, col, tag = zone_health(m, n, ph)

        # Header banner
        hdr = tk.Frame(inn, bg=col)
        hdr.pack(fill="x", pady=(0, 12))
        tk.Label(hdr, text=f"Zone {lbl}   {tag}",
                 font=F["h2"], bg=col, fg=C["white"],
                 padx=14, pady=10).pack(side="left")

        # Plain-language metrics — no raw numbers by default
        for field, raw, (txt, fcol) in [
            ("Water",   m,  moisture_label(m)),
            ("Nitrogen",n,  nitrogen_label(n)),
            ("Acidity", ph, ph_label(ph)),
        ]:
            row = tk.Frame(inn, bg=C["card"])
            row.pack(fill="x", pady=3)
            tk.Label(row, text=field, font=F["h3"],
                     bg=C["card"], fg=C["slate"],
                     width=10, anchor="w").pack(side="left")
            tk.Label(row, text=txt, font=F["body"],
                     bg=C["card"], fg=fcol).pack(side="left", padx=6)

        # Technical details hidden behind toggle (Progressive Disclosure)
        show_var = tk.BooleanVar(value=False)
        def _toggle_details():
            show_var.set(not show_var.get())
            detail_row.pack(fill="x", pady=2) if show_var.get() else detail_row.pack_forget()
            toggle_btn.config(text="▲ Hide numbers" if show_var.get() else "▼ Show numbers")

        toggle_btn = tk.Button(inn, text="▼ Show numbers",
                               font=F["sm"], bg=C["bg"], fg=C["slate"],
                               relief="flat", cursor="hand2",
                               command=_toggle_details)
        toggle_btn.pack(anchor="w", pady=(4, 0))

        detail_row = tk.Frame(inn, bg=C["card"])
        vals = []
        if m  is not None: vals.append(f"Moisture: {m:.1f}%")
        if n  is not None: vals.append(f"Nitrogen: {n:.0f} ppm")
        if ph is not None: vals.append(f"pH: {ph:.1f}")
        tk.Label(detail_row, text="   ".join(vals), font=F["mono"],
                 bg=C["card"], fg=C["slate"]).pack(anchor="w", padx=8, pady=4)

        tk.Frame(inn, bg=C["border"], height=1).pack(fill="x", pady=10)

        # Action buttons (Fitts: large, clearly labelled)
        BigBtn(inn, "💡  Get Recommendation",
               lambda z=zone: self._open_recommendation(z),
               bg=C["green"]).pack(fill="x", pady=3)
        BigBtn(inn, "💧  Plan Irrigation",
               lambda: self._show("Today's Tasks"),
               bg=C["blue"]).pack(fill="x", pady=3)

    # ── Recommendation modal ───────────────────────────────────────────────

    def _open_recommendation(self, zone: dict):
        zone_id = zone.get("zone_id", "")
        zlbl    = zone.get("zone_label", zone_id)

        win = tk.Toplevel(self.root)
        win.title(f"Recommendation — Zone {zlbl}")
        win.geometry("560x640")
        win.configure(bg=C["bg"])
        win.grab_set()

        tk.Label(win, text="💡  YieldVision Recommendation",
                 font=F["h2"], bg=C["green"], fg=C["white"],
                 padx=20, pady=14).pack(fill="x")

        body = tk.Frame(win, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=20, pady=16)
        body.columnconfigure(0, weight=1)

        loading = tk.Label(body,
                           text="⏳  Analysing your farm data…\n\nThis takes about 10–15 seconds.",
                           font=F["h3"], bg=C["bg"], fg=C["slate"],
                           justify="center")
        loading.pack(pady=40)

        def fetch():
            try:
                r = requests.get(
                    f"{self.SERVER}/api/precision/zone/{zone_id}/decisions",
                    timeout=20)
                if r.status_code == 200:
                    win.after(0, lambda d=r.json(): _render(d))
                else:
                    win.after(0, lambda: loading.config(
                        text="We couldn't load recommendations.\nCheck your internet and try again."))
            except Exception:
                win.after(0, lambda: loading.config(
                    text="We couldn't reach the server.\nCheck your connection and try again."))

        def _render(data: dict):
            loading.destroy()
            actions = data.get("top_actions", [])
            if not actions:
                tk.Label(body, text="No recommendations yet.",
                         font=F["body"], bg=C["bg"], fg=C["slate"]).pack()
                return

            top = actions[0]
            action_lbl = top.get("action_label", "No action")
            benefit    = top.get("net_benefit_usd", 0)
            conf       = top.get("confidence", 0)
            risk       = top.get("risk", "unknown")
            rec        = top.get("recommendation", {})
            rec_txt    = rec.get("text", "") if isinstance(rec, dict) else str(rec)

            # Plain-language recommendation card
            rc = tk.Frame(body, bg=C["green_lt"])
            rc.pack(fill="x", pady=(0, 10))
            tk.Label(rc, text=f"💡  {action_lbl}",
                     font=F["h2"], bg=C["green_lt"], fg=C["soil"],
                     padx=14, pady=10, wraplength=480, justify="left").pack(anchor="w")
            if rec_txt:
                tk.Label(rc, text=rec_txt,
                         font=F["body"], bg=C["green_lt"], fg=C["soil"],
                         padx=14, pady=(0, 10), wraplength=480,
                         justify="left").pack(anchor="w")

            # Expected results
            res = tk.Frame(body, bg=C["card"],
                           highlightbackground=C["border"],
                           highlightthickness=1)
            res.pack(fill="x", pady=4)
            ri = tk.Frame(res, bg=C["card"])
            ri.pack(fill="x", padx=14, pady=10)

            risk_col = {"low": C["green_lt"], "medium": C["amber"], "high": C["red"]}.get(risk, C["slate"])
            conf_bar = "█" * int(conf * 10) + "░" * (10 - int(conf * 10))
            conf_word = "HIGH" if conf >= 0.75 else ("MEDIUM" if conf >= 0.5 else "LOW")

            for ico, label, val in [
                ("📈", "Yield benefit",  f"~KSh {benefit * 130:.0f}"),
                ("📊", f"Confidence: {conf_word}", conf_bar),
                ("⚠️", "Risk level",    risk.upper()),
            ]:
                row = tk.Frame(ri, bg=C["card"])
                row.pack(fill="x", pady=3)
                tk.Label(row, text=f"{ico}  {label}",
                         font=F["body"], bg=C["card"],
                         fg=C["soil"], width=22, anchor="w").pack(side="left")
                vcol = risk_col if "Risk" in label else C["soil"]
                tk.Label(row, text=val, font=F["mono"],
                         bg=C["card"], fg=vcol).pack(side="left")

            # Three choices (User Agency — Norman)
            tk.Frame(body, bg=C["border"], height=1).pack(fill="x", pady=8)
            BigBtn(body, "✅  Yes, I will do this",
                   lambda: (messagebox.showinfo("Done!", "Great! Task added to Today's list."), win.destroy()),
                   bg=C["green"]).pack(fill="x", pady=3)

            if len(actions) > 1:
                BigBtn(body, "🔄  Show me other options",
                       lambda: _show_others(actions[1:]),
                       bg=C["blue"]).pack(fill="x", pady=3)

            BigBtn(body, "❌  I can't do this today",
                   lambda: (messagebox.askquestion("That's okay",
                       "Is it because of: time, money, or resources?\n(Your answer helps YieldVision learn)"),
                       win.destroy()),
                   bg=C["slate"]).pack(fill="x", pady=3)

        def _show_others(rest):
            for w in body.winfo_children():
                w.destroy()
            tk.Label(body, text="Other options for this zone:",
                     font=F["h3"], bg=C["bg"], fg=C["soil"]).pack(anchor="w", pady=(0, 8))
            for a in rest[:4]:  # Max 4 (Miller's Law)
                card = tk.Frame(body, bg=C["card"],
                                highlightbackground=C["border"],
                                highlightthickness=1)
                card.pack(fill="x", pady=4)
                ci = tk.Frame(card, bg=C["card"])
                ci.pack(fill="x", padx=12, pady=8)
                tk.Label(ci, text=a.get("action_label", "—"),
                         font=F["h3"], bg=C["card"], fg=C["soil"]).pack(anchor="w")
                b = a.get("net_benefit_usd", 0)
                rk = a.get("risk", "unknown")
                tk.Label(ci, text=f"Benefit: ~KSh {b*130:.0f}   Risk: {rk.upper()}",
                         font=F["sm"], bg=C["card"], fg=C["slate"]).pack(anchor="w")
                BigBtn(ci, "Choose this →",
                       lambda: (messagebox.showinfo("Done!", "Task added to Today's list."), win.destroy()),
                       bg=C["green"]).pack(anchor="e", pady=(6, 0))

        threading.Thread(target=fetch, daemon=True).start()

    # ═══════════════════════════════════════════════════════════════════════
    #  SCREEN 3 — Today's Tasks  (checklist UX)
    # ═══════════════════════════════════════════════════════════════════════

    def _build_tasks(self):
        p = self._screens["Today's Tasks"]
        p.columnconfigure(0, weight=1)
        p.rowconfigure(2, weight=1)

        # Progress bar area
        prog_frame = tk.Frame(p, bg=C["bg"])
        prog_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(14, 4))
        tk.Label(prog_frame, text="Today's progress",
                 font=F["h3"], bg=C["bg"], fg=C["soil"]).pack(side="left")
        self._task_progress_lbl = tk.Label(prog_frame, text="0 / 0 tasks",
                                           font=F["body"], bg=C["bg"],
                                           fg=C["slate"])
        self._task_progress_lbl.pack(side="right")

        self._progress_bar_canvas = tk.Canvas(p, bg=C["bg"],
                                              height=10, highlightthickness=0)
        self._progress_bar_canvas.grid(row=1, column=0, sticky="ew",
                                       padx=20, pady=(0, 8))

        # Task list scrollable
        list_card = Card(p)
        list_card.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 14))
        list_card.columnconfigure(0, weight=1)
        list_card.rowconfigure(0, weight=1)

        canvas = tk.Canvas(list_card, bg=C["card"], highlightthickness=0)
        scroll = tk.Scrollbar(list_card, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        self._tasks_inner = tk.Frame(canvas, bg=C["card"])
        self._tasks_inner.columnconfigure(0, weight=1)
        canvas_win = canvas.create_window((0, 0), window=self._tasks_inner, anchor="nw")

        def _resize(e):
            canvas.itemconfig(canvas_win, width=e.width)
        def _scroll_region(e):
            canvas.configure(scrollregion=canvas.bbox("all"))

        canvas.bind("<Configure>", _resize)
        self._tasks_inner.bind("<Configure>", _scroll_region)
        self._tasks_canvas = canvas

        self._task_checks: list = []

    def _populate_tasks(self):
        for w in self._tasks_inner.winfo_children():
            w.destroy()
        self._task_checks = []

        # Generate tasks from zones that need action
        urgent = [z for z in self._zones
                  if zone_health(z.get("soil_moisture_20cm"),
                                 z.get("nitrogen_ppm"),
                                 z.get("ph_level"))[0] in ("danger", "average")]

        if not urgent:
            tk.Label(self._tasks_inner,
                     text="🎉  No urgent tasks today!\nAll your zones look healthy.",
                     font=F["h2"], bg=C["card"], fg=C["green_lt"],
                     justify="center").pack(pady=40)
            self._task_progress_lbl.config(text="0 / 0 tasks")
            return

        tasks = []
        for z in urgent[:7]:  # Miller's Law: max 7
            lbl_name = z.get("zone_label", z.get("zone_id", "?"))
            m  = z.get("soil_moisture_20cm")
            n  = z.get("nitrogen_ppm")
            ph = z.get("ph_level")
            st, _, _ = zone_health(m, n, ph)
            priority_icon = "🔴" if st == "danger" else "🟡"
            if m is not None and m < 30:
                tasks.append((priority_icon, f"Water Zone {lbl_name}", "~20 mins", z))
            elif n is not None and n < 80:
                tasks.append((priority_icon, f"Fertilise Zone {lbl_name}", "~30 mins", z))
            elif ph is not None and (ph < 6.0 or ph > 7.8):
                tasks.append((priority_icon, f"Fix soil acidity — Zone {lbl_name}", "~15 mins", z))

        self._task_checks = []
        for i, (icon, title, duration, zone) in enumerate(tasks):
            var = tk.BooleanVar(value=False)
            row = tk.Frame(self._tasks_inner, bg=C["card"],
                           highlightbackground=C["border"],
                           highlightthickness=1)
            row.pack(fill="x", padx=8, pady=4)
            ri = tk.Frame(row, bg=C["card"])
            ri.pack(fill="x", padx=12, pady=10)

            cb = tk.Checkbutton(ri, variable=var, bg=C["card"],
                                activebackground=C["card"],
                                cursor="hand2",
                                command=lambda v=var, r=row: self._check_task(v, r))
            cb.pack(side="left")
            tk.Label(ri, text=icon, font=("Segoe UI", 16),
                     bg=C["card"]).pack(side="left", padx=(4, 8))
            tk.Label(ri, text=title, font=F["h3"],
                     bg=C["card"], fg=C["soil"]).pack(side="left")
            tk.Label(ri, text=duration, font=F["sm"],
                     bg=C["card"], fg=C["slate"]).pack(side="right")
            BigBtn(ri, "Details →",
                   lambda z=zone: (self._show("My Farm"),
                                   self._render_zone_detail(z)),
                   bg=C["green"]).pack(side="right", padx=(0, 6))
            self._task_checks.append(var)

        self._update_task_progress()

    def _check_task(self, var, row_frame):
        if var.get():
            row_frame.config(bg=C["bg"],
                             highlightbackground=C["green_lt"])
        else:
            row_frame.config(bg=C["card"],
                             highlightbackground=C["border"])
        self._update_task_progress()

    def _update_task_progress(self):
        total = len(self._task_checks)
        done  = sum(v.get() for v in self._task_checks)
        self._task_progress_lbl.config(text=f"{done} / {total} tasks done")
        w = self._progress_bar_canvas.winfo_width()
        self._progress_bar_canvas.delete("all")
        self._progress_bar_canvas.create_rectangle(0, 0, w, 10, fill=C["border"], outline="")
        if total:
            fill_w = int(w * done / total)
            self._progress_bar_canvas.create_rectangle(0, 0, fill_w, 10,
                                                       fill=C["green_lt"], outline="")
        if total and done == total:
            messagebox.showinfo("Great work! 🎉",
                                f"You completed all {total} tasks today!\nYour crops thank you.")

    # ═══════════════════════════════════════════════════════════════════════
    #  SCREEN 4 — Reports  (simple bar chart via canvas)
    # ═══════════════════════════════════════════════════════════════════════

    def _build_reports(self):
        p = self._screens["Reports"]
        p.columnconfigure(0, weight=1)
        p.rowconfigure(1, weight=1)

        tk.Label(p, text="Your farm over time",
                 font=F["h1"], bg=C["bg"], fg=C["soil"],
                 padx=20, pady=14).grid(row=0, column=0, sticky="w")

        card = Card(p)
        card.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 14))
        b = card.body(padx=20, pady=16)
        b.columnconfigure(0, weight=1)
        b.rowconfigure(1, weight=1)

        tk.Label(b, text="Soil health score by zone",
                 font=F["h2"], bg=C["card"], fg=C["soil"]).grid(row=0, column=0, sticky="w")
        tk.Label(b,
                 text="(Higher is better. Green = Healthy, Amber = Watch, Red = Urgent)",
                 font=F["sm"], bg=C["card"], fg=C["slate"]).grid(row=0, column=0, sticky="e")

        self._report_canvas = tk.Canvas(b, bg=C["card"], highlightthickness=0)
        self._report_canvas.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self._report_canvas.bind("<Configure>", lambda _: self._draw_report_chart())

    def _draw_report_chart(self):
        cv = self._report_canvas
        cv.delete("all")
        w = cv.winfo_width()
        h = cv.winfo_height()
        if w < 10 or h < 10 or not self._zones:
            return

        zones = self._zones[:20]  # max 20 bars
        n     = len(zones)
        margin_l, margin_b = 40, 30
        bar_area_w = w - margin_l - 20
        bar_w = max(8, bar_area_w // n - 4)

        # Grid lines
        for pct in (0, 25, 50, 75, 100):
            y = h - margin_b - int((h - margin_b - 10) * pct / 100)
            cv.create_line(margin_l, y, w - 10, y,
                           fill=C["border"], dash=(3, 3))
            cv.create_text(margin_l - 4, y, text=str(pct),
                           font=F["sm"], fill=C["slate"], anchor="e")

        for i, zone in enumerate(zones):
            m  = zone.get("soil_moisture_20cm")
            n_ = zone.get("nitrogen_ppm")
            ph = zone.get("ph_level")
            st, col, _ = zone_health(m, n_, ph)

            # Health score 0–100
            score_parts = []
            if m  is not None: score_parts.append(min(100, m / 50 * 100))
            if n_ is not None: score_parts.append(min(100, n_ / 150 * 100))
            if ph is not None:
                ph_score = 100 if 6.0 <= ph <= 7.0 else max(0, 100 - abs(ph - 6.5) * 30)
                score_parts.append(ph_score)
            score = sum(score_parts) / len(score_parts) if score_parts else 50

            x = margin_l + i * (bar_w + 4) + 2
            bar_h = int((h - margin_b - 10) * score / 100)
            y0 = h - margin_b - bar_h
            y1 = h - margin_b

            cv.create_rectangle(x, y0, x + bar_w, y1,
                                 fill=col, outline="")

            lbl = zone.get("zone_label", zone.get("zone_id", "?"))
            cv.create_text(x + bar_w // 2, h - margin_b + 14,
                           text=lbl, font=F["sm"],
                           fill=C["slate"], angle=45 if n > 10 else 0)

    # ═══════════════════════════════════════════════════════════════════════
    #  SCREEN 5 — Alerts
    # ═══════════════════════════════════════════════════════════════════════

    def _build_alerts(self):
        p = self._screens["Alerts"]
        p.columnconfigure(0, weight=1)
        p.rowconfigure(1, weight=1)

        tk.Label(p, text="Alerts & Notifications",
                 font=F["h1"], bg=C["bg"], fg=C["soil"],
                 padx=20, pady=14).grid(row=0, column=0, sticky="w")

        scroll_card = Card(p)
        scroll_card.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 14))
        scroll_card.columnconfigure(0, weight=1)
        scroll_card.rowconfigure(0, weight=1)

        canvas = tk.Canvas(scroll_card, bg=C["card"], highlightthickness=0)
        sb = tk.Scrollbar(scroll_card, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

        self._alerts_inner = tk.Frame(canvas, bg=C["card"])
        self._alerts_inner.columnconfigure(0, weight=1)
        aw = canvas.create_window((0, 0), window=self._alerts_inner, anchor="nw")

        def _rz(e): canvas.itemconfig(aw, width=e.width)
        def _sc(e): canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.bind("<Configure>", _rz)
        self._alerts_inner.bind("<Configure>", _sc)

    def _populate_alerts(self):
        for w in self._alerts_inner.winfo_children():
            w.destroy()

        critical = [z for z in self._zones
                    if zone_health(z.get("soil_moisture_20cm"),
                                   z.get("nitrogen_ppm"),
                                   z.get("ph_level"))[0] == "danger"]
        watch    = [z for z in self._zones
                    if zone_health(z.get("soil_moisture_20cm"),
                                   z.get("nitrogen_ppm"),
                                   z.get("ph_level"))[0] == "average"]

        sections = [
            ("🔴  Act Today", critical, C["red"]),
            ("🟡  This Week",  watch,   C["amber"]),
        ]

        any_alert = False
        for section_title, zones, colour in sections:
            if not zones:
                continue
            any_alert = True
            tk.Label(self._alerts_inner, text=section_title,
                     font=F["h2"], bg=C["card"], fg=colour,
                     padx=16, pady=8).pack(anchor="w")

            for z in zones[:5]:  # Miller's Law
                lbl_name = z.get("zone_label", z.get("zone_id", "?"))
                m  = z.get("soil_moisture_20cm")
                n_ = z.get("nitrogen_ppm")
                ph = z.get("ph_level")

                if m is not None and m < 20:
                    msg = f"Zone {lbl_name}: Soil is critically DRY ({m:.0f}%). Apply water today."
                elif n_ is not None and n_ < 40:
                    msg = f"Zone {lbl_name}: Nitrogen LOW ({n_:.0f} ppm). Apply fertiliser."
                elif ph is not None and ph < 5.5:
                    msg = f"Zone {lbl_name}: Soil too acidic (pH {ph:.1f}). Add lime."
                else:
                    msg = f"Zone {lbl_name}: Multiple conditions need attention."

                row = tk.Frame(self._alerts_inner, bg=colour + "22",
                               highlightbackground=colour,
                               highlightthickness=1)
                row.pack(fill="x", padx=12, pady=3)
                ri = tk.Frame(row, bg=row["bg"])
                ri.pack(fill="x", padx=12, pady=8)
                tk.Label(ri, text=msg, font=F["body"],
                         bg=row["bg"], fg=C["soil"],
                         wraplength=480, justify="left").pack(side="left")
                BigBtn(ri, "Act →",
                       lambda z=z: (self._show("My Farm"),
                                    self._render_zone_detail(z)),
                       bg=colour).pack(side="right")

        if not any_alert:
            tk.Label(self._alerts_inner,
                     text="✅  No alerts right now.\nAll zones are healthy!",
                     font=F["h2"], bg=C["card"], fg=C["green_lt"],
                     justify="center").pack(pady=60)


# ═══════════════════════════════════════════════════════════════════════════
def main():
    root = tk.Tk()
    YieldVisionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()