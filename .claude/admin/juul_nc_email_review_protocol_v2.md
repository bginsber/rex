# JUUL–NC Email Review Protocol (v2)

## 0) Authority & Incorporation
This Protocol incorporates and is subordinate to:
- The **[Case Caption] Protective Order** dated [DATE] (“Protective Order”). Designation levels: **AEO**, **Confidential**, **Public**. Challenge procedures and re-designation follow the Protective Order.
- The **ESI Protocol** (if any).
- The Court’s **FRE 502(d) Order** (or, absent that, FRE 502(b) governs). See §7 (Claw-Back).

If this Protocol conflicts with the Protective Order or ESI Protocol, those documents control.

## 1) Scope & Sources
- Corpus: Emails from **JUUL Labs Collection** related to **State of North Carolina v. JUUL Labs, Inc.**, obtained via the **UCSF Industry Documents Library** (IDL), with OCR text joined per dataset workflow.
- Core metadata expected: `id`, `bates`, `custodian`, `datesent/datereceived`, `author/recipient`, `title`, `type=email`, `ocr_text`, `redacted`, `filepath`, `collection`, `case`, and any IDL topic tags.

## 2) Definitions & Standards (apply narrow tailoring)
**Attorney–Client Privilege (ACP):** Confidential communications between client and lawyer for the purpose of seeking, obtaining, or providing legal advice.  
**Work Product (WP):** Documents/materials prepared by or for counsel **in anticipation of litigation** or for trial; “opinion” WP (mental impressions, conclusions) gets heightened protection.  
**Common Interest (CI):** ACP/WP shared among parties with a common legal interest **pursuant to an executed CI agreement**—business interest alone is insufficient.  
**Trade Secret (DTSA 18 U.S.C. §1839(3)):** Information that (i) derives **independent economic value** from not being generally known, and (ii) is subject to **reasonable secrecy measures**.  
**Confidential Personal Information (CPI):** Non-public personal identifiers (DOB, SSN, driver’s license, non-work email/phone/address, banking/benefits), student/parent identities, and other sensitive personal data.  
**Carve-out:** **Employee compensation/share purchase/acquisition financial details are not CPI by themselves** and should not be redacted solely on that basis.  
**Legal/Contract Limits:** Material barred from disclosure by statute/regulation or third-party contractual prohibitions that JUUL cannot unilaterally waive. **Identify the specific legal source/contract** when invoking this category.

## 3) Classification Labels (multi-label; span-level redactions)
- **PRIVILEGED** (ACP/WP/CI): mark basis explicitly (e.g., `ACP`, `WP`, `CI`).
- **TRADE_SECRET** (meets DTSA criteria).
- **CONFIDENTIAL_TAX** (non-public tax identifiers/filings).
- **CPI/PERSONNEL** (as defined above).
- **LEGAL/CONTRACT_LIMIT** (cite statute/contract).
- **NON-JLI_PERSONAL** (unrelated personal/professional).
- **RESPONSIVENESS**: `RESPONSIVE` if tied to youth access/marketing, retailer compliance/verification, nicotine strength/disclosures, health/therapeutic claims, or governance thereof. Otherwise `NON-RESPONSIVE`.
- **HOTDOC:n** (1–5). Use 5 for potential admissions/awareness, cover-up attempts, C-suite involvement, or documents central to allegations.

**Justifications**: Provide **one concise sentence** per decision—do not reveal privileged substance.

## 4) Proportionality (FRCP 26(b)(1))
If redaction work on a single document would exceed **15 minutes** or requires full-page masking, **escalate** (§6) for withholding vs. targeted redaction decision, weighing importance, burden, and availability of the information from less burdensome sources.

## 5) Redaction Specifications (technical)
- **Method:** Permanent **burn-in** redactions; no overlays.  
- **Appearance:** Solid black box labeled `REDACTED – [CATEGORY]`.  
- **Granularity:** Redact only the necessary spans; leave non-sensitive text intact.  
- **Bates & system metadata:** never redact.  
- **OCR variability:** Compute offsets on a **normalized text view** (trim, collapse whitespace, normalize hyphens). Store both normalized offsets and source character indices. For PDFs, record page/quad boxes when available to improve placement fidelity.

## 6) Review Workflow & Escalation
**Pilot Calibration (mandatory):** Review **100 docs** (stratified sample).  
- Compute **Cohen’s/Fleiss’ κ** across reviewers; target **≥0.80**.  
- Tune thresholds/rules; freeze **Policy v2.1** after pilot.

**Primary Review:**  
1) Auto-detections (regex/Presidio) → tag candidates.  
2) Policy reasoning pass (Safeguard/LLM) on “maybes.”  
3) Reviewer decision with span-level redactions + designations (Protective Order).

**Escalation:** Any doc with `needs_review=true`, privilege uncertainty, DTSA invocation, or >50% body redacted:  
- **Triage Attorney** within **24 hours** → decision or escalate to **Privilege Partner** within **48 hours**.  
- Log all escalations with outcome and rationale.

**Reviewer Qualifications:**  
- Primary reviewers: training module on this Protocol, ACP/WP distinctions, DTSA elements, Protective Order designations.  
- Second-level reviewers: licensed attorney with litigation experience.

## 7) FRE 502 Claw-Back Protocol
- If potentially privileged material is produced: **notify** receiving party within **5 business days** of discovery; identify Bates ranges and basis (ACP/WP/CI).  
- Receiving party shall **sequester** or return/destroy copies consistent with the Protective Order and FRE 502(b)/(d).  
- Parties meet and confer within **7 days**; disputes submitted to the Court per Protective Order.

## 8) Quality Control (QC) & Validation
- **Random QC:** **10%** of **NON-RESPONSIVE** docs.  
- **Targeted QC:** **100%** of **PRIVILEGED** designations (different attorney); **100%** of **HOTDOC ≥4**.  
- **IRR Target:** **≥90% agreement**; **κ ≥ 0.80** maintained.  
- **Drift checks:** Weekly spot-checks; re-training if κ < 0.75.  
- **Audit Ledger:** For every decision record: reviewer_id, timestamp, software version/hash, policy version, confidence, spans, and justification.

## 9) TAR/AI Integration
- Use seed set from pilot; train responsiveness model (TAR 1.0/2.0 acceptable).  
- Promote docs above **score ≥0.70** for priority review; sample rejects to monitor false negatives.  
- Do **not** rely on TAR for privilege; TAR may prioritize likely-privileged for human review.

## 10) Production Specifications
Preferred: **TIFF+Text** with **DAT/OPT** + extracted metadata; acceptable alternative: **searchable PDF** with burn-in redactions.  
**Minimum metadata fields:** `BEGBATES`, `ENDBATES`, `BEGATTACH`, `ENDATTACH`, `CUSTODIAN`, `AUTHOR`, `RECIPIENTS`, `CC`, `BCC`, `DATESENT`, `DATERECEIVED`, `SUBJECT`, `FILEPATH`, `CONF_LEVEL`, `PRIVILEGE_BASIS`.  
Privileged docs withheld: produce **Privilege Log** (see schema §11). Redacted docs designated per Protective Order.

## 11) Output Schemas
**Decision JSON (per doc):**
```json
{
  "doc_id": "JLI00489744",
  "labels": ["PRIVILEGED:ACP", "RESPONSIVE", "HOTDOC:4"],
  "designations": ["Confidential"], 
  "redactions": [
    {"category": "CPI/PERSONNEL", "start_norm": 1024, "end_norm": 1060, "start_src": 1037, "end_src": 1079, "page": 1, "justification": "Personal mobile number"}
  ],
  "privilege_log": {
    "date": "2019-04-14",
    "author": "In-house counsel",
    "recipients": ["Exec team"],
    "subject_matter": "Legal advice re retailer compliance",
    "basis": ["ACP"]
  },
  "confidence": 0.82,
  "needs_review": false,
  "reviewer_id": "rvw_0123",
  "policy_version": "v2.0",
  "software_version": "rexlit@<git-hash>",
  "decision_ts": "2025-11-01T22:00:00Z"
}
Privilege Log CSV:
DOC_ID,DATE,FROM,TO,CC,BCC,SUBJECT_MATTER,BASIS,NOTES

12) Third-Party Rights & Waiver Procedures
When invoking LEGAL/CONTRACT_LIMIT, cite the controlling statute/regulation/contract. If JUUL seeks to waive a contractual restriction, obtain written consent from the third party; retain the consent in the audit record.

13) Recordkeeping & Chain of Custody
All inputs/outputs hashed; append-only JSONL audit ledger; policy changes via version-controlled repo (tags per release).

Keep reviewer rosters, training completion, and QC reports for the file.

## 14) YAML Configuration Template

```yaml
policy_version: "v2.0"
protective_order:
  caption: "[Case Caption]"
  date: "[DATE]"
  levels: ["AEO", "Confidential", "Public"]

fre_502:
  enabled: true
  notify_window_business_days: 5
  meet_confer_days: 7

pilot:
  n_docs: 100
  irr_target_kappa: 0.80

thresholds:
  hotdoc_priority_min: 4
  tar_promote_score_min: 0.70
  proportionality_minutes_per_doc: 15

qc:
  random_sample_nonresponsive_pct: 10
  targeted:
    privileged_pct: 100
    hotdoc_ge: 4
    hotdoc_pct: 100
  irr_targets:
    agreement_pct: 90
    kappa_min: 0.80

escalation:
  triage_hours: 24
  partner_hours_after_triage: 48
  criteria:
    - needs_review_true
    - privileged_uncertain
    - dtsa_invoked
    - redacted_body_pct_gt: 50

redaction:
  method: "burn-in"
  label_format: "REDACTED – {CATEGORY}"
  preserve_bates: true
  ocr_normalization: ["trim", "collapse_whitespace", "normalize_hyphens"]

production:
  preferred: "TIFF+Text"
  alt: "Searchable PDF"
  loadfiles: ["DAT", "OPT"]
  metadata_fields:
    - BEGBATES
    - ENDBATES
    - BEGATTACH
    - ENDATTACH
    - CUSTODIAN
    - AUTHOR
    - RECIPIENTS
    - CC
    - BCC
    - DATESENT
    - DATERECEIVED
    - SUBJECT
    - FILEPATH
    - CONF_LEVEL
    - PRIVILEGE_BASIS
```
