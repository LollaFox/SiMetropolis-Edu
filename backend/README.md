# Narrative city sandbox backend

Backend development reference. For classroom downloads, see [SiMetropolis Edu](../README.md).

Teammate guides: [frontend API handoff (English)](docs/releases/FRONTEND_HANDOFF_EN.md) / [中文](docs/releases/FRONTEND_HANDOFF_ZH.md); [reading saved city history (English)](docs/releases/CITY_HISTORY_EN.md) / [中文](docs/releases/CITY_HISTORY_ZH.md).

A working backend for the existing Northern Metropolis handoff frontend. The default offline demonstration completes 50 residential towers, 12 business towers, 10 parks and 4 stations. The frontend files are unchanged. All scenario values and social profiles are synthetic.

## Saved simulation data

The offline demonstration contains twelve months. Saved months are available through the replay and snapshot endpoints below.

The unchanged frontend API renderer has no tower-mesh input. Its API map is therefore a separate footprint view; the overview uses schematic existing city sites. Display distances/district labels are not the engine's exact grid. Legacy housing labels mean resident places here; unavailable climate/finance panels can display zero. These limits are also disclosed in the initialization review and `/api/model`.

## Change the government script

`examples/default-scenario.json` and `examples/parks-first-scenario.json` have the same objects and locations. The latter completes all parks in month 1. Change `x/y`, `startMonth` and `completionMonth` to compare locations and timing. Months are one-based relative to the selected start date. Duplicate cells, invalid dates/types and inconsistent capacities are rejected.

The numerical engine owns construction, 25-person groups, four group slots/tower, exact 3×3 neighborhoods, fixed firms, jobs, rents and monthly persistence. AI supplies completion narratives, small/large firm choices and four district-wide resident role decisions. Invalid resident batches preserve occupancy. A failed mandatory firm choice records deterministic small-firm recovery. Rent premiums begin in the next month and are recomputed without compounding.

## Regional Northern Metropolis preset

To export the regional preset from the command line, run the following command.

```sh
python3 -B -m backend.cli --preset northern-metropolis --output /private/tmp/nm-regional-offline
```

The preset fills all 132 cells of a schematic 12×11 grid: 100 residential development clusters, 20 business clusters, eight park objects and four station objects. Five residential clusters start each month and complete in the following month; the full script takes 21 monthly steps. Its startup demonstration and CLI default cover **2025-01-01 through 2026-09-01**. Configure chooses 1 to 5 years and the product run honors those dates. An explicit CLI `--end` overrides its default. Choose either `--preset` or `--scenario`, not both.

Each residential cluster has four 6,250-person slots: 25,000 resident places, totaling 2.5 million potential places when all clusters complete. Actual population comes from AI entry/departure decisions and can be much lower. Each assigned business cluster offers 26,000 small-firm or 39,000 large-firm positions; the AI mix produces between 520,000 and 780,000 offers. The 650,000 reference is a midpoint, not a forced outcome. The 60% potential-worker assumption and workers without allocated modeled jobs do not measure real regional unemployment.

These objects represent aggregate development clusters, not literal towers or surveyed projects. The [official InvestHK overview](https://www.investhk.gov.hk/en/why-hong-kong/super-connector-to-china-and-the-world/) supplies the reference magnitudes of about 300 km², 2.5 million residents and 650,000 jobs; its 900,000 homes are a different quantity from this model's resident places. Locations, object proportions, construction dates, wages and financial coefficients remain synthetic. The validated `scale` metadata, assumptions and sources appear in initialization review, `/api/model` and saved-run exports.

Every exported month includes a separate `monthlyBuildingTotals` table with `housingCapacity`, `plannedHousingCapacity`, `actualResidents`, `offeredJobs`, `filledJobs` and `vacancies` for every object. These are computed from the canonical state rather than duplicated inside its large audit record. CLI runs save the same derived tables in `building-totals.json.gz`.

## Offline exports and live runs

```sh
python3 -B -m backend.cli --output /private/tmp/nm-narrative-offline
```

Choose a new output directory for each run. Outputs include monthly states, complete decision context/outcomes, narratives, events, provider-attempt metrics and a summary. New monthly files use lossless gzip plus shared structural records; [storage format and measurements](docs/STORAGE.md) explain the transparent reader and preserved legacy files. Server data lives under `backend/.data/` and is excluded from Git. `/api/v3/simulations/{simulationId}/export` provides fully hydrated canonical states, per-object tables and metrics; IDs are returned by simulation or available in `/api/state`.

The pacing flags start five residential towers each month and finish each tower in the following month, completing all fifty by month 11. Change `--residential-starts-per-month`, `--construction-months`, and optional `--construction-interval-months` to vary the government schedule. Omitting all pacing flags preserves the original script. Month 1 of this paced scenario has residential construction sites and no completed residential occupancy.

The CLI accepts provider and pacing flags for a direct exported run. DeepSeek defaults to `deepseek-flash`; `--timeout 120` or `--timeout 180` sets the per-request wait, and `--retries 2` allows at most two transient retries per request.

Startup demonstration stays offline even with a live provider selected; only newly confirmed API runs use that provider. There is **no total live-call cap**. Per-request timeouts and bounded transient retries remain. The adapter records actual attempts, bytes, runtime, failures and returned token usage. Job polling exposes the active month and attempt progress before a monthly state is saved; direct CLI runs also write `status.json`. The first 12-month Flash trial has completed; [verification evidence](docs/VERIFICATION.md) records its validation limits and the separate regional/storage trial. Mocked/offline tests alone do not establish live narrative quality, reliability or speed.

Long live jobs can outlast the frontend's roughly two-minute polling window. Retry Start analysis with the same session to retrieve/resume the same operation. Restarted or partially failed runs preserve completed months. A call interrupted before its checkpoint may be repeated; its remote usage is unknown. Use a single server process per data directory.

Backend replay remains available independently of the inherited panel layout: `GET /api/state` returns the selected overview and its `timeline`; `POST /api/seek` with `{"month": <timeline month>}` selects a saved moment, and `POST /api/switch` with `{"id": "<simulationId>"}` selects that run's latest saved moment. These overview month numbers come from `timeline`; construction months in scenario files are one-based. No legacy intervention changes the narrative engine's script.

## Verification and design notes

- [Verification evidence](docs/VERIFICATION.md)
- [Actual frontend compatibility](docs/COMPATIBILITY.md)
- [Model defaults and monthly ordering](docs/PLAN.md)
- [AI adapter and live commands](docs/AI.md)
- [Independent review](docs/REVIEW.md)
- [Storage format, compatibility and measurements](docs/STORAGE.md)

The existing private-research context is retained; no original material has been published or relicensed. Existing frontend and Three.js notices are untouched. This is an exploratory sandbox, not a validated forecast. Preset firm GDP mechanically rewards more/larger firms and is not a standalone measure of strategy success.
