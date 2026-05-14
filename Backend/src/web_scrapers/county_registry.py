"""County scraper registry used by the frontend pipeline runner."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from pathlib import Path


_DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent / "output_data"


@dataclass(frozen=True)
class CountyScraper:
    key: str
    label: str
    module: str
    default_year: str = "2019"
    output_subdir: str | None = None


_COUNTIES: dict[str, CountyScraper] = {
    "sacramento": CountyScraper(
        key="sacramento",
        label="Sacramento County",
        module="src.web_scrapers.scraper_sacramento_county",
    ),
    "sonoma": CountyScraper(
        key="sonoma",
        label="Sonoma County",
        module="src.web_scrapers.scraper_sonoma_county",
        default_year="2021",
        output_subdir="sonoma",
    ),
}


def supported_counties() -> tuple[CountyScraper, ...]:
    return tuple(_COUNTIES.values())


def normalize_county_key(value: str | None) -> str:
    candidate = (value or "").strip().casefold()
    if not candidate:
        return "sacramento"
    for county in _COUNTIES.values():
        if candidate in {county.key.casefold(), county.label.casefold()}:
            return county.key
    return candidate


def get_county_scraper(value: str | None) -> CountyScraper:
    key = normalize_county_key(value)
    try:
        return _COUNTIES[key]
    except KeyError as exc:
        available = ", ".join(county.label for county in supported_counties())
        raise ValueError(f"Unsupported county scraper: {value or key}. Available: {available}") from exc


def scraper_output_root(environ=None) -> Path:
    environ = os.environ if environ is None else environ
    override = (environ.get("CONFLICT_SCRAPER_OUTPUT_DIR") or "").strip()
    return Path(override).expanduser().resolve() if override else _DEFAULT_OUTPUT_ROOT


def output_dir_for_county(value: str | None, year: str | int | None = None, *, output_root=None) -> Path:
    county = get_county_scraper(value)
    base = Path(output_root).expanduser().resolve() if output_root else scraper_output_root()
    if county.output_subdir:
        base = base / county.output_subdir
    scrape_year = str(year or county.default_year).strip() or county.default_year
    return base / scrape_year


def scrape_county(value: str | None, year: str | int | None = None) -> Path:
    county = get_county_scraper(value)
    scrape_year = str(year or county.default_year).strip() or county.default_year
    module = importlib.import_module(county.module)
    output_root = scraper_output_root()
    previous_output_root = os.environ.get("CONFLICT_SCRAPER_OUTPUT_DIR")
    if county.output_subdir:
        os.environ["CONFLICT_SCRAPER_OUTPUT_DIR"] = str(output_root / county.output_subdir)
    try:
        module.scrape(year=scrape_year)
    finally:
        if county.output_subdir:
            if previous_output_root is None:
                os.environ.pop("CONFLICT_SCRAPER_OUTPUT_DIR", None)
            else:
                os.environ["CONFLICT_SCRAPER_OUTPUT_DIR"] = previous_output_root
    return output_dir_for_county(county.key, scrape_year, output_root=output_root)
