# CS2 COLORFORGE

A mobile-friendly Counter-Strike 2 loadout viewer with live marketplace lookups.

## Features
- Curated coverage of the 34 standard CS2 firearms: rifles, pistols, SMGs and heavy weapons.
- CS2 skin artwork loaded from the ByMykel CS2 catalogue.
- Live price checks against Steam Community Market, Skinport and CSFloat.
- Displays available marketplace results with direct links; the lowest returned listing is used for the displayed total.
- NAD (Namibian dollars) and ZAR (South African rand) conversion from a live USD exchange-rate feed.
- No demo prices. Missing live prices remain unavailable and are excluded from the partial total.
- Responsive layout for Android and desktop browsers.

## Deploy on Render
1. Connect this GitHub repository to Render as a **Web Service**.
2. Use the repository root as the root directory.
3. Render can read `render.yaml`; alternatively use:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn server:app --workers 2 --threads 8 --timeout 120`
   - Health check path: `/health`
4. Open the Render URL on your Android phone and use the browser menu to add it to your Home screen.

The included Blueprint targets Render's free plan in Frankfurt. Render plan availability and free-tier limits can change.

## Run locally
Python 3.11+:

```bash
pip install -r requirements.txt
python server.py
```

Open http://localhost:5000.

## Price and data notes
- Price feeds are external and can rate-limit, block requests, or omit items. The app never substitutes sample/demo prices.
- Skinport data is cached for five minutes. Exchange rates are cached for one hour; the skin catalogue is cached for one hour.
- Steam prices are queried across standard wear grades. Skinport/CSFloat return the listing information their public endpoints make available.
- Displayed prices are indicative marketplace listings, not guaranteed checkout prices; taxes, fees, region and item wear may affect final cost.
- A missing price means no result was returned by the selected sources at lookup time, not that the item is free or unavailable for purchase.
