"""JSON configuration, validated instruments, and deduplicated universe selection."""
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class Instrument:
    id: str
    ticker: str
    name: str
    market: str
    currency: str
    benchmark: str


def load_universe(path: str | Path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    instruments = {}
    for key, item in config["instruments"].items():
        instrument = Instrument(id=key, **item)
        if instrument.market not in {"KR", "US"}:
            raise ValueError(f"Unsupported market: {key}")
        expected = "KRW" if instrument.market == "KR" else "USD"
        if instrument.currency != expected:
            raise ValueError(f"Currency mismatch: {key}")
        if instrument.market == "KR" and not (
            len(instrument.ticker) == 6 and instrument.ticker.isdigit()
        ):
            raise ValueError(f"KR ticker must be a six-character string: {key}")
        instruments[key] = instrument
    identities = [(i.market, i.ticker) for i in instruments.values()]
    if len(identities) != len(set(identities)):
        raise ValueError("Same security has multiple instrument IDs")
    for mega in config["themes"].values():
        for theme in mega["subthemes"].values():
            ids = theme["instruments"]
            if not ids or len(ids) != len(set(ids)):
                raise ValueError("Empty or duplicated subtheme basket")
            unknown = set(ids) - instruments.keys()
            if unknown:
                raise ValueError(f"Unmapped instruments: {unknown}")
    return config, instruments


def select(config, instruments, mega_id=None, subtheme_id=None):
    ids = set()
    megas = config["themes"]
    for mid, mega in megas.items():
        if mega_id is not None and mid != mega_id:
            continue
        for sid, sub in mega["subthemes"].items():
            if subtheme_id is None or sid == subtheme_id:
                ids.update(sub["instruments"])
    if not ids:
        raise ValueError("Selection has no instruments")
    return [instruments[key] for key in sorted(ids)]
