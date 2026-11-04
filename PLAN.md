# Implementation Plan: Weather-Aware Truck Routing

**Budget:** 16 working hours over 4 days. **Priority:** correctness and clarity first, extras last.
**Deliverables:** GitHub repo, hosted app, 5–10 minute Loom.

## 1. What the app does

1. The user enters an origin and destination (Photon autocomplete), a departure date/time, a load weight, and a sampling interval (10 / 25 / 50 mi, default 25).
2. The backend fetches **3 truck routes** from Valhalla (`costing: "truck"`, `alternates: 2`).
3. Each route is cut into **checkpoints every N miles**. Each checkpoint gets an **ETA**, which is the departure time plus the cumulative drive time to that point.
4. Weather for each checkpoint comes from Open-Meteo, using the **forecast hour that matches its ETA**.
5. The **risk engine** classifies each checkpoint using the brief's wind/rain/snow table plus the load-weight rules.
6. The **ranking** picks the recommended route by: fewest Severe miles → fewest High miles → lowest average risk → shortest time.
7. The UI shows the routes coloured by risk, checkpoint markers, a legend, a side panel that explains the recommendation, and a 0–48h weather heatmap slider.

## 2. Architecture

```
frontend/  React + TS + Vite
  ├─ TripForm (Photon typeahead, datetime, weight, interval)
  ├─ MapView (MapLibre: route lines, checkpoint markers, heatmap layer)
  ├─ SidePanel (route comparison, "why recommended", checkpoint list)
  ├─ HeatmapSlider (0–48h, client-side frame switching)
  └─ api/ (TanStack Query hook usePlan, typed DTOs)

backend/   Django + DRF
  └─ routing/
       ├─ api: POST /api/plan  (single endpoint), GET /api/health
       ├─ clients/valhalla.py   (HTTP, 1 req/s throttle, cache)
       ├─ clients/openmeteo.py  (batched multi-coord, cache)
       ├─ geo.py                (polyline6 decode, haversine, resample by distance)
       ├─ checkpoints.py        (distance → ETA interpolation)
       ├─ risk.py               (PURE: weather + load → level)  ← unit-tested hardest
       ├─ ranking.py            (PURE: routes → ordered + reason)
       ├─ heatmap.py            (grid over route bbox × 0–48h)
       └─ service.py            (orchestrates the above)
```

**Key decisions**
- **One endpoint.** `POST /api/plan` returns routes, checkpoints, per-route summary, the recommendation and its reason, and the heatmap grid. The frontend makes one round-trip and the slider runs entirely on the client.
- **Pure core.** `risk`, `ranking`, `geo` and `checkpoints` do no I/O, so they're testable with plain pytest. Their tests use fixtures and never hit the network.
- **Caching.** Django's local-memory cache (switchable to file or Redis through env). Valhalla responses are cached by (origin, destination, rounded weight). Open-Meteo responses are cached by (rounded lat/lon, model run hour). Valhalla's 1 req/s limit is enforced with a process-level lock and timestamp.
- **Units.** Open-Meteo is called with `wind_speed_unit=mph&precipitation_unit=inch` so its values compare directly with the brief's table. Snowfall comes back in cm, so convert it in exactly one place.
- **Mile weighting.** Each checkpoint stands for the stretch of road around it, half the interval on each side, clipped at the route ends. Severe and High miles are the sums of those stretches, and average risk is the mile-weighted mean of the levels' numeric scores.
- **Forecast horizon.** Open-Meteo covers up to 16 days. Any checkpoint ETA beyond that is flagged "no forecast" and doesn't count toward risk, and the UI shows it.
- **Time zones.** The departure time is sent as ISO-8601 with an offset and everything is computed in UTC. Open-Meteo is queried with `timezone=UTC`.
- **Heatmap.** A coarse grid over the padded bbox of all routes (≤ ~150 points, adaptive spacing), fetched with batched multi-coordinate Open-Meteo calls for hours 0–48 after departure. Each cell gets a risk level per hour, using the same `risk.py` without the ETA logic.

## 3. API contract (draft)

`POST /api/plan`
```json
{ "origin": {"lat": 32.78, "lon": -96.80, "label": "Dallas, TX"},
  "destination": {"lat": 39.74, "lon": -104.99, "label": "Denver, CO"},
  "departure": "2026-11-06T08:00:00-06:00",
  "load_weight_lbs": 42000,
  "interval_miles": 25 }
```
Response (abridged):
```json
{ "recommended_route_id": "r1",
  "recommendation_reason": "Fewest Severe miles (0 vs 50, 75)",
  "routes": [{ "id": "r1", "distance_mi": 853, "duration_h": 13.1,
               "geometry": [[lon,lat],...],
               "summary": {"severe_mi": 0, "high_mi": 25, "avg_risk": 0.8},
               "checkpoints": [{ "mile": 25, "lat": 0, "lon": 0, "eta": "...",
                                 "weather": {"wind_mph": 0, "gust_mph": 0, "rain_in_h": 0, "snow_in_h": 0},
                                 "risk": "low", "reasons": ["..."] }] }],
  "heatmap": { "hours": [0,...,48], "cells": [{"lat":0,"lon":0,"risk":[0,1,...]}] },
  "warnings": [] }
```
Errors use a consistent `{ "error": { "code", "message" } }` shape with 400 / 502 / 504.

## 4. Schedule and tickets

| Day | Ticket | Est |
|---|---|---|
| **1 — Backend core** | Scaffold Django + DRF, env config, CORS, health, pytest, ruff | 1.0h |
| | Risk engine (pure) + exhaustive tests from the brief's table | 1.5h |
| | Valhalla client: 3 truck routes, polyline6, throttle, cache | 1.5h |
| **2 — Pipeline** | Checkpoint sampler + ETA interpolation (+ tests) | 1.5h |
| | Open-Meteo client: batched, ETA-hour lookup, units, cache | 1.5h |
| | Ranking (pure) + `/api/plan` orchestration + API tests | 1.0h |
| **3 — Frontend** | Scaffold Vite React TS, Tailwind, TanStack Query, typed client | 0.75h |
| | Trip form with Photon typeahead + validation | 1.0h |
| | MapLibre map: risk-coloured routes, checkpoints, legend | 1.5h |
| | Side panel: comparison, recommendation reason, checkpoint list | 1.0h |
| | Heatmap: backend grid + 0–48h slider layer | 1.5h |
| **4 — Ship** | Loading/error/empty states + edge cases | 0.5h |
| | Deploy backend + frontend (ask Junaid before creating accounts) | 1.0h |
| | README (setup, architecture, decisions, limits) + Loom outline | 1.0h |
| | **Total** | **~15.75h** (≈ 15 min buffer) |

Cut line if behind: the heatmap shrinks to a static frame at departure +0h, then to a stretch goal.

## 5. Risks and open questions
- **The brief's exact risk table and load rules aren't in the repo yet.** Add the brief as `docs/BRIEF.md` before the risk-engine ticket so the thresholds are encoded word for word and tested.
- The Valhalla public server can be slow or rate-limited. Mitigate with caching, a timeout, a clear 502 message, and saved route fixtures for tests and the demo.
- Valhalla may return fewer than 3 alternates on short trips. Show however many it returns and say so in a warning.
- Hosting is undecided (e.g. Render for Django, Vercel/Netlify for the frontend). It needs Junaid's go-ahead before any accounts are created or anything is deployed.
