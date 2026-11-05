# Loom recording script (≈5–6 min)

Read this aloud while recording with Loom (screen + camera bubble if you like).
Each section is one scene: do the **On screen** action, then read the text.
Live app: https://spotter-truck-routing-vh98.onrender.com (open it a minute before you
record, because Render's free tier takes ~30–60 s to wake up). Repo: https://github.com/junaidshahzad3/spotter-truck-routing

A generated version with a synthetic voice is produced by `scripts/walkthrough` (see its README).

## Weather-Aware Truck Routing

**On screen:** Show the app's home page (or the title card).

Hi, this is a walkthrough of Weather-Aware Truck Routing, my take-home project for Spotter AI's full stack role. It's a React and Django app that helps a truck driver pick the safest route, based on the forecast at the time the truck will actually reach each part of the trip, the load weight, and travel time. I'll demo the app first, then walk through the risk and ranking logic, the tests, and how it's built and deployed.

## 1 · Trip details

**On screen:** Type Dallas → pick it, Denver → pick it, set the departure time, 42000 lb, leave 25 mi.

The driver enters an origin and a destination. Place search uses Photon, which is designed for type-ahead. Then the departure date and time, the load weight in pounds, and how often to sample the weather along the way: every ten, twenty-five, or fifty miles. The default is twenty-five.

## 2 · Planning the trip

**On screen:** Click **Plan routes** and wait for the results.

When I press Plan routes, the backend asks Valhalla, an open-source routing engine, for three truck routes. It places a checkpoint every twenty-five miles on each route, works out the truck's arrival time at each checkpoint from Valhalla's own drive times for each road segment, and looks up the Open-Meteo forecast for that exact hour.

## 3 · Recommendation

**On screen:** Point at the recommendation banner, then each route card.

On the left is the recommended route and the reason it was chosen, followed by a card for each route: its Severe and High risk miles, average risk, distance, drive time, and arrival. Routes are ranked exactly as the brief asks. Fewest Severe miles first, then fewest High miles, then lowest average risk, then shortest travel time. The brief also defines a No Travel level, so No Travel miles are compared before anything else. A route through No Travel conditions should never win.

## 4 · Routes and checkpoints on the map

**On screen:** Click another route card, then back; click a checkpoint in the list (popup opens).

On the map, the selected route is colored by the risk at each checkpoint, and the alternatives are shown in grey. I can switch routes from the cards, or by clicking a route on the map. Below the cards is every checkpoint with its arrival time and risk level. Clicking one flies the map to it and opens the details: wind, rain, and snow at the arrival hour, and the reasons behind its risk level.

## 5 · 0–48 hour weather heatmap

**On screen:** Close the popup, zoom out, drag the heatmap slider, press Play.

At the bottom is the weather heatmap along the trip corridor, with a forecast slider from zero to forty-eight hours after departure. The whole grid arrives in the same response as the routes, so scrubbing and playback run entirely in the browser with no extra requests, which keeps it smooth.

## 6 · Risk rules from the brief

**On screen:** Open `backend/routing/risk_rules.py` on GitHub; scroll to the load rules.

Now the logic. All the thresholds live in one file, risk rules dot p y, copied from the brief. Wind, rain, and snow each have five bands, from Low to No Travel. The load rules are here too. Fifty-five miles an hour or more is No Travel for any load. Forty-five to fifty-four, with more than thirty thousand pounds, is No Travel. And thirty-five to forty-four, with more than forty thousand pounds, is Severe.

## 7 · The classifier

**On screen:** Open `backend/routing/risk.py` → `classify()`.

The classifier is a pure function. It grades each factor on its table, applies the load rules, which can only raise the wind level, never lower it, and takes the worst factor as the checkpoint's level. It also returns plain-English reasons, which is what the map popups display.

## 8 · Tests

**On screen:** Open `backend/tests/test_risk.py`; scroll through WIND/RAIN/SNOW and the load-rule cases.

The tests check every band edge, exactly at, just below, and just above each threshold, plus every load rule, against values copied by hand from the brief, so a typo in the rules file can't make its own tests pass. All of the routing, weather, and ranking logic is plain functions tested on recorded API responses, so the hundred and two backend tests run in a couple of seconds, without the network.

## 9 · Ranking

**On screen:** Open `backend/routing/ranking.py` → `summarize()` and `rank()`.

Ranking summarizes each route by the miles at each risk level. Each checkpoint stands for the road halfway to its neighbors, so the stretches add up exactly to the route length. It then sorts by the brief's criteria, and writes a one-line explanation naming the criterion that decided it.

## 10 · Architecture and decisions

**On screen:** Open the README → Architecture and Key decisions.

The README covers the architecture and the main decisions. OpenRouteService's public API caps alternative routes at one hundred kilometers, so Valhalla handles long-haul trips. Nominatim doesn't allow type-ahead, so place search uses Photon. Open-Meteo is free, needs no key, and accepts many coordinates in one request. The backend is stateless, with a single plan endpoint, and it caches results and throttles calls to stay within the public servers' limits.

## 11 · Deployment and next steps

**On screen:** Show the GitHub Actions tab, then the live app URL.

Django serves the built React app from a single Docker image deployed on Render, and GitHub Actions runs linting, the backend tests, and the frontend build on every push. Known limits: forecasts are hourly, and the public routing server is best effort. Next, I'd add departure-time optimization: trying a few departure times and recommending the safest window. Thanks for watching.
