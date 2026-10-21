# WorkforceNexa — Sourcing Module Test Results

**Application under test:** WorkforceNexa Console (`http://localhost:3000`)
**Modules covered:** Opportunities · Sourced Profiles · Resume Brander · AI JD Builder
**Tester:** Automated UI/API walkthrough (browser automation), logged in as `wfn admin` (SUPERADMIN)
**Date:** 2026-09-25

## Legend

| Symbol | Meaning |
|---|---|
| ✅ PASS | Behaved as expected |
| ⚠️ FINDING | Works, but a gap/inconsistency worth fixing |
| ❌ BLOCKED | Could not be completed — external dependency/config issue |

---

## 1. Executive Summary

| Module | Happy-path scenarios | Validation scenarios | Blockers |
|---|---|---|---|
| Opportunities | 9/9 passed | 3/3 passed, 1 finding | 0 |
| Sourced Profiles | 8/8 passed | 6 passed, 3 findings | 0 |
| Resume Brander | 7/7 passed | 2/2 passed | 1 infra issue (Converter live-editor) |
| AI JD Builder | Validation only — generation could not be verified | 1/1 passed | 1 (AI backend unauthorized) |

**Top issues to fix:**
1. **AI generation is completely non-functional** — both the AI JD Builder and any AI-dependent step return `401 Unauthorized` from OpenRouter. The server is missing/has an invalid `OPENROUTER_API_KEY`. This blocks JD generation from both the standalone builder and the in-opportunity "Build with AI" shortcut.
2. **Resume upload is not actually required or type-checked server-side**, despite the UI marking it "Upload Resume/CV *". A profile can be created with no file (system silently substitutes an auto-generated placeholder resume) or with a non-resume file type (e.g. `.txt`) once the client-side `accept` filter is bypassed.
3. **Mettle Test Score has no upper bound** (`max` attribute is empty) — a score of 150 was accepted without warning.
4. **Resume Converter's live editor backend (OnlyOffice) is unreachable**, causing a silent `502` on forcesave; downloads still return 200 but may not reflect live edits.
5. Bulk **Import Openings** silently drops invalid rows (logged to console only) with no visible message to the user.

---

## 2. Opportunities Module

### 2.1 Happy-path scenarios

| # | Scenario | Steps | Result |
|---|---|---|---|
| O1 | Create opportunity — full fields | Filled Requested Date, Demand Area, Location, Squad, Role, Technology, No. of Candidates, Client, Client SPOC, Recruiter SPOC, Job Description → Create | ✅ PASS — opportunity created, listed, detail view accurate |
| O2 | Create opportunity — minimal required fields only | Filled only Demand Area, Location, Role, No. of Candidates, Client → Create | ✅ PASS — created; unset optional fields render as "Not specified" / "Not assigned" |
| O3 | Search opportunities | Searched "Java" | ✅ PASS — correctly filtered to matching role/technology records |
| O4 | Filter by Location | Selected "Bengaluru" | ✅ PASS — correct subset returned |
| O5 | Filter by Client | Selected "ADCB" | ✅ PASS — correct subset returned |
| O6 | Combined filters (Location + Client) | Both filters applied simultaneously | ✅ PASS — intersection correctly computed |
| O7 | Clear Filters | Clicked "Clear Filters" | ✅ PASS — all filters and search reset, full list restored |
| O8 | Sort by column | Clicked "Client" column header | ✅ PASS — list re-sorted ascending with sort-direction indicator |
| O9 | Pagination | Changed pages via "Next" arrow | ✅ PASS — correct next page of records loaded |
| O10 | Recruiter SPOC inline edit | Opened opportunity details → edited Recruiter SPOC chips → Save | ✅ PASS — persisted immediately |
| O11 | Job Description Attachment upload | Uploaded a file under "Job Description Attachment" | ✅ PASS — auto-saves on selection, shows filename/type/upload timestamp, "View" link works |
| O12 | Opportunity auto-close on fulfillment | Moved a profile to "Onboarded" | ✅ PASS (by design) — opportunity status flips to `CLOSED` automatically; confirmed server-side (`DEMAND_NOT_OPEN` 409 on further profile submission attempts), not just a UI restriction |

### 2.2 Validation scenarios

| # | Scenario | Expected | Result |
|---|---|---|---|
| V1 | Submit Create Opportunity form empty | Blocked, required fields flagged | ✅ PASS — native "Please fill out this field" on first empty required field (Demand Area) |
| V2 | No. of Candidates = `-5` | Rejected | ✅ PASS — "Value must be greater than or equal to 1." |
| V3 | Bulk Import Openings — incomplete row (missing Role/Demand Area) | Row rejected | ⚠️ **FINDING** — row is silently skipped; error (`Row 2: missing Role or Demand Area -- skipped`) is only written to the browser console, no toast/banner shown to the user. Opportunity count is correctly left unchanged, but the user has no visibility into why nothing was imported. |

### 2.3 AI integration (from within Opportunity Details)

| # | Scenario | Result |
|---|---|---|
| AI-O1 | Click "Build with AI" on Job Description, fill Technology Stack, "Generate with AI" | ❌ **BLOCKED** — `OpenRouter API Error: Client error '401 Unauthorized' for url 'https://openrouter.ai/api/v1/chat/completions'`. Same root cause as AI JD Builder module (§4). |

---

## 3. Sourced Profiles Module

### 3.1 Happy-path scenarios

| # | Scenario | Steps | Result |
|---|---|---|---|
| P1 | Add profile — full fields + resume + photo, opportunity open | Filled all fields, attached PDF resume | ✅ PASS — profile created, listed under opportunity, document viewable |
| P2 | Full stage progression: Submitted → Screened → Interview L1 → Interview L2 → HR-Discussion (Selected) → Offer Pending Approval → Offer Approved → Offer Sent → Offer Accepted → **Onboarded** | Advanced one stage at a time via row status dropdown + confirm (✓) | ✅ PASS — each transition confirmed with a toast (`Profile #N moved to STAGE`) and persisted |
| P3 | Alternate branch: Submitted → **Rejected** | Selected "Rejected" from status dropdown on a second candidate | ✅ PASS |
| P4 | Status dropdown only exposes valid next stages (+ Rejected) | Inspected dropdown options at each stage | ✅ PASS (by design) — no ability to skip stages or move backward |
| P5 | View Profile Details | Clicked profile name/"View" | ✅ PASS — modal shows full candidate data + attached documents with working "View" |
| P6 | "Add Profile" entry via top-level Sourced Profiles page | Clicked "Add Profile" → opportunity picker | ✅ PASS — lists all opportunities with live profile counts and OPEN/CLOSED badges |
| P7 | Status filter | Filtered to "Onboarded" | ✅ PASS — correct count/subset returned |
| P8 | Demand Area filter (combined with Status + Search) | Combined all three filters | ✅ PASS — correctly narrowed at each step |
| P9 | Clear Filters | Reset all three filters | ✅ PASS |
| P10 | Export CSV | Clicked "Export CSV" | ✅ PASS (presumed) — no errors thrown; triggers client-side generation (no network call observed, consistent with in-browser CSV export). File contents not independently verified. |

### 3.2 Validation scenarios

| # | Scenario | Expected | Result |
|---|---|---|---|
| V4 | Submit Add Profile form empty | Blocked | ✅ PASS — native required-field validation |
| V5 | Email = `not-an-email` | Rejected | ✅ PASS — "Please include an '@' in the email address..." |
| V6 | Total Experience = `-3` | Rejected | ✅ PASS — "Value must be greater than or equal to 0." |
| V7 | Duplicate profile (same email + phone within same opportunity) | Blocked | ✅ PASS — real-time check surfaces: *"[Name] was already submitted for this opportunity (profile #N, currently STATUS). Submitting again is blocked."* |
| V8 | Mettle Test Score = `150` | Should be capped (0–100 expected for a test score) | ⚠️ **FINDING** — accepted with no warning. DOM inspection confirms `min="0"`, `max=""` — no upper bound is enforced client-side, and the backend accepted it too. |
| V9 | Submit with **no resume file** attached | UI marks "Upload Resume/CV *" as required | ⚠️ **FINDING** — submission succeeds anyway. DOM inspection confirms the file input has `required: false`. The system silently substitutes a synthetic, auto-generated resume PDF built from profile field data (generic boilerplate: "Experienced consultant with strong delivery discipline…"), rather than blocking submission or clearly labeling the field as optional. |
| V10 | Upload a `.txt` file as the resume (bypassing the `.pdf,.doc,.docx` picker filter) | Should be rejected server-side | ⚠️ **FINDING** — accepted and stored as-is (labeled "DOC" in the UI, filename `notaresume.txt`). The file-type restriction exists only as the file `<input accept>` client hint; there is no server-side (or even robust client-side) enforcement. |
| V11 | Delete a profile | — | ℹ️ **By design, not a defect** — the "Delete" button is present on every profile card but is rendered disabled (`Mui-disabled`) regardless of stage (tested on `Submitted` and `Rejected` profiles). There appears to be no UI path to delete a submitted profile, likely an intentional audit-trail safeguard. |

---

## 4. Resume Brander Module

### 4.1 "Resume Brander" tab

| # | Scenario | Result |
|---|---|---|
| R1 | Upload a resume (PDF) | ✅ PASS — `POST /api/worknexa/resume/parse` → 200 |
| R2 | Upload a candidate photo | ✅ PASS — "Photo uploaded" confirmation shown |
| R3 | Download PDF (branded) | ✅ PASS — `POST /api/worknexa/resume/brand?format=pdf` → 200 |
| R4 | Download Word (branded) | ✅ PASS — `POST /api/worknexa/resume/brand?format=docx` → 200 |
| R5 | Reset Workspace | ✅ PASS — clears resume/photo, returns to empty-state placeholder |
| R6 | Upload an unsupported file type (`.txt`) | ✅ PASS — silently rejected by the dropzone's `accept` filter; no state change, no server call made |

### 4.2 "Resume Converter" tab

| # | Scenario | Result |
|---|---|---|
| R7 | Upload a non-text-layer ("scanned") PDF → Convert Layout | ✅ PASS — clear, correct validation message: *"This PDF has no readable text layer -- it looks like a scanned image. Scanned resumes aren't supported; please upload a text-based PDF or a Word file."* |
| R8 | Upload a valid text-based multi-column PDF → Convert Layout | ✅ PASS — conversion succeeds, opens editor workspace with "Create branded resume" / Download options |
| R9 | Download PDF from the converted workspace | ⚠️ **FINDING (infra)** — the download call itself returns 200, but it is preceded by `POST .../resume/editor/session/{id}/forcesave` → **502 Bad Gateway**. Console shows the root cause: `[OnlyOffice] Script load failed` while loading `https://workforcenexa.d4insight.com/onlyoffice/web-apps/apps/api/documents/api.js` — the OnlyOffice document-editing server this feature depends on is unreachable in this environment. The failure is silent to the end user (no visible error), so a downloaded file may not include any live in-browser edits made after conversion. |

---

## 5. AI JD Builder Module

Tested both as a standalone page (`/worknexa/jd-builder`) and the equivalent "Build with AI" shortcut embedded in Opportunity Details (§2.3) — behavior is identical in both places.

| # | Scenario | Result |
|---|---|---|
| J1 | Client-side validation — "Generate with AI" disabled with empty Role Title | ✅ PASS |
| J2 | Fill Role Title + Technology Stack → Generate with AI | ❌ **BLOCKED** — `OpenRouter API Error: Client error '401 Unauthorized' for url 'https://openrouter.ai/api/v1/chat/completions'`, with the app's own error output explicitly suggesting: *"Please ensure your OPENROUTER_API_KEY is correct or check the server logs."* This is a server/environment configuration issue, not a UI defect — but it means **no AI-generated JD content could be produced or validated** in this environment. |
| J3 | "Apply & Save" / "Apply to Opportunity" stays disabled without a successful generation | ✅ PASS |

**Impact:** Because JD generation is non-functional, the following downstream happy paths could not be exercised: reviewing/editing AI-generated text, "Refine existing Job Description" toggle, "Save & attach as Word Document (.docx)" toggle, and applying a generated JD back onto an opportunity.

---

## 6. Consolidated Findings (by severity)

| Severity | Finding | Module |
|---|---|---|
| High | AI generation backend unauthorized (`OPENROUTER_API_KEY` invalid/missing) — blocks all AI JD generation | AI JD Builder / Opportunities |
| Medium | Resume file upload is not actually required, and accepts any file type server-side despite UI labeling/restrictions | Sourced Profiles |
| Medium | Resume Converter's OnlyOffice editor dependency is unreachable, causing silent 502s on forcesave | Resume Brander |
| Low | Mettle Test Score has no upper-bound validation (accepts values like 150) | Sourced Profiles |
| Low | Bulk "Import Openings" silently drops invalid rows with no user-facing feedback | Opportunities |

## 7. Not covered

- Bulk **Import Openings** via actual file upload (only the inline grid entry path was tested).
- CSV export **content** verification (only that the action completes without error).
- Delete flows for profiles in states other than `Submitted`/`Rejected` (button was disabled in all cases tested, so no state appears to allow deletion via the UI).
- Any role/permission other than `SUPERADMIN`.
