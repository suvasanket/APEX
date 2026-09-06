"""Multi-Carrier Registry for Indian Domestic Direct Airline Carriers (Non-OTAs)."""

from typing import Optional

from pydantic import BaseModel, ConfigDict

from apex.collectors.airindia import AirIndiaCollector
from apex.collectors.airindia_express import AirIndiaExpressCollector
from apex.collectors.akasa import AkasaCollector
from apex.collectors.base import BaseCollector
from apex.collectors.indigo import IndiGoCollector
from apex.collectors.spicejet import SpiceJetCollector


class CarrierMetadata(BaseModel):
    """Metadata describing a direct Indian domestic airline operator."""

    model_config = ConfigDict(frozen=True)

    iata_code: str
    name: str
    parent_group: str
    portal_url: str
    source_code: str
    market_share_approx: float


DOMESTIC_CARRIERS: dict[str, CarrierMetadata] = {
    "6E": CarrierMetadata(
        iata_code="6E",
        name="IndiGo",
        parent_group="InterGlobe Aviation",
        portal_url="https://www.goindigo.in",
        source_code="indigo_direct",
        market_share_approx=0.62,
    ),
    "AI": CarrierMetadata(
        iata_code="AI",
        name="Air India",
        parent_group="Tata Group",
        portal_url="https://www.airindia.com",
        source_code="airindia_direct",
        market_share_approx=0.14,
    ),
    "IX": CarrierMetadata(
        iata_code="IX",
        name="Air India Express",
        parent_group="Tata Group",
        portal_url="https://www.airindiaexpress.com",
        source_code="airindia_express_direct",
        market_share_approx=0.06,
    ),
    "QP": CarrierMetadata(
        iata_code="QP",
        name="Akasa Air",
        parent_group="SNV Aviation",
        portal_url="https://www.akasaair.com",
        source_code="akasa_direct",
        market_share_approx=0.05,
    ),
    "SG": CarrierMetadata(
        iata_code="SG",
        name="SpiceJet",
        parent_group="SpiceJet Ltd",
        portal_url="https://www.spicejet.com",
        source_code="spicejet_direct",
        market_share_approx=0.03,
    ),
}

COLLECTOR_FACTORIES = {
    "6E": IndiGoCollector,
    "AI": AirIndiaCollector,
    "IX": AirIndiaExpressCollector,
    "QP": AkasaCollector,
    "SG": SpiceJetCollector,
}


def get_supported_carriers() -> list[CarrierMetadata]:
    """Return list of all supported direct airline carriers."""
    return list(DOMESTIC_CARRIERS.values())


def resolve_carrier_code(query: str) -> str:
    """Resolve query (IATA or airline name) to canonical 2-letter IATA code."""
    q = query.strip().upper()
    if q in DOMESTIC_CARRIERS:
        return q
    for code, meta in DOMESTIC_CARRIERS.items():
        if q == meta.name.upper() or q in meta.name.upper():
            return code
    raise KeyError(f"Unknown domestic airline carrier: '{query}'")


def get_carrier_metadata(query: str) -> CarrierMetadata:
    """Fetch metadata for a given carrier code or name."""
    code = resolve_carrier_code(query)
    return DOMESTIC_CARRIERS[code]


def create_carrier_collector(query: str) -> BaseCollector:
    """Instantiate a collector for the given carrier code or name."""
    code = resolve_carrier_code(query)
    factory = COLLECTOR_FACTORIES[code]
    return factory()


def get_all_carrier_collectors() -> dict[str, BaseCollector]:
    """Instantiate collectors for all 5 scheduled direct domestic carriers."""
    return {code: factory() for code, factory in COLLECTOR_FACTORIES.items()}
