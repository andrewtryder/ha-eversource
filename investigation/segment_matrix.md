# Eversource public segment matrix

The public location-selector configuration embedded in Eversource's server-rendered page lists `ct`, `ema`, `egma`, `wma`, and `nh`. This is first-party UI evidence, not a brute-force discovery method. Only NH has been fetched, parsed, fixture-tested, and exposed by this integration.

| User-visible territory | Segment | Residential electric service | Supply page works | Delivery page works | Rate classes | Notes |
|---|---|---:|---:|---:|---|---|
| New Hampshire | `nh` | yes | yes | yes | R | Verified production target; Public Service of New Hampshire. |
| Connecticut | `ct` | yes | unverified | unverified | unverified | First-party location selector lists Connecticut Light & Power; not supported. |
| Massachusetts EMA/EMA | `ema` | yes | unverified | unverified | unverified | Eastern Massachusetts Electric; distinct MA territory. |
| Massachusetts EGMA/EMA | `egma` | yes | unverified | unverified | unverified | Gas/Electric selector variant; not supported. |
| Massachusetts EGMA/WMA | `wma` | yes | unverified | unverified | unverified | Western Massachusetts; distinct MA territory. |

The unverified values are documented for future investigation only and are intentionally absent from `TERRITORIES` and `tools/probe_segments.py`.
