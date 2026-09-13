# External source lookup recovery

The 13 September 2026 pipeline completed, but the server checkout contained the
uncommitted grammar-review feature, Homeric lookups timed out, and place-cluster
enrichment received Wikidata HTTP 429 responses.

## Repository updates

Keep the deployed feature, migration and schema snapshot committed together.
The daily update checks tracked and untracked files and uses a fast-forward-only
pull. A dirty checkout still blocks automatic updates so local work is preserved.
Before reconciling a deployment checkout, back up its pending files and compare
them with the intended commit. Do not discard live feature files to silence the
warning.

## Wikidata

`link_wikidata_places.py` supplies a contact URL in its User-Agent, paces every
outbound request, includes `maxlag=5` for Action API searches, and caches successful
responses within the process. Empty search results receive the same pacing.
HTTP 429/5xx, maxlag/rate-limit API errors, timeouts and connection failures use
bounded exponential backoff, respecting either form of `Retry-After`. A cooldown
longer than 60 seconds defers work; subsequent requests in that process retain
the cooldown. No retries are made before it expires.

Incomplete searches raise an error instead of becoming an empty candidate list.
New cluster extraction then rolls back and leaves the lemma eligible for retry.
For clusters already stored by an earlier run, retry only enrichment:

```sh
uv run extract_place_clusters.py --refresh-candidates --lemma-id 61075 --dry-run
uv run extract_place_clusters.py --refresh-candidates --lemma-id 61075
```

This path makes no model calls. It preserves original mentions, existing candidate
records and all human edits, and skips clusters changed during lookup. With no
lemma selected it defaults to three clusters lacking candidates. A completed
search may still find no suitable ancient place; that is an unresolved alignment,
not a network failure or an automatic identification.

See [Wikimedia API rate limits](https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits)
and [Action API etiquette](https://www.mediawiki.org/wiki/API:Etiquette).

## Homeric passages

The resolver first tries HTTPS Hopper with a bounded timeout. After a transport
failure, it avoids that host for the rest of the run. Successes and failures are
cached by passage so repeated citations do not repeat the same failed request.

The fallback is the official
[Perseus canonical-greekLit repository](https://github.com/PerseusDL/canonical-greekLit/tree/df7270e5df9c6e4e14c85a11a0a4b7f4a1a9f59e/data/tlg0012),
pinned at revision `df7270e5df9c6e4e14c85a11a0a4b7f4a1a9f59e`.
It validates the XML edition identifier and Murray translator attribution,
selects exactly the requested Greek book and line, and extracts the enclosing
English translation card. Notes and headings are excluded while inline text and
word boundaries are retained.

The fallback Greek edition is **perseus-grc2**, not Hopper's requested
**perseus-grc1**. Records retain the actual retrieved edition in `cts_urn`, the
requested URN in retrieval evidence, the Murray **perseus-eng3** source, the
translation card range, source URLs, repository revision and both file checksums.
The English card is context, not a line-aligned translation. Existing passage
rows are not refreshed unless explicitly requested with `--force`.

```sh
uv run resolve_homeric_source_passages.py --mention-id 3375 --dry-run
uv run python -m unittest test_pipeline_source_lookups test_place_cluster_extraction
```
