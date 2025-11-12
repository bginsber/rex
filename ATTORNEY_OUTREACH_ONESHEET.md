# Attorney Outreach: Privilege Classification Evaluation

## The Ask
**Help us label 50-100 documents to validate RexLit's privilege classification accuracy.**
- **Time commitment:** ~2 hours (documents pre-screened, labeling template provided)
- **Timing:** Phase 2 sprint (next 2-3 weeks)
- **Scope:** Privileged vs. non-privileged documents, with category (attorney-client, work product, etc.)

---

## The Problem (Why This Matters)

### Legal Risk: Rule 502 Waiver Without Metrics

**Current state:** RexLit's privilege classifier is tested manually, but we can't prove it works under court scrutiny.

**If challenged:**
- Opposing counsel: "How do you know your automated classifier is accurate?"
- Our answer today: "We tested it manually."
- Our answer tomorrow: "We validated against 100 attorney-reviewed documents; 92% accuracy, F1 = 0.88."

**Why it matters:** Under Federal Rule of Evidence 502, privilege is waivable if you can't demonstrate due care in identifying and protecting privileged information. Quantified metrics + documented methodology = legal defensibility.

### Current Privilege Pipeline

RexLit uses a hybrid approach:
1. **Fast pre-filter** (pattern-based): ≥85% confidence → skip LLM (saves $)
2. **LLM escalation** (Groq Cloud): 50-84% confidence → send to AI for reasoning
3. **Human review**: <50% confidence → flag for attorney decision

**Gap:** We don't know if 85%/50% thresholds are actually calibrated correctly. What does "85% confident" mean in practice?

### What Scorecard Evaluation Provides

Standard e-discovery metrics:
- **Precision:** Of documents marked privileged, how many are actually privileged? (Avoid over-redaction)
- **Recall:** Of all privileged documents, what percentage did we find? (Avoid waiver)
- **F1 Score:** Balanced accuracy metric (industry standard for privilege review)
- **Confidence Calibration:** Does "85% confident" actually mean 85% accuracy?

---

## What You'd Be Doing

### Step 1: Document Review (30-45 min)
- We provide 50-100 pre-screened documents (mostly real JUUL discovery materials, redacted for confidentiality)
- You categorize each as:
  - **Not Privileged**
  - **Privileged: Attorney-Client** (direct legal advice between attorney and client)
  - **Privileged: Work Product** (attorney preparation in anticipation of litigation)
  - **Privileged: Other** (joint defense agreement, etc.)
  - **Uncertain** (edge case → we'll note it)

### Step 2: Brief Comments (Optional, 15-30 min)
- 1-2 sentence reasoning for tricky cases
- Helps us understand failure modes (e.g., "in-house counsel emails are hard to detect")

### Step 3: Review Results (15-30 min, Async)
- We run evaluation, share results dashboard
- You review accuracy/edge cases, suggest improvements
- Input on whether 85%/50% thresholds make sense for your workflow

**Total time: ~2 hours over 1-2 weeks**

---

## What Happens Next

### Engineering Side (Phase 1a-1b, This Sprint)
- Build evaluation infrastructure (adapter + CLI)
- Set up Scorecard project
- Document evaluation methodology for compliance

### Your Side (Phase 1c, Next Sprint)
- Label documents (2 hours)
- Review results and sign off on methodology

### Outcome (End of Q1)
- Published baseline metrics: F1 = X%, Precision = Y%, Recall = Z%
- Documented evaluation methodology (audit trail for Rule 502 defense)
- Data-driven tuning of confidence thresholds

---

## Why Now?

1. **Reputational risk:** If challenged, "We don't measure accuracy" is indefensible
2. **Timing:** Tests are already written; infrastructure being built; low friction to add evaluation
3. **User trust:** Quantified metrics → confidence in product for legal teams
4. **Operational:** Results will guide threshold tuning and policy improvements

---

## Timeline

| Milestone | Owner | Duration | Status |
|-----------|-------|----------|--------|
| Scorecard evaluation framework (adapter + CLI) | Engineering | 2 weeks | 🚀 Starting now (Issue #39) |
| Document labeling & ground truth testset | You + Eng | 2 hours + setup | ⏳ Next sprint (Phase 1c) |
| Evaluation run & results analysis | Engineering + Scorecard | <1 day | ⏳ After labeling |
| Methodology sign-off & baseline publication | You + Compliance | 1 hour | ⏳ End of Phase 1c |

---

## Questions?

- **"How long, really?"** ~2 hours active work. We handle setup, Scorecard UI, results analysis.
- **"Will this change how RexLit works?"** No. Evaluation is optional (`--online` flag, separate from normal CLI).
- **"What if my labels disagree with current tests?"** That's the point! Helps us recalibrate.
- **"Can we use real documents from past cases?"** Yes, if redacted appropriately. We'll work with your document controls.
- **"What if we find accuracy is low (<65%)?"** Feedback loop: adjust policy, retrain, re-evaluate. This is why we measure.

---

## Next Steps

1. **Read:** Full issue on GitHub: https://github.com/bginsber/rex/issues/39
2. **Review:** Evaluation methodology doc: `docs/PRIVILEGE_EVALUATION_METHODOLOGY.md` (in Phase 1b PR)
3. **Commit:** Confirm 2-hour availability for Phase 1c (next sprint)
4. **Discuss:** Any concerns about data privacy or Rule 502 implications

---

**TL;DR:** Help us label 100 documents so we can prove RexLit's privilege classifier works. 2 hours now saves 20 hours of discovery dispute later.
