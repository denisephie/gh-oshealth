# processes all gh events from gharchive, but only for a fixed set of repos 
# single source of truth for which repos we track and category they belong to
# matching new events to canonical repo (if name changed) utilizing the id 

from __future__ import annotations 
from enum import StrEnum 
from pydantic import BaseModel, Field # basemodel to check types at construction, field to customize field behav

class Category(StrEnum): # for grouping/reporting
    ORCHESTRATION = "orchestration"
    TRANSFORMATION = "transformation"
    STORAGE = "storage"
    INGESTION = "ingestion"
    BI = "bi"

class Repo(BaseModel): #pydantic model for tracked repo
    model_config = {"frozen": True} # set immutable and hashable (repo obj lives in tuple/set as constants)
    full_name: str # owner/repo
    category: Category # ecosystem role
    repo_id: int | None = None # optional cos not backfilled from API
    aliases: frozenset[str] = Field(default_factory=frozenset) # former name of repos -> if not given default to empty frozenset

    @property # returns all owner/repo values prev and current
    def match_names(self) -> frozenset[str]:
        return self.aliases | {self.full_name}

WATCHLIST: tuple[Repo, ...] = ( # tuple of repo instances (hardcode what to filter)
    Repo(
        full_name="dbt-labs/dbt-core",
        category=Category.TRANSFORMATION,
        aliases=frozenset({"fishtown-analytics/dbt", "dbt-labs/dbt"}),
    ),
    Repo(full_name="apache/airflow", category=Category.ORCHESTRATION),
    Repo(
        full_name="dagster-io/dagster",
        category=Category.ORCHESTRATION,
        aliases=frozenset({"dagster-io/dagit"}),
    ),
    Repo(full_name="TobikoData/sqlmesh", category=Category.TRANSFORMATION),
    Repo(full_name="duckdb/duckdb", category=Category.STORAGE),
    Repo(full_name="apache/iceberg", category=Category.STORAGE),
    Repo(
        full_name="apache/superset",
        category=Category.BI,
        aliases=frozenset({"apache/incubator-superset"}),
    ),
    Repo(full_name="dlt-hub/dlt", category=Category.INGESTION),
    Repo(full_name="PrefectHQ/prefect", category=Category.ORCHESTRATION),
    Repo(full_name="apache/spark", category=Category.STORAGE),
)


WATCHLIST_NAMES: frozenset[str] = frozenset( # flatten watchlist into frozenset per name across all repos (check is this string in the watchlist w/o finding which repo it maps to)
    name for repo in WATCHLIST for name in repo.match_names
)

_BY_LOWER_NAME: dict[str, Repo] = { # private dict mapping lowercased name to repo
    name.lower(): repo for repo in WATCHLIST for name in repo.match_names
}

def resolve(repo_name: str) -> Repo | None: #look up owner/repo string from event (case insensitive) return matching repo or none
    return _BY_LOWER_NAME.get(repo_name.lower())

def matches(repo_name: str) -> bool: # boolean of the lookup above
    return repo_name.lower() in _BY_LOWER_NAME