# Loom walkthrough outline (target 7–8 min)

1. **Problem (0:00–0:45)**: the same trip can be safe or dangerous depending on *when*
   the truck reaches each stretch. The app plans routes around the forecast at the
   truck's ETA, not the weather right now.

2. **Demo (0:45–3:30)**
   - Type the origin and destination (Photon typeahead), set the departure time, load
     and interval, then press **Plan routes**.
   - Walk through the recommendation banner and its reason, then the 3 route cards
     (Severe and High miles, average risk, arrival time).
   - Click a non-recommended route to see its risk colouring change on the map.
   - Click a checkpoint in the list: the map flies to it, the popup shows the ETA,
     wind, gusts, rain and snow plus the reasons, and the heatmap jumps to that hour.
   - Play the 0–48 h heatmap and show weather moving across the corridor.
   - Change the load across 30,000 / 40,000 lb and re-plan to show the brief's wind-and-load
     rules (35–44 mph over 40k lb → Severe; 45–54 mph over 30k lb → No Travel).

3. **How it works (3:30–5:30)**
   - Pipeline: Valhalla truck routes → checkpoints every N mi → ETA from maneuver
     times → Open-Meteo hour at that ETA → risk engine → ranking. (Show `service.py`.)
   - `risk_rules.py` holds the brief's table (5 levels including No Travel) and `risk.py`
     is a pure function; show the band-edge tests in `test_risk.py`.
   - Mile accounting: each checkpoint covers half the gap to its neighbours, so the
     stretches add up to the route length.
   - `ranking.py`: the brief's four tie-breakers (No Travel miles compared first) and the
     reason sentence.

4. **Engineering choices (5:30–7:00)**
   - Why Valhalla (ORS's public API caps alternatives at 100 km), Photon (Nominatim
     forbids autocomplete) and Open-Meteo (free, batched, 16 days ahead).
   - Throttling and caching for public APIs; one endpoint; a stateless backend; one
     Docker image.
   - 100+ backend tests run on real API fixtures with no network calls; CI; errors use
     one shape with clean upstream failure handling.

5. **Limitations and next steps (7:00–7:45)**: hourly forecast granularity,
   best-effort public servers, departure-time optimisation, and ice/visibility factors.
