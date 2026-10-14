# Retrieving the rest by hand

**14 October 2026.** Lessons from retrieving 150 full texts for our benchmark (1 Oct 2026). Work through `status.csv` rows where `status` is `needs_manual`: open `manual_url`, and `backup_url` if that fails.

## Rules we kept

- **Never accept a terms-of-use, licence or consent page, and never solve a CAPTCHA, on someone else's behalf** (e.g. ScienceDirect or Project MUSE asking for an attribute release). A person with the access rights decides. If they don't, count the paper as unobtainable and record why. That record is your PRISMA "reports not retrieved" figure.
- Checks that clear themselves (PMC's check, Cloudflare's "Just a moment") are fine to wait out.
- Keep one log line per unobtainable paper with the reason: subscription not held, conference abstract only, grey literature not found, CAPTCHA, and so on.

## Source-by-source notes

| Source | What works |
|---|---|
| **PMC** (papers outside the open-access subset) | In a browser, PMC's check passes on its own. After that, about 20 PDFs can be fetched from the same page before it triggers again. Scripts get 403 or a bot check. |
| **Europe PMC** | Its render link works in a browser tab; scripts get 403. Many PDFs can be fetched in one tab and saved as a single zip. |
| **Elsevier / ScienceDirect** | Needs institutional login. Plain VPN IPs are often not recognised, so go through the proxy (OpenAthens). It may show a CAPTCHA (see the rules above). Downloaded files are named `1-s2.0-<PII>-main.pdf`, and the PII identifies the paper, which makes renaming easy. |
| **Lippincott / Wolters Kluwer** | These journals are now on ovid.com. Open the DOI directly; once the proxy session is set, it persists. Take the `/pdf/` link. |
| **Wiley, Taylor & Francis, SAGE** | Script requests get 403. In a logged-in browser the PDF link works. |
| **LILACS / SciELO** | The LILACS "Fulltext URL" usually points to SciELO, which is open. Pass it as `--url-col` so the script tries it first. Theses and grey literature often have no file. |
| **No DOI** | Search the exact title in Google Scholar (`backup_url`) and look for a repository copy. |

## Browser practicalities

- Chrome allows only one automatic download per tab. To fetch many PDFs, open a few fresh tabs, fetch each PDF from the article page, and close the old tabs.
- A reference manager browser extension (e.g. Zotero) may intercept PDF and RIS downloads. Pause it while downloading.
- Downloads can stall behind a "keep / discard" or permission prompt you can't see. Check the downloads bar.

## Getting the files into MetaScreener

Rename each manually downloaded file to the paper's title (the `title` column in `status.csv`), or anything close to it. Then put it in the same `pdfs/` folder and upload that folder together with the original CSV on Screen Fields. Files named this way are matched on title; a publisher name like `1-s2.0-S0277…-main.pdf` will only match if the PDF's own metadata carries the title or DOI.
