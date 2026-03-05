from __future__ import annotations

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    # PostgreSQL
    database_url: str = field(
        default_factory=lambda: os.environ.get(
            "DATABASE_URL",
            "postgresql://rcf:rcf@localhost:5432/rcf",
        )
    )

    # Anthropic
    anthropic_api_key: str = field(
        default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", "")
    )

    # External APIs
    iplan_arcgis_url: str = field(
        default_factory=lambda: os.environ.get(
            "IPLAN_ARCGIS_URL",
            "https://ags.iplan.gov.il/arcgisiplan/rest/services/PlanningPublic/Xplan/MapServer",
        )
    )
    mavat_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "MAVAT_BASE_URL", "https://mavat.iplan.gov.il"
        )
    )

    # Scanner tuning
    scanner_concurrency: int = field(
        default_factory=lambda: int(os.environ.get("SCANNER_CONCURRENCY", "5"))
    )
    retry_attempts: int = field(
        default_factory=lambda: int(os.environ.get("SCANNER_RETRY_ATTEMPTS", "3"))
    )
    classifier_confidence_threshold: float = field(
        default_factory=lambda: float(
            os.environ.get("CLASSIFIER_CONFIDENCE_THRESHOLD", "0.7")
        )
    )

    # Address ingestion — CBS data.gov.il CKAN API
    ckan_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "CKAN_BASE_URL",
            "https://data.gov.il/api/3/action/datastore_search",
        )
    )
    ckan_streets_resource_id: str = field(
        default_factory=lambda: os.environ.get(
            "CKAN_STREETS_RESOURCE_ID",
            "9ad3862c-8391-4b2f-84a4-2d4c68625f4b",
        )
    )
    ckan_cities_resource_id: str = field(
        default_factory=lambda: os.environ.get(
            "CKAN_CITIES_RESOURCE_ID",
            "5c78e9fa-c2e2-4771-93ff-7f400a12f7ba",
        )
    )
    ckan_page_size: int = field(
        default_factory=lambda: int(os.environ.get("CKAN_PAGE_SIZE", "1000"))
    )
    ingestion_max_house_number: int = field(
        default_factory=lambda: int(
            os.environ.get("INGESTION_MAX_HOUSE_NUMBER", "100")
        )
    )
    ingestion_house_number_step: int = field(
        default_factory=lambda: int(
            os.environ.get("INGESTION_HOUSE_NUMBER_STEP", "1")
        )
    )
    ingestion_batch_size: int = field(
        default_factory=lambda: int(
            os.environ.get("INGESTION_BATCH_SIZE", "500")
        )
    )


def get_config() -> Config:
    return Config()
