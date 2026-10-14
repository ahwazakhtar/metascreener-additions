# metascreener-additions

**Version 0.1 · 14 October 2026 · draft, not yet validated**

Additions to [MetaScreener](https://github.com/Sautmann/MetaScreener) from the systematic review *Effectiveness of Quality-Improvement Interventions on Quality of Care in Primary Care in Low- and Middle-Income Countries* (World Bank partnership). Contact: ajafri@bu.edu.

There are two parts:

1. **Full-text screening fields** (`fields/`). A custom-fields JSON for the Screen Fields page, adapted from our title/abstract fields.
2. **A PDF fetcher** (`fetch/`). It downloads the open-access PDFs for a list of records, names them so MetaScreener can match them to the CSV, and lists the rest with a link to open by hand.

## 1. Full-text fields

| File | What it is |
|---|---|
| `fields/fulltext-custom-fields-v0.1.json` | **The file to load.** 24 fields: 8 eligibility answers (Yes / No / Maybe), 8 justifications, and 8 `_Section` fields giving where in the paper each answer comes from. |
| `fields/titleabstract-custom-fields-v1.6.json` | The title/abstract fields we screened 35,867 records with (29 Sep 2026). Included for comparison. |
| `fields/fulltext-system-prompt-v0.1.txt` | The full prompt the full-text fields were taken from, as sent directly to the API in our benchmark. |
| `fields/CHANGES.md` | What differs from title/abstract, and why. |

Load it on **Screen Fields → custom fields → upload**. Field names match the title/abstract names, so the two runs can be joined on them.

**Status:**
- **Not validated yet.** We are running a 150-paper benchmark (gpt-6-luna against one blind human reviewer). The LLM side is done (150/150 valid replies); the human coding is in progress. Agreement figures will be added here when it is finished.
- **The benchmark did not go through MetaScreener.** It sent each PDF to the Chat Completions API as a file (the model sees the text and the page images). MetaScreener extracts the text with PDF.js, so tables and figures arrive as flattened text. Results may differ, most likely on fields answered from tables.
- **Not yet run in the MetaScreener UI.** The JSON uses exactly the structure of our title/abstract file, which does load. The full-text version itself has not been loaded or run in the app.
- **No full-text decision rule yet.** How the eight answers combine into include/exclude at full text will be set after the benchmark.

## 2. PDF fetcher

```
python fetch/fetch_fulltext.py records.csv --email you@university.edu --out fulltext --id-col RecordID
```

Only the Python standard library is needed (3.9+). The input is any CSV with a title column and, where available, `DOI` and `PMID` columns; all column names can be set with flags. The results go to `fulltext/`:
- `pdfs/` holds the downloaded files.
- `status.csv` has one row per record. Each row has `status` (`ok` or `needs_manual`), the source used, and, for anything not downloaded, a `manual_url` and `backup_url` to open by hand.

Sources, in the order tried:
1. **PMC open-access subset**, from NCBI's AWS open-data bucket (`pmc-oa-opendata`). The PMC ID comes from the PMID via E-utilities.
2. **Europe PMC render.** This usually returns 403 to scripts but costs nothing to try.
3. **OpenAlex**: the best open-access PDF, then every other PDF link it lists.
4. **An optional extra URL column** (`--url-col`), e.g. the LILACS "Fulltext URL", which often points to SciELO.

A file is kept only if it is really a PDF (it starts with `%PDF`).

Useful flags:
- `--proxy "<prefix>"` wraps DOI links for manual retrieval in your library proxy, e.g. an OpenAthens redirector: `https://go.openathens.net/redirector/<institution>?url=`.
- `--stamp` (needs `pip install pypdf`) writes the CSV title into each PDF's Title metadata.
- `--limit N` runs only the first N records, for testing.

**Matching in MetaScreener:** Screen Fields matches uploaded PDFs to CSV rows in this order:
1. A DOI in the PDF metadata.
2. A title in the PDF metadata (similarity above 0.6).
3. The filename against the CSV title (similarity above 0.5).

The fetcher names each file after the record's title, cut to 140 characters, so the third rule works even when a publisher's PDF has no usable metadata. `--stamp` makes the second rule match exactly. Use the same CSV for fetching and for screening.

**Expected yield:** on our 150-paper benchmark sample (14 Oct 2026) the script downloaded **57 of 150 (38%)**: 47 from the PMC bucket (of 66 papers with a PMC ID) and 10 from OpenAlex links. The rest needed a browser: subscriptions through the library proxy, publisher bot checks (Wiley and others return 403 to scripts), and grey literature. Our sample is LMIC health literature with many LILACS records, so other topics will see different rates. `fetch/MANUAL-RETRIEVAL.md` collects what we learned. Re-running is safe: files already downloaded are skipped, and API replies are cached in `<out>/api-cache.json`.

`examples/sample-input.csv` holds 6 records from our corpus covering each route: two from PMC, two open access, one closed access, and one with no DOI. On 14 Oct 2026 the script downloaded 3 of the 6.

## Licence

Code: MIT (`LICENSE`). Field and prompt text (`fields/`): CC BY 4.0.
