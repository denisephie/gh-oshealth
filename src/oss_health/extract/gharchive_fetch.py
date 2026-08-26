# 1 - constants and enums

import time
import zlib  # zlib can compress and decompress
from collections.abc import (
    Iterable,
    Iterator,
)  # to add type hints to a function that returns an iterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

import httpx

from oss_health.common.gharchive import hour_url, is_expected_available

# kept event_types (frozenset = immutable)
# not kept: WatchEvent, ForkEvent, GollumEvent, MemberEvent, PublicEvent -> not relevant to metric
# note: caps notation for constants that shd nvr change

TRACKED_EVENT_TYPES = frozenset(
    [
        "PullRequestEvent",
        "PullRequestReviewEvent",
        "IssuesEvent",
        "IssueCommentEvent",
        "PushEvent",
        "PullRequestReviewCommentEvent",
        "CommitCommentEvent",
        "CreateEvent",
        "DeleteEvent",
    ]
)

ABSOLUTE_THRESHOLD = 10  # fail the hour at this many badly parsed lines
FRACTION_THRESHOLD = 0.0001  # fail the hour above this rate of failures, 0.01%

"""
absolute threshold and fraction threshold will be the benchmark of flagging a "FAIL" during line parsing
condition to be passed shd be if the fail is under the absolute threshold AND fraction threshold  
"""

CONNECT_TIMEOUT = 10  # secs, wait time for TCP connection to open
READ_TIMEOUT = 60  # secs, wait time per chunk received
GZIP_WBITS = (
    16 + zlib.MAX_WBITS
)  # max windowbits = 15, adding 16 makes it 31 that falls into the window of gzip


class Status(StrEnum):
    FETCHED = "fetched"  # proceed
    NOT_YET_PUBLISHED = "not_yet_published"  # retry later
    MISSING = "missing"  # missing
    FAILED = "failed"  # retry now


@dataclass(frozen=True)
class HourResult:
    hour: datetime
    status: Status
    lines_read: int
    events_matched: int
    lines_malformed: int
    bytes_downloaded: int
    duration_seconds: float
    url: str
    error: str | None = None  # error can hold str or none
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def malformed_rate(self) -> float:
        if self.lines_read == 0:
            return 0.0
        else:
            return self.lines_malformed / self.lines_read

    @property
    def is_usable(self) -> bool:
        if self.status is Status.FETCHED:
            return True
        else:
            return False


# 2 - line reassembly -> bcs gzip doesn't actually split per line for every chunk


def _iter_lines(chunks):  # parameter is the chunks arriving (in bytes)
    buffer = b""  # byte literal = instance of bytes type
    for chunk in chunks:
        buffer += chunk  # add per chunk of bytes into buffer
        parts = buffer.split(b"\n")  # returns list of b"xx", b"yy", etc
        buffer = parts[
            -1
        ]  # reassignment of buffer to hold the part after \n split that is going to be reassembled in the next iteration
        for part in parts[:-1]:  # exclusive of the last (reassigned buffer)
            yield part
    if buffer:  # if the buffer still contains remaining unfinished chunks, hold it
        yield buffer


# 3 - decompresser -> takes compressed gzip chunks, yield decompressed bytes


def _decompress(chunks: Iterable[bytes]) -> Iterator[bytes]:
    decompressor = zlib.decompressobj(
        GZIP_WBITS
    )  # creates a decompression obj for streaming data (process data in sequential chunks)
    for chunk in chunks:
        data = decompressor.decompress(chunk)  # decompress to original size
        if data:
            yield data  # if hv something pass it along, if no input no need
    tail = decompressor.flush()  # tells decompressor that no more input is coming, so emit anything held, if not it will keep waiting for data
    if tail:  # tail not empty (not b"")
        yield tail  # send out the non-empty


# 4 - takes an hr from gharchive, and filter events


def fetch_hour(
    hour: datetime,
    *,  # now and client to be passed by name
    now: datetime | None = None,
    client: httpx.Client | None = None,
) -> HourResult:
    started = time.monotonic()  # elapsed time (stopwatch-ish?)
    if hour.tzinfo is None:
        raise ValueError("fetch_hour requires a timezone-aware datetime")
    url = hour_url(hour)
    if not is_expected_available(hour, now=now):  # for unpublished
        return HourResult(
            hour=hour,
            status=Status.NOT_YET_PUBLISHED,
            lines_read=0,
            events_matched=0,
            lines_malformed=0,
            bytes_downloaded=0,
            duration_seconds=time.monotonic() - started,
            url=url,
            error=None,
            events=[],
        )
    return None  # temporary, replaced in Sitting 2
