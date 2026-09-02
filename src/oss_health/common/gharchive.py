# gh archive publishes one gzipped json file/utc hour (note: hour not zero-padded -> no 09 just 9, days and month are tho)
# all funcs

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

BASE_URL = "https://data.gharchive.org"
PUBLISH_LAG = timedelta(
    hours=2
)  # 2 hr buffer for file to exist (to clear misconception abt file uploaded/not and error)


def hour_url(dt: datetime) -> str:  # download URL for whatever UTC hour dt falls in
    if dt.tzinfo is None:  # rejects naive (no timezone)
        raise ValueError("hour_url requires a timezone-aware datetime")
    dt_utc = dt.astimezone(UTC)  # convert to utc
    return f"{BASE_URL}/{dt_utc:%Y-%m-%d}-{dt_utc.hour}.json.gz"  # format url to date time, hour is just int (no zero pads)


def hour_range(
    start: datetime, end: datetime
) -> Iterator[datetime]:  # yield start to end utc hour (both inclusive)
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("hour_range requires timezone-aware datetimes")
    cursor = start.astimezone(UTC).replace(
        minute=0, second=0, microsecond=0
    )  # truncate bounds down to top of hr (00:45 treated as the hour of 00:00)
    stop = end.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    if stop < cursor:  # error for end preceeding start time
        raise ValueError(f"end ({end}) precedes start ({start})")
    while cursor <= stop:
        yield cursor
        cursor += timedelta(hours=1)  # one hr at a time, yield each one


def is_expected_available(
    dt: datetime, *, now: datetime | None = None
) -> bool:  # shd this hour's file exist now, distinguishing unpublished and 404
    reference = now if now is not None else datetime.now(UTC)
    return dt.astimezone(UTC) <= reference - PUBLISH_LAG
