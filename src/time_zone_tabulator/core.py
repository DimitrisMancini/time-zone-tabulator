from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, tzinfo, timedelta
import zoneinfo


@dataclass(frozen=True)
class ZoneMatch:
    """A time zone that satisfied a query.

    Attributes:
        name: IANA zone identifier (e.g. ``"America/New_York"``).
        utc_offset: The zone's offset from UTC at the queried instant, in
            minutes. East of UTC is positive. Minutes are used so zones
            such as ``Asia/Kolkata`` (UTC+5:30) are represented exactly.
        dst_active: ``True`` if daylight saving time was in effect at the
            queried instant, ``False`` otherwise.
    """

    name: str
    utc_offset: int
    dst_active: bool


class TimeZoneTabulator:
    """Find IANA time zones matching a UTC offset and DST status.

    The class iterates over every zone name exposed by
    :mod:`zoneinfo` (via :data:`zoneinfo.available_timezones`) and asks each
    zone for its offset and DST flag at a single instant. That instant is
    supplied by a clock function passed to the constructor, which keeps the
    class fully deterministic and testable: tests inject a fixed clock and
    never touch the wall clock.

    Interpretation decisions (stated plainly so the behaviour is predictable):

    * **Offset is measured at the query instant.** A zone whose offset
      changes across the year is judged solely by where it sits at that
      instant. We do not try to characterise a zone's "standard" offset
      separately from its DST offset, because that distinction is fuzzy for
      zones with permanent DST or historical transitions.
    * **Offset is reported in whole minutes.** Every real IANA zone in the
      modern database resolves to a whole-minute offset, so no precision is
      lost. Fractional minutes are not supported.
    * **DST is whatever the zone says.** ``dst()`` returning a non-zero
      timedelta counts as DST active; ``None`` or a zero-duration timedelta
      counts as inactive. Some zones return a zero timedelta rather than
      ``None`` when DST is not in effect, so both are treated as inactive.
    * **Duplicate zone names are deduplicated.** :data:`zoneinfo.available_timezones`
      occasionally contains alias entries that resolve to the same key; we
      sort and de-duplicate so output is stable.
    * **Unresolvable zones are skipped.** A handful of entries in
      :data:`zoneinfo.available_timezones` can raise on some platforms when
      constructed. They are silently omitted rather than aborting the query,
      because the purpose is tabulation, not exhaustive validation.
    """

    def __init__(self, now: "datetime | None" = None) -> None:
        """Create a tabulator.

        Args:
            now: The instant at which offsets and DST status are evaluated.
                If omitted, :func:`datetime.now` with no timezone is captured
                once at construction time. Capturing eagerly (rather than
                calling ``now`` per query) means repeated queries against the
                same tabulator are consistent with each other, which matters
                for callers that compare several offsets in a loop.
        """
        if now is None:
            now = datetime.now()
        self._now = now

    def find(
        self,
        utc_offset_minutes: int,
        dst_active: bool,
    ) -> list[ZoneMatch]:
        """Return zones whose offset and DST flag match at the query instant.

        Args:
            utc_offset_minutes: Desired UTC offset in minutes. East is positive.
                For example, UTC+5:30 is ``330`` and UTC-8:00 is ``-480``.
            dst_active: Desired DST flag.

        Returns:
            A list of :class:`ZoneMatch`, sorted by zone name. The list is
            empty if no zone matches. Sorting by name makes the output
            deterministic across runs and platforms, which matters for tests
            and for callers diffing results.
        """
        matches: list[ZoneMatch] = []
        seen_names: set[str] = set()

        # available_timezones returns a set; iterating over a sorted copy
        # gives reproducible behaviour even before the final sort, and makes
        # early-skip debugging easier.
        for name in sorted(zoneinfo.available_timezones()):
            if name in seen_names:
                continue
            seen_names.add(name)

            info = self._zone_info(name)
            if info is None:
                continue

            offset, dst = info
            if offset == utc_offset_minutes and dst == dst_active:
                matches.append(
                    ZoneMatch(name=name, utc_offset=offset, dst_active=dst)
                )

        matches.sort(key=lambda m: m.name)
        return matches

    def _zone_info(self, name: str) -> "tuple[int, bool] | None":
        """Return ``(utc_offset_minutes, dst_active)`` for *name*, or ``None``.

        ``None`` means the zone could not be constructed or interrogated.
        This is deliberately broad: the point of the tabulator is to answer
        queries, not to diagnose broken zone data on a given platform.
        """
        try:
            tz = zoneinfo.ZoneInfo(name)
        except Exception:
            # ZoneInfo raises KeyError for unknown keys, but on some
            # platforms construction can raise other errors for entries
            # that exist in the list but cannot be loaded. Treat all of
            # these as "unavailable" and move on.
            return None

        dt = self._now.replace(tzinfo=tz)
        offset_td: timedelta | None = dt.utcoffset()
        dst_td: timedelta | None = dt.dst()

        # utcoffset() is None for 'nominal' datetimes, which should not
        # happen here because we attached a tzinfo, but guard anyway.
        if offset_td is None:
            return None

        total_minutes = int(offset_td.total_seconds() // 60)
        # dst() returns None when DST is not in effect, but some zones
        # return a zero timedelta instead. Treat both as inactive.
        dst = dst_td is not None and dst_td != timedelta(0)
        return total_minutes, dst
