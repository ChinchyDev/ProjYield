# YieldVision Desktop

Electron + React desktop application for the YieldVision precision farming system.  
Companion to the FastAPI backend (`../main_server.py`).

---

## What this is

A farmer-facing desktop app that connects to the YieldVision backend and displays:

- **Home** — greeting, critical alerts, zone health summary, rover status
- **Farm** — GPS-positioned zone map, zone-by-zone soil readings, inline recommendations
- **Tasks** — today's recommended actions sorted by urgency, mark done/skip
- **Alerts** — CRITICAL → HIGH → MEDIUM urgency tiers, rover scan schedule

The app is **offline-first** by design. It shows the last fetched data if the server is unreachable, and syncs when the connection comes back.

---

## Project structure

```
yieldvision-desktop/
├── electron.js          # Electron main process (window, IPC)
├── preload.js           # Secure bridge between Electron and React
├── package.json
├── tailwind.config.js
├── postcss.config.js
├── .env.example         # Copy to .env — configure API URL here
├── public/
│   └── index.html
└── src/
    ├── index.jsx        # React entry point
    ├── index.css        # Tailwind + global styles
    ├── App.jsx          # Root component — session, theme, routing
    ├── theme.js         # Light/dark design tokens (Palette B)
    ├── api.js           # All backend API calls
    ├── utils/
    │   └── health.js    # Zone health scoring, status labels
    ├── components/
    │   ├── BottomNav.jsx
    │   ├── Pill.jsx
    │   ├── StatCard.jsx
    │   ├── SectionHeader.jsx
    │   └── Spinner.jsx
    └── screens/
        ├── OnboardingScreen.jsx  # Login / farm registration
        ├── HomeScreen.jsx
        ├── FarmScreen.jsx
        ├── ZoneMap.jsx           # GPS scatter-plot of zones
        ├── ZoneDetail.jsx        # Zone readings + recommendations
        ├── TasksScreen.jsx
        └── AlertsScreen.jsx
```

---

## Prerequisites

| Dependency | Version  | Notes                    |
|------------|----------|--------------------------|
| Node.js    | ≥ 18     | Required for Electron 29 |
| npm        | ≥ 9      |                          |
| Python     | ≥ 3.8    | For the FastAPI backend  |

---

## Getting started

### 1. Install dependencies

```bash
cd yieldvision-desktop
npm install
```

### 2. Start the backend (separate terminal)

```bash
# From the project root (where main_server.py lives)
pip install -r requirements.txt
python main_server.py
```

The FastAPI server runs on `http://localhost:8000` by default.

### 3. Run in development mode

```bash
# Starts React dev server + Electron together
npm run electron:dev
```

This opens the Electron window loading `localhost:3000` with hot reload.  
DevTools open automatically in detached mode.

### 4. Run React only (browser, no Electron)

```bash
npm start
```

Useful for fast UI iteration. Opens `http://localhost:3000` in your browser.

---

## Building a distributable

```bash
npm run electron:build
```

Output goes to `dist/`. Produces:
- **macOS** → `.dmg`
- **Windows** → `.exe` (NSIS installer)
- **Linux** → `.AppImage`

> **Note:** Code signing is not configured. For production distribution  
> you will need to add your certificates to `electron-builder` config in `package.json`.

---

## Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Variable               | Default                    | Description                          |
|------------------------|----------------------------|--------------------------------------|
| `REACT_APP_API_URL`    | `http://localhost:8000`    | FastAPI backend URL for browser/PWA  |
| `YIELDVISION_API_URL`  | `http://localhost:8000`    | FastAPI URL for Electron (env var passed to the process) |

To point to a backend on a different machine (e.g. a Raspberry Pi on the same network):

```bash
YIELDVISION_API_URL=http://192.168.1.42:8000 npm run electron
```

---

## Design system

**Palette B** — all five colours used throughout:

| Token     | Hex       | Role (60-30-10)                         |
|-----------|-----------|-----------------------------------------|
| `#1B2727` | Deep teal | Dark mode background, text on light bg |
| `#3C5148` | Forest    | Panels, nav bar, primary buttons (30%) |
| `#6B8E4E` | Olive     | Accent, healthy status, actions (10%)  |
| `#B2C5B2` | Sage      | Muted text, borders, nav glow          |
| `#D5DDDF` | Mist      | Light mode background (60%)            |

**Theme tokens** live in `src/theme.js`. Both light and dark modes export the same token names so components never need to know which mode is active — they just receive the `t` prop.

**Dark/light toggle** — controlled by `App.jsx`, saved to `localStorage`. Defaults to the OS preference (`prefers-color-scheme`).

---

## Backend API endpoints used

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/health` | Server + DB connectivity check |
| `GET`  | `/farms/{id}/summary` | Farm overview, zone list |
| `POST` | `/farms/register` | Register a new farm |
| `GET`  | `/zones/{id}/state?farm_id=` | Latest zone sensor readings |
| `POST` | `/zones/{id}/recommend?farm_id=` | Generate recommendations |
| `GET`  | `/farms/{id}/recommendations` | Pending recommendations |
| `PATCH`| `/recommendations/{id}/apply?farm_id=` | Mark done/skipped |
| `GET`  | `/rover/schedule/{id}` | Rover scan priority queue |

> **Note:** The `/farms/{id}/summary` endpoint should return a `zones` array for  
> the Farm Map to populate with zone positions. If this isn't in your current  
> `farm_summary` view, add a `GET /farms/{id}/zones` endpoint or extend the view.

---

## Roadmap (planned, not yet built)

- [ ] Zone planting registration form (add crop to a zone)
- [ ] SD card batch upload UI (drag-and-drop CSV from rover)
- [ ] Irrigation calculator screen
- [ ] PWA build (same codebase, `npm run build` + serve)
- [ ] Open-Meteo rain forecast integration (post-demo)

---

## Relationship to the backend

```
yieldvision-desktop/     ← this folder (React + Electron)
    ↕  HTTP (localhost:8000)
main_server.py           ← FastAPI backend
decision_engine.py
irrigation_engine.py
precision_models.py
database_setup.sql       ← PostgreSQL schema
```

The desktop app and backend are intentionally separate — the backend can run on the same machine, a local server, or eventually a Raspberry Pi attached to the rover. The desktop app only needs the `API_URL` to point at it.
