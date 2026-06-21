$ErrorActionPreference = "Stop"
python -m ruff check geoifcassets tests
python -m mypy geoifcassets
