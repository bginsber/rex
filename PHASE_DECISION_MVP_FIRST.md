# Scorecard Integration: MVP-First Phase Decision

## Issue
GitHub Issue: https://github.com/bginsber/rex/issues/39 (Phase 1a-1b)

## Decision: MVP First (REST API Only, No MCP in Initial Release)

**Recommended Timeline:**
- **Phase 1a** (Week 1): Adapter + bootstrap wiring + unit tests
- **Phase 1b** (Week 2): CLI command + documentation + mocked integration test
- **Phase 1c** (Sprint 2, optional): Ground truth testset + baseline evaluation
- **Phase 2** (Later): CI/CD integration (regression testing)
- **Phase 3** (Later): MCP integration (conversational evaluation via Claude)

## Rationale: "Instrumentation Before Orchestration"

### Why MVP First (1a+1b)?

**Core insight:** You need metrics before you can meaningfully use Model Context Protocol.

1. **Get the data first**
   - Build evaluation infrastructure (adapter + CLI)
   - Collect baseline metrics (F1, precision, recall)
   - Know the actual accuracy before optimizing anything

2. **Validate legal strategy**
   - Run evaluation against real labeled data (Phase 1c)
   - Confirm F1 > 0.65 threshold is achievable
   - Establish audit trail for Rule 502 compliance

3. **Unblock team**
   - Adapter/CLI can land independently (useful for manual evaluations)
   - Doesn't require Phase 1c testset to be ready
   - Enables parallel work: engineering on 1a-1b, legal on testcase review

4. **Defer nice-to-have (MCP)**
   - MCP adds conversational interface to Scorecard
   - But you can already run evaluations via CLI
   - Valuable only after you have patterns to discuss (baseline results)
   - Can add in Phase 3 when engineering bandwidth available

### Why Not MCP Now?

| Concern | Impact | Resolution |
|---------|--------|-----------|
| MCP adds complexity | Delays MVP | Do REST API first, MCP later |
| MCP not core to goal | Scope creep | Evaluation metrics are the goal; MCP is enhancement |
| MCP needs Scorecard patterns | No insights yet | Build baseline first (Phase 1c), then use MCP to discuss refinements |

**Analogy:** Don't build a chatbot before you know what to say. Get the data, establish the facts, then build the conversational interface.

## What Lands in First Release (Phase 1a-1b)

### Phase 1a: Evaluation Adapter
- ✅ `rexlit/app/ports/scorecard_port.py` - Port interface
- ✅ `rexlit/app/adapters/scorecard_evaluation_adapter.py` - REST API implementation
- ✅ `rexlit/bootstrap.py` - Wired behind `offline_gate`
- ✅ Unit tests with mocked Scorecard (deterministic, no API key needed)
- ✅ Offline-first: `--online` flag required, graceful degradation in offline mode

### Phase 1b: CLI + Documentation
- ✅ `rexlit evaluate-privilege-model` command
- ✅ `docs/SCORECARD_EVALUATION.md` - Setup, usage, troubleshooting
- ✅ `docs/PRIVILEGE_EVALUATION_METHODOLOGY.md` - Legal defensibility & EDRM compliance
- ✅ `CLAUDE.md` update - Environment variables, metric management, data privacy policy
- ✅ Integration test (mocked Scorecard) - smoke test only, no flakiness in CI

### What's Deferred (Phase 1c, Optional)
- Ground truth testset (50-100 attorney-labeled documents)
- Baseline evaluation run against Scorecard
- `SCORECARD_BASELINE_RESULTS.md` - Documented baseline metrics
- Manual validation script

**Why defer Phase 1c?** It depends on attorney review (not an engineering blocker). Can run in parallel and land in Sprint 2.

## User Experience (MVP)

**User can immediately do:**
```bash
# With mocked adapter (no Scorecard API key needed, for testing)
rexlit evaluate-privilege-model --testset mock_data.jsonl

# With real Scorecard (requires API key and Phase 1c testset)
export SCORECARD_API_KEY="..."
export SCORECARD_PROJECT_ID="314"
rexlit evaluate-privilege-model --testset ground_truth.jsonl --online
```

**User needs from legal team:**
- 50-100 labeled documents (Phase 1c, can defer)
- 4-5 metrics defined in Scorecard UI (Phase 1c, can defer)

## Phase 2+ Roadmap

### Phase 2: CI/CD Integration
- Pytest fixture for loading Scorecard testset
- Regression test suite (nightly, real Scorecard)
- GitHub Actions workflow with `F1 > 0.65` gate
- Alerts on >5% accuracy drops

### Phase 3: MCP Integration (Future)
- MCP server wrapping Scorecard API
- Claude can invoke evaluations conversationally
- Use baseline results to discuss refinements
- **Timing:** After Phase 1c results show patterns to optimize

## Decision Matrix

| Aspect | MVP (1a-1b) | Later (1c+) |
|--------|-----------|-----------|
| **Can ship?** | ✅ Yes (independent) | ⏱️ Needs attorney |
| **Unblocks what?** | ✅ Infrastructure + docs | ✅ Baseline metrics |
| **Legal defensible?** | ⚠️ Partial (framework ready) | ✅ Full (metrics prove it works) |
| **User value?** | ✅ Can manually evaluate | ✅ Can automate + measure |
| **Timeline** | 2-3 weeks | +1-2 weeks (Phase 1c) |

## Next Steps

1. **Engineering (Tomorrow)**
   - Assign Phase 1a owner (6-8 hours)
   - Assign Phase 1b owner (6-8 hours)
   - Sync on acceptance criteria from issue #39

2. **Legal/Compliance (This Week)**
   - Review evaluation methodology doc (PRIVILEGE_EVALUATION_METHODOLOGY.md)
   - Sign off on data privacy approach (redacted testcases only)
   - Commit to Phase 1c testcase labeling (2 hours, Phase 2 sprint)

3. **Scorecard Setup (Parallel)**
   - Create account + project
   - Get API key (for Phase 1c when ready)
   - Define 4-5 metrics (waiting on Phase 1a completion)

## Risk Mitigation

**Risk:** Phase 1c gets indefinitely deferred
- **Mitigation:** Schedule Phase 1c in next sprint before starting Phase 1a
- **Rationale:** Attorney review is finite (2h), shouldn't block infrastructure

**Risk:** MVP doesn't actually add value without testset
- **Mitigation:** Document use case: "CLI tool for manual evaluations + framework for automation"
- **Rationale:** Even without Phase 1c, CLI is useful for ad-hoc privilege analysis

**Risk:** Team builds MCP prematurely
- **Mitigation:** Explicitly defer Phase 3 until Phase 1c baseline is complete
- **Rationale:** No patterns to optimize without data

## Summary

**Principle:** Instrumentation before orchestration. Get the metrics first (Phases 1a-1b-1c), then build the conversational interface (Phase 3 MCP). This unblocks engineering now, ensures legal compliance, and gives clear input for future optimization.

**Outcome:** By end of next sprint, RexLit can answer "How accurate is privilege classification?" with numbers, not anecdotes. MCP is a nice-to-have that becomes valuable once you have a story to tell.
