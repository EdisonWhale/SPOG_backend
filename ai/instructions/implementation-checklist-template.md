# [Project/Feature Name] - Implementation Checklist

**Session:** [SESSION_ID] - [session-short-name]  
**Branch:** `sessions/[YYYY-MM-DD-session-short-name-SESSION_ID]`  
**Watermark:** `[ai-claude-SESSION_ID-session-short-name]`  
**Last Updated:** [YYYY-MM-DD Eastern Time (UTC-05:00)] - [brief status note]

---

## 📋 Legend

- ⬜ Not started
- 🟡 In progress
- ✅ Complete
- ❌ Blocked / skipped
- 🔗 Commit SHA (short) appended inline when available

---

## Phase 1: [Phase Name]

**Goal:** [One sentence describing what this phase accomplishes.]  
**Depends on:** [Prior phase(s), or "None".]  
**Exit Criteria:** [Specific, verifiable conditions that must be true before moving on.]  
**Notes command:** `/update-notes` after [trigger condition].

| # | Task | Status | Commit |
|---|------|--------|--------|
| 1.1 | [Task description] | ⬜ | — |
| 1.2 | [Task description] | ⬜ | — |
| 1.3 | [Task description] | ⬜ | — |

---

## Phase 2: [Phase Name]

**Goal:** [One sentence describing what this phase accomplishes.]  
**Depends on:** Phase 1 complete.  
**Exit Criteria:** [Specific, verifiable conditions.]

#### 2-A: [Sub-group Name]

| # | Task | Status | Commit |
|---|------|--------|--------|
| 2A.1 | [Task description] | ⬜ | — |
| 2A.2 | [Task description] | ⬜ | — |

#### 2-B: [Sub-group Name]

| # | Task | Status | Commit |
|---|------|--------|--------|
| 2B.1 | [Task description] | ⬜ | — |
| 2B.2 | [Task description] | ⬜ | — |

#### 2-C: Phase 2 Wrap-Up

| # | Task | Status | Commit |
|---|------|--------|--------|
| 2C.1 | Confirm all Phase 2 tasks complete and tests pass | ⬜ | — |
| 2C.2 | `/update-notes` - create `[NNN]-[phase-2-summary-name].md` | ⬜ | — |

---

## Phase 3: [Phase Name]

**Goal:** [One sentence describing what this phase accomplishes.]  
**Depends on:** Phase 2 complete.  
**Exit Criteria:** [Specific, verifiable conditions.]  
**Status:** [Leave blank until complete, then add: ✅ **COMPLETE** - Commit `[sha]`]

| # | Task | Status | Commit |
|---|------|--------|--------|
| 3.1 | [Task description] | ⬜ | — |
| 3.2 | [Task description] | ⬜ | — |
| 3.3 | `/update-notes` - create `[NNN]-[phase-3-summary-name].md` | ⬜ | — |

---

## Phase N: Session Wrap-Up

| # | Task | Status | Commit |
|---|------|--------|--------|
| N.1 | Update `session_index.md` with session entry | ⬜ | — |
| N.2 | Create `session_metadata.json` | ⬜ | — |
| N.3 | Create shrinkwrap report | ⬜ | — |
| N.4 | Push branch and open MR | ⬜ | — |

---

## 📝 Notes & Decisions Log

| Date | Note |
|------|------|
| [YYYY-MM-DD] | Checklist created; Phase 1 in progress |
| [YYYY-MM-DD] | [Decision or finding recorded here] |

---

## 📐 Usage Guidelines

> **Remove this section before using the checklist in a session.**

### Status Emoji Reference
| Emoji | Meaning |
|-------|---------|
| ⬜ | Not started |
| 🟡 | In progress |
| ✅ | Complete |
| ❌ | Blocked or skipped (add reason in Notes log) |

### Commit Column
- Use short SHA (7 chars): e.g. `a760c8a`
- Use `—` when no commit applies (documentation steps, approvals)
- Multiple commits: `a760c8a, 83ba992`
- Reference MRs inline: `[!42](URL)`

### Phase Structure Guidelines
- **Simple phases** (linear tasks): use a flat table directly under the phase header
- **Complex phases** (grouped work): use `#### N-A:` sub-group headers with individual tables
- **Phase status banner**: add `**Status:** ✅ **COMPLETE** - Commit \`sha\`` below the phase header when done
- **Exit Criteria**: always define before starting a phase; must be verifiable, not subjective

### Notes & Decisions Log
- Record all significant design decisions, trade-offs, and bug fixes here
- Include the date and enough context for a future AI session to understand the rationale
- Use bold for bug fix entries: `**Bug fix:** description`
- Use bold for design decisions: `**Decision:** description`

### Checklist Lifecycle
1. AI assistant creates this file at session start (in the session folder)
2. Status emojis updated as work progresses
3. Commit SHAs filled in after each commit
4. Notes log updated when decisions are made or bugs are found
5. `/update-notes` called at phase boundaries and session end
6. Checklist committed with each update so progress is tracked in git history

---

*Implementation checklist following procedures from `/ai/instructions/ai_session_management.md`*
