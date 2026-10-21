# WorkforceNexa – Sourcing AI Reports: Deep Test Results

Tested: 2026-10-15 on https://workforcenexa.d4insight.com/worknexa/ai-reports (logged in as Recruiter Admin).
Method: UI inspection + direct calls to every `/api/worknexa/ai-reports/*` endpoint, cross-checked against raw `/demands` (102) and `/profiles` (81).

Legend: DYNAMIC = driven by DB and correct | PARTIAL = DB-driven but wrong/inconsistent or mixed with hardcoded values | STATIC = hardcoded/templated/fabricated | BROKEN = fails

## 1. Dashboard (/ai-reports)

| Widget | Result | Evidence |
|---|---|---|
| KPI tiles (Total 29, Today 5, Saved 0, Scheduled 0, Favorites 0, Insights 9, Downloads 1) | DYNAMIC | From reports tables; Saved/Scheduled/Favorites verified against real CRUD |
| Hiring Trend (closed opps by month 3/5/5/7) | DYNAMIC | Sum 20 = CLOSED demands (20) |
| Candidate Funnel | PARTIAL / BUG | Submitted 77, Screened 1 correct. Interview shows 0 but DB has 2 (INTERVIEW_L1, INTERVIEW_L2); Selected shows 0 but DB has 1 ONBOARDED. Status names not mapped. |
| Recruiter Productivity | DYNAMIC (top 5 only) | Submitted counts match profiles by sourcer_id. 37 profiles have no sourcer (null) so are not attributed. |
| Department Hiring (donut) | PARTIAL / BUG | Shows only 6 areas; omits the biggest (Everyday Banking 24, Core Platforms 18). "Banking" vs "banking" not merged. |
| Source Effectiveness (Linkedin 79 / Referral 41 / Direct Apply 75 / Agency 29) | STATIC / FABRICATED | Total 224 but only 81 profiles exist; profiles table has no source/channel field. |
| Offer Acceptance Trend (Sep 100%, Oct 75%) | STATIC / FABRICATED | Only 1 offer exists in system; "last 6 months" shows 2 points. |
| Recent Reports / Recent Activities (API returns them) | Recent Reports DYNAMIC; Recent Activities STATIC | Activities are hardcoded ("Just now", "15 mins ago", user " mahalingam"/"admin"). Neither list is rendered on the page. |
| Quick Actions buttons | STATIC (navigation only) | Not data |

## 2. Traditional Reports (/ai-reports/traditional) – 33 templates tested

Common defects (all reports):
- The 6 summary tiles (Total Openings 102, Active 82, Submitted 81, Selected 1, Interviewing 0, Rejection 0%) are IDENTICAL on every report – not report-specific.
- "AI Executive Analysis" is a template: only the report name and row count are interpolated. Risks / Opportunities / Recommendations text is the same hardcoded text for every report ("notice periods for senior candidates...", "reduce reliance on staffing agencies").
- "Active Openings 82" conflicts with real data (OPEN 79; chat says 79 open / 23 closed; DB has 79 OPEN, 20 CLOSED, 3 SELECTED).
- "Interviewing 0" wrong (2 profiles in interview stages). "Selected 1" vs 3 SELECTED demands.

| Report | Rows | Result |
|---|---|---|
| Open Positions | 79 | DYNAMIC (table); AI text templated |
| Closed Positions | 20 | DYNAMIC table |
| Active Requirements | 79 | DYNAMIC table |
| Hiring Pipeline / Recruitment Status / Candidate Pipeline | 6 | DYNAMIC (77 submitted 95.1%) but stage names miss interview/onboarded |
| Hiring Velocity | 10 | PARTIAL – Age real; "Fill Speed: 7/10/13/16 Days Avg" cyclic = synthetic |
| Candidate Summary / Candidate Status | 20 (capped) | DYNAMIC but capped at 20 rows |
| Candidate Source | 20 | STATIC – "Source: Direct Apply" for every row; no source field in DB |
| Resume Quality Distribution | 20 | PARTIAL – score present, "Rate: N/A" on every row |
| Experience Distribution | 20 | DYNAMIC |
| Skill Distribution | 20 | PARTIAL – many "Core skill: None" |
| Recruiter Productivity | 14 | DYNAMIC rows; AI summary contradicts: says "0 profiles submitted" while rows total 44 |
| Recruiter Performance | 14 | PARTIAL – "Rating" = submitted/20 style formula (0.4, 0.5, 0.2); one row shows 4.1 for 1 submission (inconsistent); AI summary says 0 submitted |
| Recruiter Workload | 14 | PARTIAL – real counts; "Recruiting" status constant |
| Interview Scheduling Performance | 14 | STATIC – "Response Time: 2d/3d/4d avg" cyclic, not from data |
| Offer Conversion | 14 | PARTIAL – "Converted: 0 (100.0%)" for 0 offers (wrong) |
| Average Hiring Time | 14 | STATIC – "14,15,16,17,18,19,12,13 Days" sequential pattern, fixed "Target: 14 Days" |
| Interview Success Rate | 1 | DYNAMIC (0 total) |
| Offers Released | 1 | DYNAMIC (Gowri R) |
| Client Hiring Status / Closure Rate | 5 | DYNAMIC (ENBD 76 reqs, 14/76 closed) |
| Client Hiring Trend | 5 | STATIC – "Trend: Upward/Stable" label not computed |
| Client SLA | 5 | STATIC – "5/6/7/4 Days Response TAT", "Target: 5 Days" hardcoded |
| Interviews Scheduled / Interviews Completed / Interview Feedback / Interview Delay Report | 0 | NO DATA (empty) – nothing in DB |
| Offers Accepted / Offers Rejected / Offer Expiry | 0 | NO DATA (empty) |
| **Offer Acceptance %** | – | **BROKEN** – API returns `INVALID_INPUT: Invalid report name` (UI name does not match backend name) |

## 3. Predictive Reports (/ai-reports/predictive)

- **BROKEN – page crashes to a blank white screen.** Console: `ReferenceError: LinearProgress is not defined` in `PredictiveAIReports` (missing MUI import). Triggers whenever the API returns `predictions`, i.e. always. None of the 4 tabs (forecast, acceptance, bottleneck, difficulty) can be viewed.
- Behind the crash, the API data is STATIC: all 4 types return the identical summary, "Projected Hires 15 Candidates 85%", "TAT Speedup 5 business days 70%", risk "Client SPOC review bottleneck", healthScore 50, and recommendation "Validate offer packages against UAE market averages".
- Tables: forecast = STATIC ("40 positions", "85%", "78%"); acceptance = STATIC/fake candidate "Omar K., Senior Consultant, 92%"; bottleneck = PARTIAL (mixed hardcoded stages, "4.5 days", "3.1 days"); difficulty = PARTIAL (job titles real; index values computed; reasons "N/A", marketDemand "Medium" always).

## 4. Smart Reports (/ai-reports/smart)

- **STATIC / FAKE.** Three completely different prompts ("open opportunities for ENBD", "candidates by Mogana Priya K", and gibberish "xyzzy qwerty banana") all returned: same intent CANDIDATE_SEARCH, same SQL (`... WHERE demands.technology LIKE '%React%'`), same explanation sentence, same table. The prompt is only echoed back. No NL understanding, no real SQL generated.
- Suggested queries on the page are hardcoded (acceptable as suggestions).

## 5. Chat with AI

- PARTIAL. Numbers are live ("102 total, 79 open, 23 closed; 81 profiles; recruiter submitted counts") but responses are keyword-routed templates that dump the same data block regardless of the question (weather question got the portal summary). Not true conversational AI. 23 closed also conflicts with DB (20 CLOSED + 3 SELECTED).

## 6. Saved / Scheduled / Favorites / Export

| Feature | Result |
|---|---|
| Saved Reports (create, list, delete) | WORKS (round trip verified, test record deleted). Saved record had summary/data_snapshot null when created via API. |
| Scheduled Reports (create, list, delete) | WORKS (round trip verified, test record deleted). Note: `recipients` is a single string, not a list. |
| Favorites (add, list, remove) | WORKS (verified, cleaned up) |
| Export PDF | WORKS (valid PDF, 11.5 KB) – but returned `downloadUrl` is `/api/download-temp...` which fails; only `/api/worknexa/download-temp...` works. Verify in UI that the button downloads. |
| Export Excel | WORKS (valid XLSX, 8 KB), same downloadUrl prefix issue |

## Summary scorecard

- Fully dynamic and correct: KPI tiles, Hiring Trend, Recruiter Productivity (top 5), Open/Closed/Active tables, Pipeline tables, Candidate Summary/Status, Experience, Client Hiring Status/Closure, Offers Released, Interview Success Rate, Saved/Scheduled/Favorites CRUD, PDF/Excel export.
- Dynamic but wrong/inconsistent: Candidate Funnel, Department Hiring, summary tiles on every traditional report, recruiter AI summary text, Offer Conversion, Recruiter Performance rating.
- STATIC / fabricated (must be fixed): Source Effectiveness, Offer Acceptance Trend, Recent Activities, Candidate Source, Average Hiring Time, Interview Scheduling Performance, Client SLA, Client Hiring Trend, Hiring Velocity fill speed, all AI Executive Analysis narratives, all Predictive data, Smart Reports, Chat (template).
- Broken: Predictive page (blank screen), Offer Acceptance % report (invalid name).
- Empty (no source data): 4 interview reports and 3 offer reports.

## Suggested fix priority
1. Add missing `LinearProgress` import in PredictiveAIReports (Predictive page crash).
2. Fix report name mismatch for "Offer Acceptance %".
3. Replace hardcoded Source Effectiveness / Offer Acceptance / Recent Activities with real queries (add a source field to profiles if needed).
4. Map profile statuses (INTERVIEW_L1/L2, ONBOARDED) in the funnel and summary tiles; compute per-report tiles.
5. Compute TAT, SLA, trend, response-time and fill-speed from timestamps instead of synthetic values.
6. Generate AI narratives and predictions from the report's own data (or an LLM); implement real Smart Report NL-to-query.
