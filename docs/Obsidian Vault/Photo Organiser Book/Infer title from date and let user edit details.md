i.e. trip to lakes

Analyze completes
→ Title auto‑inferred
→ User sees editable Title field
→ User may refine it
→ Preview reflects final title
→ Copy Organize executes

Inference happens once per analysis input change, not continuously. Per folder

- ✅ Infer date range after Analyze
- ✅ Generate neutral default title
- ✅ Populate editable Title field
- ✅ Freeze inference after user edit
- ✅ Reflect title in Preview and Destination
- ✅ Copy‑only Organize uses final title
- ✅ Completion message uses title verbatim

## 1. Data Source Rules

1. The title **must be derived solely from Analyze results**.
2. Only files with a **valid capture date** may be used for inference.
3. Files without a capture date:
    - Are excluded from range calculation
    - Must not block inference if at least one dated file exists

**Prohibited sources:**

- Folder names
- File modification times
- Camera models
- GPS/location data
- User input other than title edits

2. Date Range Determination Rules
2.1 Eligible Dates

Compute:

earliestDate
latestDate


Using only valid capture dates.

2.2 Range Classification
Apply exactly one of the following cases, top‑down:


Single day

earliestDate == latestDate



Single month

Same year AND same month



Multiple months, single year

Same year, different months



Multiple years

Different years



No other categories are permitted.

3. Date Range Formatting Rules
Formatting must be human‑readable and consistent.
3.1 Single Day
YYYY‑MM‑DD

Example:
2025‑04‑12


3.2 Single Month
Month YYYY

Example:
April 2025


3.3 Multiple Months, Same Year
Month–Month YYYY

Example:
April–May 2025

Rules:

Use an en‑dash (–), not a hyphen (-)
Month names must be full, not abbreviated


3.4 Multiple Years
Month YYYY – Month YYYY

Example:
Dec 2024 – Jan 2025

Rules:

Both start and end months must be shown
Years must be explicit on both sides if different


4. Title Construction Rules
4.1 Default Title Template
The default inferred title must be:
Photos – <Formatted Date Range>

Examples:
Photos – April 2025
Photos – April–May 2025
Photos – Dec 2024 – Jan 2025

Rules:

“Photos” is fixed and neutral
Title must not imply location, event, or subject
No emojis or punctuation beyond the en‑dash


5. No‑Data Fallback Rules
If no valid capture dates exist:

Skip date inference entirely
Use the fallback title:
Photos – Undated Import


Surface a non‑blocking informational note:

“Some files do not contain capture date metadata.”



The fallback title must remain editable.

6. User Override Rules (Critical)
6.1 Editability

The Organization Title field is always editable before Preview.
The inferred title is pre‑filled, not locked.

6.2 Ownership Transfer
Once the user edits the title:

The title becomes user‑owned
The system must never overwrite it automatically

This applies even if:

Analyze is re‑run
Preview is regenerated


7. Re‑Inference Rules
Auto‑inference may occur only when inputs change, and only if the title is not user‑owned.
Inputs that allow re‑inference:

Source folder changed
New Analyze run completes
Analysis data is invalidated

Inputs that must NOT trigger re‑inference:

Preview generation
Navigation
Organize execution
Progress polling


8. Preview Consistency Rules

The Preview must display the effective title exactly as it will be used.
The title must appear in:

Preview summary
Destination path
Example file paths


Any change to the title:

Invalidates the existing preview
Requires regeneration before execution




9. Execution & Completion Rules

Organize execution must use the final effective title, verbatim.
Completion messaging must reference the title:
Files copied to:
<Destination>/<Organization Title>/


Copy‑only organize enables the final message:

“You can now safely format the card.”




10. Explicit Non‑Goals
The title inference must not:

Guess event names (“Wedding”, “Trip”)
Infer locations
Create multiple jobs from one import
Modify files or directories during inference
Replace a user‑entered title

These are v3.x concerns.