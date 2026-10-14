# Full-text fields v0.1: changes from title/abstract v1.6

**14 October 2026**

The full-text fields were written on 1 October 2026 and approved by the review's researcher the same day. They are taken from `fulltext-system-prompt-v0.1.txt`. The JSON uses exactly the same field instruction text, with two additions described under "What is added".

## Why the rules change

At title/abstract the rule was **sensitivity over specificity**: exclude only when the abstract positively states a disqualifying fact, because abstracts routinely leave out the country, the design and the measurement method. At full text that information should be there, so the rules are stricter.

## What changes

| | Title/abstract v1.6 | Full text v0.1 |
|---|---|---|
| Answers | Yes / No / Maybe / NotStated | Yes / No / Maybe. **NotStated is dropped.** |
| Maybe | "Not enough information in the abstract" | Only if the question is still unclear **after reading the full text**. |
| No | Only when the abstract affirmatively states a disqualifying fact | When the paper establishes it. |
| `RelevantOutcome` | Borderline outcomes (utilisation/coverage, patient adherence, provider attitudes, availability/stockouts, fidelity, cost) → Maybe | If those are the **only** outcomes reported → **No**. |
| `ControlledDesign` | Recorded only, never excludes | Answered against the Cochrane EPOC designs (RCT, cluster RCT, non-randomised controlled, controlled before-after, ITS). Uncontrolled before-after, descriptive, cross-sectional and qualitative designs → **No**. |
| `QI_Intervention` | — | A stand-alone measurement study that evaluates no intervention → **No** (protocol decision, 28 Sep 2026). A standardised patient used to *measure* the effect of a provider-side QI intervention is still Yes. |
| `NotVerticalScreening` | — | Unchanged in substance: life-stage populations (antenatal, maternity, child health, PMTCT within ANC) and tracer conditions inside general primary care are Yes. A dedicated disease clinic, including a multi-condition NCD clinic, is No. |

## What is added

1. **A full-text preamble in every decision field.** Each of the 8 decision instructions opens with: *"Answer from the FULL TEXT of the paper … where the abstract and the body of the paper differ, the body takes precedence."* In our direct-API prompt this sentence was in the system prompt. It is repeated per field here because:
   - in our checkout the Screen Fields system-prompt edit was not saved to the job (`systemPromptOverride`, issue reported earlier);
   - field instructions should not rely on text outside themselves.
2. **Eight `_Section` fields.** For each decision, where in the paper the supporting information appears, using the paper's own section labels ("2.3 Study setting", "Table 2"), up to three locations, or "Not reported". This is meant for the human check: a reviewer can go straight to the passage.

## Unchanged

- The field names. They match title/abstract, so the two runs can be joined.
- The justification fields. They ask for a quoted or paraphrased passage, plus the category the answer falls into.
- MetaScreener's built-in design/method taxonomy and flags.
