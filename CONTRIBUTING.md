# Contributing

Thanks for your interest in improving the GP Desert Map! This is a small public-interest project;
contributions, bug reports, and data corrections are all welcome.

## Development setup

The system Python is often 3.14, which is too new for the geospatial wheels, so the project pins
**Python 3.12**.

```bash
brew install python@3.12 tippecanoe        # toolchain (macOS; on Linux use your package manager)
bash scripts/bootstrap.sh                  # creates .venv (3.12) and installs runtime requirements
. .venv/bin/activate
pip install -r requirements-dev.txt        # pytest + ruff for development
```

## Run it locally

```bash
python pipeline/run_all.py                 # fetch sources → parse → score → emit → build tiles
bash scripts/build_site.sh                 # assemble dist/
python scripts/serve.py 8080 dist          # Range-capable preview (http.server will NOT work)
# open http://localhost:8080
```

## Tests and linting

```bash
pytest          # unit tests (tests/) — fast, hermetic, no network
ruff check .    # lint + import sorting
```

Both run in CI on every push and pull request (`.github/workflows/tests.yml`); please make sure they
pass before opening a PR. Optionally install the git hook so this runs automatically:

```bash
pip install pre-commit && pre-commit install
```

## Guidelines

- Keep the pipeline's **build-time assertions** meaningful — if you change a data source or a parsing
  step, update the expected counts in `pipeline/lib/config.py` (`EXPECT`) and add/adjust a test.
- Add a unit test for any new pure logic (put reusable logic in `pipeline/lib/` so it's importable).
- **Never commit** anything under `raw/`, `interim/`, or `osrm/` (they are gitignored and can contain
  large files or personal data such as doctors' names — see below).
- Match the existing style: Hungarian in the user-facing UI, English in code/comments/docs (with
  Hungarian terms in *italics* + a gloss in the docs).
- See `SCHEMA.md` for the data contract between pipeline steps and the published GeoJSON.

## Data & privacy

The NEAK source files contain personal data (GP names, surgery addresses, phone numbers). The pipeline
deliberately keeps that data **out** of every committed/published artifact — outputs are aggregated by
settlement and district, never by named individual. Please preserve that boundary in any change.

By contributing you agree that your contributions are licensed under the project's MIT License.
