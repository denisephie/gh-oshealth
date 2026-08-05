before moving on to scripting: 

Landing zone schema and event selection
## Status
Accepted — 2026-08-05

## Context
* Github Archive events vary in types, and not all is relevant to the metrics that we want to monitor in this system
* Every event type has a different payload schema. GitHub has never published a
  stable spec for these, and fields have appeared and disappeared over the years.
* Malformed lines during parsing usually occur and this puts a dilemma whether we should flag it as failed, or just skip it

## Decision
* Select relevant Github events that contribute to the metrics: 
1. PullRequestEvent = time-to-merge, newcomer funnel
2. PullRequestReviewEvent = maintainer load, review concentration
3. IssuesEvent = time-to-first-response denominator
4. IssueCommentEvent = time-to-first-response numerator, newcomer funnel 
5. PushEvent = contributor retention, contribution volume
6. PullRequestReviewCommentEvent = maintainer load
7. CommitCommentEvent
8. CreateEvent
9. DeleteEvent
* The landing zone has a fixed nine-column schema taken from the stable event envelope: 
1. event_id 
2. event_type
3. actor_id
4. actor_login
5. repo_id
6. repo_name
7. created_at
8. payload_json
9. ingested_at

payload_json is stored as an opaque string (hidden from user). Typed columns are extracted in dbt staging using native JSON functions (DuckDB and BigQuery both support this)
* We can use percentage aggregates to determine the amount of lines that will be the amount benchmarked for flagging parse failures. However, it depends on the type of event and also the dataset size (e.g, for 1 billion lines, a fail rate of 0.05% (this is failed parses/total lines) looks fine, but when we materialize the numbers -> 500,000 events lost (no good). So:
1. 0 malformed = normal, no log
2. 1–9 malformed **and** under 0.01% = log a warning with the count, continue
3. 10 or more malformed **or** 0.01% or above = fail 


## Alternatives rejected
* Keeping all events; WatchEvent, ForkEvent, GollumEvent, MemberEvent, PublicEvent -> all are not relevant to the contribution metrics, only attention + admin
* Parse payload per typed models per event type -> too many Pydantic models, schema is also not published by Github (we cannot see payload, so we also won't know if a payload is changed by GH)
* Extract only chosen subsets of payload fields and dropping the rest -> keeping everything is still cheap, the discrepancy between chosing some and all is not big in terms of size so doing this is just tedious work
* Skip malformed lines and using purely the percentage of fail rates -> intuitively looks fine, but when materialized into numbers adds up to concern of skipping fractions of data

## Consequences
* The extractor is schema-agnostic. GitHub can change a payload that the extractor does not notice (opaque string). Only dbt staging needs updating.
* Adding a new field is a dbt model edit and a `dbt run`, and it re-parses history we already have. No re-fetch.
* Every column comes from a JSON extraction expression instead of a plain select, and a typo in a JSON path produces a NULL rather than an error. dbt tests on the staging layer are therefore not optional.
* payload_json is stored per row and does not compress as well as typed columns would. 
* Wanting an excluded event type later means re-fetching that window. Accepted, the exclusion list is short and stable.
* The malformed thresholds are not set until we have observed real files. They should be revisited once we have a few hundred hours of counts.
* Per-event-type validation is not handled here. It belongs in dbt staging tests where rows are already parsed with known types.
