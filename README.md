# Time Zone Tabulator

Finds IANA time zones that match a given UTC offset and current daylight-saving status.

```python
from datetime import datetime
from time_zone_tabulator import TimeZoneTabulator

t = TimeZoneTabulator(now=datetime(2024, 7, 15, 12, 0, 0))
for m in t.find(-240, dst_active=True):
    print(m.name, m.utc_offset, m.dst_active)
```

`TimeZoneTabulator(now=None)` takes an optional `datetime` at which offsets and DST flags are evaluated. If `now` is omitted, the current instant is captured once at construction time. `find(utc_offset_minutes, dst_active)` returns a list of `ZoneMatch(name, utc_offset, dst_active)`, sorted by zone name. Offsets are whole minutes, east of UTC positive; `Asia/Kolkata` at UTC+5:30 is `330`.

## Why this exists

The problem is narrow: given an offset and a DST flag observed at a specific instant, which IANA zones could produce that combination? This comes up when correlating a raw offset (say, from a log line or a user agent) against named zones without pulling in a heavier database.

The trade-off is that the answer is instant-specific. A zone's offset and DST status change across the year, so the tabulator judges each zone solely at the instant you give it. It does not try to describe a zone's "standard" offset separately from its DST offset, because that distinction is fuzzy for zones with permanent DST or historical transitions. If you need a zone's long-term behaviour, this is the wrong tool.

## Awkward edge

`zoneinfo.available_timezones()` includes alias entries and, on some platforms, names that cannot actually be constructed. The tabulator deduplicates names and silently skips any zone that raises during construction, so the output is stable but may not include every name the platform lists. Offsets are reported in whole minutes; every real IANA zone in the modern database resolves to a whole-minute offset, so nothing is lost.
