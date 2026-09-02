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

import httpx  # iter_bytes, client, timeout, client.stream, raise for status, status code

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
# decompresses a continuous stream of data per chunk, outputting as they are available without loading everyth all at once


def _decompress(chunks: Iterable[bytes]) -> Iterator[bytes]:
    decompressor = zlib.decompressobj(
        GZIP_WBITS
    )  # creates a decompression obj for streaming data (process data in sequential chunks)
    for chunk in chunks:
        while chunk:  # keep working on this lump until nothing left (while chunk has bytes in it)
            data = decompressor.decompress(chunk)  # decompress to original size
            if data:
                yield data  # if hv something pass it along, if no input no need
            if not decompressor.eof:  # if not end of, get back to for loop to fetch
                break
            # whole lump is finished
            chunk = decompressor.unused_data  # unused belongs to next lump
            decompressor = zlib.decompressobj(GZIP_WBITS)
    tail = decompressor.flush()  # tells decompressor that no more input is coming, so emit anything held, if not it will keep waiting for data
    if tail:  # tail not empty (not b"")
        yield tail  # send out the non-empty


# 4 - takes an hr from gharchive (input = UTC hour) and hands back HourResult
# note: we cant js download, load, filter, file too big!
# HourResult will come back with one of the 4 statuses


def fetch_hour(  # inputs
    hour: datetime,
    *,  # everyth after * which is now and client must be by keyword (passed by name like now = A, client = B)
    now: datetime | None = None,
    client: httpx.Client | None = None,
) -> HourResult:
    started = time.monotonic()  # stopwatch started

    if hour.tzinfo is None:
        raise ValueError("hour must be timezone-aware!")

    url = hour_url(hour)

    if not is_expected_available(hour, now=now):  # for the logs that are not yet published
        return HourResult(
            hour=hour,
            status=Status.NOT_YET_PUBLISHED,
            url=url,
            events=[],
            lines_read=0,
            events_matched=0,
            lines_malformed=0,
            bytes_downloaded=0,
            duration_seconds=time.monotonic() - started,
        )

    lines_read = 0
    events_matched = 0
    lines_malformed = 0
    bytes_downloaded = 0
    events: list[dict] = []

    owns_client = (
        client is None
    )  # none = client empty = own_client true = nobody handed client, need to make one myself
    if owns_client:
        client = (
            httpx.Client()
        )  # httpx.Client makes web reqs, keeps connection open to server and reconnects

    timeout = httpx.Timeout(connect=CONNECT_TIMEOUT, read=READ_TIMEOUT, write=10.0, pool=10.0)
    # connect = server to pick up, read = wait for next chunk, write/pool = send data and wait for free connetion from pool
    try:
        with client.stream("GET", url, timeout=timeout) as response:  # reads header
            if response.status_code == 404:  # no file
                return HourResult(
                    hour=hour,
                    status=Status.MISSING,
                    url=url,
                    events=[],
                    lines_read=0,
                    events_matched=0,
                    lines_malformed=0,
                    bytes_downloaded=0,
                    duration_seconds=time.monotonic() - started,
                )
            response.raise_for_status()  # everything except 2xx

            def counted():  # to count for bytes downloaded BEFORE decompression cs by the time it reaches _decompress, alr inflate
                nonlocal bytes_downloaded  # for global
                for chunk in response.iter_bytes():
                    bytes_downloaded += len(chunk)
                    yield chunk  # yield for generator

            for line in _iter_lines(_decompress(counted())):
                # counted() -> compressed chunks counted
                # _decompress() -> chunk inflated to json
                # _iter_lines() -> reassembled to complete liens
                lines_read += 1
            print(f"lines read={lines_read}, bytes={bytes_downloaded}")
            return None  # placeholder

    finally:  # clean up as try block's way out
        if owns_client:
            client.close()  # close a self made client, don't close a borrowed one (next fetched hours will fail since connection pool cut off)
