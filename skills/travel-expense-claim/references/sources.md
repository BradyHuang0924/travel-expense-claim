# The five sources

All five are fetched over the network on every run. Nothing is served from a cache; a
gate failure stops the run rather than falling back to a retained copy.

| id | locator | gate |
|---|---|---|
| `policy` | `POST notion.site/api/v3/loadPageChunk`, page `3d80b700-541e-81ed-93eb-d386abc1dcb0` | title carries `POL-`, at least one content block, not the SPA shell |
| `binder.*` | `drive.google.com/uc?export=download&id=<id>` | bytes start `%PDF`, footer carries `SRC-D-3` |
| `registers.*` | `docs.google.com/spreadsheets/d/<id>/gviz/tq?tqx=out:csv&sheet=<tab>` | body is CSV not HTML, banner carries `SRC-D-3` |

## Why the policy needs the API

A plain `GET` of the Notion page returns HTTP 200 and about 20 KB of application shell.
Its only readable text is "JavaScript must be enabled in order to use Notion" -- zero
characters of policy. The page content exists only behind the public `loadPageChunk`
endpoint, so that is the access path.

It is still a fresh read: an unauthenticated call to the live backend at run time,
returning the current `recordMap`. The payload carries the page's own `version` and
`last_edited_time`, both recorded in `sources.json` beside the SHA-256 of the response
bytes. An edit to the policy changes all three, so freshness is checkable rather than
asserted. The cursor is followed until its stack is empty, so a page longer than one
chunk is not silently truncated.

## Parsing traps

* Every register tab carries a human banner. On nine tabs it is folded into the first
  header cell; on `People` it occupies three whole rows before the header. Header
  detection is per tab -- the first row whose second cell is non-empty.
* Register cells hold ordered multi-values separated by newlines (`Source revisions`,
  `Affected fields`, `Review roles`, `Budget record references`).
* The PDF expense table extracts as one cell per line: six header names followed by
  repeating groups of six values.

## Versions, and the gap

Only the policy carries a version string (`POL-2026.2`). The four business sources stamp
package id `SRC-D-3` and no version, so `observed_version` is the SHA-256 of the retained
bytes. No version number is invented.

Two dangling references are recorded as package defects rather than resolved:

* **`DW-D-2`.** Every one of the 307 `Review ledger` rows cites source revisions
  `DW-D-2 / POL-2026.2 / SRC-D-3`. `POL-2026.2` and `SRC-D-3` resolve to real artifacts;
  `DW-D-2` appears in no other tab, no PDF and not in the policy page. It is the only
  occurrence of any `DW-` token anywhere in the five sources. Its column exists to carry
  the "relevant source versions" a reply was made against (block 6), which block 6 then
  uses to "reject wrong-role, stale-version or wrong-subject replies for current
  authorization" -- but the value is identical on all 307 rows across batches 1, 3 and 4
  and across both claim and permit subjects, so it cannot discriminate a stale reply from
  a current one.
* **The fixed source manifest.** Block 0 says "Read the fixed source manifest before each
  run." No such artifact is supplied.
