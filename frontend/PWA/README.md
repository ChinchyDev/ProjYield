# YieldVision PWA

Progressive Web App for YieldVision precision farming system.
HCI-grounded design for Kenyan smallholder farmers.

## Quick Start

```bash
npm install
npm start
```

Opens at http://localhost:3000

## Build for Production

```bash
npm run build
```

## Backend

Requires `backend/main_server.py` running at http://localhost:8000

```bash
cd ../../backend
python main_server.py
```

## HCI Principles Applied

- **Hick's Law** — 5 nav items max, Miller's Law for lists (max 7)
- **Fitts's Law** — all touch targets ≥ 48px
- **Norman UCD** — plain farming language, not sensor jargon
- **Progressive Disclosure** — summary first, technical details behind toggle
- **Nielsen Heuristics** — visibility of status, error prevention, offline mode
- **Colour + icon + text** — never colour alone (accessibility)

## Screens

| Screen | Purpose |
|--------|---------|
| 🏠 Dashboard | Priority alert + farm at a glance |
| 🌱 My Farm | Zone list + plain-language detail |
| 📋 Today's Tasks | Checklist with progress bar |
| 📊 Reports | Bar chart health scores |
| 🔔 Alerts | Act Today / This Week grouping |
