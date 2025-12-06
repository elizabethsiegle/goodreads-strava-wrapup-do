## Goodreads + Strava 2025 Wrapped

- Users can upload Goodreads and Strava CSVs to generate a friendly 2025 wrap-up with charts and summaries
- Stack: Streamlit, pandas, Altair, model calls via DigitalOcean Inference, deployed app via GitHub repo URL[DigitalOcean app platform](https://www.digitalocean.com/products/app-platform)

Quick start
- Install deps: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Run app: `streamlit run app.py`
- Upload 1 or both: Goodreads `goodreads_library_export.csv` and Strava `activities.csv`

[Export Strava data here](https://www.strava.com/athlete/delete_your_account)

[Export Goodreads data here](https://www.goodreads.com/review/import)

[Upload your data here to try it out in the webapp!](https://goodreads-strava-wrapup-9x5tw.ondigitalocean.app/) 

Environment
- Create `.env` (do not commit secrets):
	- `MODEL_ACCESS_KEY=...` for [Inference API calls from DigitalOcean](https://docs.digitalocean.com/products/gradient-ai-platform/how-to/use-serverless-inference/#keys)

Features
- Wrap-up cards shown before visualizations
- Miles/mph units; Strava links built from Activity ID/Filename
- Books charts (monthly, cumulative) + ratings distribution
- Steps views (daily, weekly, 7‑day average; overlay chart)
- Optional genre insight and celebratory image posters

DigitalOcean links
- Inference: https://www.digitalocean.com/products/inference
- App Platform: https://www.digitalocean.com/products/app-platform

Notes (lol)
- Keep `.env` out of git (`.gitignore` includes it).
- CSV schemas vary; the app uses defensive parsing for dates and IDs.
