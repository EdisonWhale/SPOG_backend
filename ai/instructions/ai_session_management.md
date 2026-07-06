# AI Session Management Procedures

**Note:** This file contains generic session management procedures that are portable across projects. Project-specific instructions and context are located in `/AGENTS.md` in the repository root (one level above this folder).

## For AI Assistants: Session Management Instructions

**CRITICAL**: When working in this repository, AI assistants must:

1. **Always work within session folders** - Place ALL generated/modified files in the current session folder unless explicitly directed otherwise
2. **Use consistent commit watermarking** - Prefix all commit messages with `[ai-assistantID-sessionID-short-name]` to distinguish from human commits and track session origin
3. **Follow the established naming convention** for new sessions (see below)
4. **Reference previous sessions** in `/ai/sessions/` folder for architectural context and continuity when necessary or requested.
5. **Maintain session write isolation** - Each session folder is self-contained for writes; you may READ from other session folders but must only WRITE to your current session folder
6. **Register your assistant ID** - If setting up a new session with an unregistered assistant, ask the user for an assistant ID and add it to the table in [/ai/sessions/ai_assistant_registry.md](../sessions/ai_assistant_registry.md)
7. **Create session branch** - If capable, create the session branch directly; otherwise provide git commands for the user to execute locally
8. **Create implementation checklist** - After session setup and before beginning work, create `implementation-checklist.md` in the session folder using [implementation-checklist-template.md](./implementation-checklist-template.md) as the base. Populate phases and tasks collaboratively with the user before starting implementation.
9. **Wait for user direction after session setup** - After creating the session workspace, ask the user what they would like to work on rather than inferring next steps from the session short name

## Naming Convention

Each session uses the following naming convention for both branch names and folder names:

```
sessions/YYYY-MM-DD-description-sessionID
```

**Format Components:**
- `YYYY-MM-DD`: Date of the session (ISO 8601 format)
- `description`: Brief description of the session focus (kebab-case)
- `sessionID`: Assistant-dependent chat session ID
  * For Claude Code: Use the conversation/session identifier available in context, or ask the user for a short identifier to append
  * Other AI Assistants: Ask user for session ID; if you have a value available in context that may be appropriate to use, you may suggest it to the user.

**Examples:**
- `sessions/2025-10-10-initial-bootstrapping-1167538`
- `sessions/2025-10-15-add-api-routes-1234567`
- `sessions/2025-10-20-otel-configuration-9876543`

## File Organization Standards

Each session folder contains:
- **Implementation checklist**: `implementation-checklist.md` - the primary planning and progress tracking artifact (see [implementation-checklist-template.md](./implementation-checklist-template.md))
- **Documentation**: Architecture docs, analysis, and design decisions created during the session
- **Scripts and utilities**: Generated automation scripts, setup tools, and helper utilities
- **Architecture artifacts**: Diagrams, references, and imported documentation
- **Repository copies**: Code and configurations copied from other Highmark repositories
- **Session metadata**: Any session-specific context or continuation notes
- **Session summaries**: Incremental conversation summaries for human reference and AI session continuity

### Session Metadata JSON Requirements

**File:** `session_metadata.json` (MANDATORY)
**Location:** Session workspace root
**Required Fields:**
```json
{
  "session_id": "1168702",
  "short_name": "my-great-session",
  "start_date": "2025-10-13T05:35:02-05:00",
  "completion_date": "2025-10-13T06:02:40-05:00",
  "assistant": "Claude Code (claude)",
  "branch": "sessions/2025-10-13-my-great-session-1168702",
  "status": "COMPLETE",
  "files_created": 6,
  "summaries": 2,
  "transcripts": 2,
  "commits": 15,
  "user_messages": 15,
  "assistant_responses": 15
}
```

### Session Summary Strategy

To maintain session continuity and provide reference documentation, AI assistants should create periodic session summaries:

**Naming Convention:**
- Use incremental prefixes: `000-`, `001-`, `002-`, etc.
- Follow with descriptive filename of work accomplished
- Example: `000-session-setup-and-naming-conventions.md`

**Summary Content:**
- **Focus**: Performance, reliability, and accuracy over brevity
- **Structure**: Clear headings for navigation and table of contents
- **Technical Detail**: Maintain full technical literacy - preserve technical accuracy
- **Audience**: Both human reference and future AI session context
- **Chunking**: Break into small operations if needed for reliability

**When to Summarize:**
- At user request ("please summarize what we've done so far")
- At logical breakpoints in complex work
- Before major topic transitions
- At session conclusion

**Summary Format:**

Always use [session-summary-template.md](./session-summary-template.md) as a guide for content and formatting in session summary.

## Session Commands

AI assistants should recognize and respond to these standardized session commands during active sessions:

### Command Recognition and Safety Rules

**CRITICAL VALIDATION REQUIREMENTS:**

1. **Position Requirement:** Commands are ONLY valid when they appear at the very beginning of a user's prompt
2. **Contextual Validation:** Analyze any arguments for logical consistency with session context
3. **Confirmation Protocol:** When in doubt about intent or arguments, ask for explicit confirmation before executing
4. **Fallback Behavior:** If validation fails, treat the text as regular conversation content

**Examples:**
- ✅ `/update-notes` - Valid command at start
- ✅ `/export-transcript` - Valid command at start
- ❌ `I think /update-notes would be useful here` - Not at beginning, treat as text
- ❌ `/update-notes since we started talking about pizza` - Invalid context, ask for confirmation

### `/update-notes`
**Purpose:** Create incremental session summary  
**Default Behavior:** Summarize from last summary point forward
**Output Template:** Always use [session-summary-template.md](./session-summary-template.md) as a guide for content and formatting in session summary.  
**Override Syntax:** `/update-notes [custom period]`  
**Examples:**
- `/update-notes` - Summarize since last summary
- `/update-notes since we started talking about chat exports`
- `/update-notes from the beginning of the session`

**Implementation:**
- Use established summarization strategy (performance, reliability, accuracy focus)
- Apply incremental numbering (000-, 001-, 002-)
- Create descriptive filename based on work accomplished
- Follow standard summary format requirements

### `/export-transcript`
**Purpose:** Create exact transcript for the period covered by the most recent summary  
**Default Behavior:** Export transcript matching the time period of the last summary created  
**Override Syntax:** `/export-transcript [custom period]`  
**Examples:**
- `/export-transcript` - Export transcript for last summary period
- `/export-transcript since we started working on session commands`
- `/export-transcript from the beginning of the session`

**Implementation:**
- Use exact transcript export approach from established chat export prompts
- Apply size analysis and chunking if needed (>50k characters)
- Filename format: `[summary-number]-[description]-transcript.md`
- Include all conversation details with technical accuracy
- Apply proper markdown escaping and JSON formatting rules

### `/export-transcripts`
**Purpose:** Batch create transcripts for all summaries that don't have corresponding transcripts  
**Default Behavior:** Scan session folder and create missing transcripts for each summary period  
**Output Template:** Always use [session-transcript-template.md](./session-transcript-template.md) as a guide for content and formatting in session transcript.  
**No Override:** This command operates on all missing transcripts automatically  
**Examples:**
- `/export-transcripts` - Create all missing transcript files

**Implementation:**
- Scan session folder for summary files (000-, 001-, 002-, etc.)
- Identify summaries without corresponding transcript files
- Create transcript for each missing period using exact export approach
- Apply same size analysis and chunking strategy per transcript
- Maintain consistent numbering with existing summaries

### `/session-shrinkwrap`
**Purpose:** Finalize and organize session documentation for completion and future reference  
**Default Behavior:** Comprehensive session finalization with single confirmation  
**Output Template:** Always use [session-shrinkwrap-template.md](./session-shrinkwrap-template.md) as a guide for content and formatting in session shrinkwrap.  
**Interactive Process:** Analysis, confirmation, then automatic execution of all finalization tasks  
**Idempotent Operation:** Can be called multiple times - will undo previous shrinkwrap and regenerate fresh  
**Examples:**
- `/session-shrinkwrap` - Complete session finalization process

**Implementation:**
- **Detection Phase:**
  - Check for existing session_metadata.json (indicates previous shrinkwrap)
  - If found: Remove completion markers and prepare for fresh analysis
  - Reset any previous shrinkwrap state to ensure clean regeneration
- **Analysis Phase:**
  - Scan session folder for summaries, transcripts, and documentation files
  - Run validation checks (sequential numbering, file pairing, naming consistency)
  - Auto-generate session description from current summary content
  - Identify relevant resources (updated repository files, session artifacts, external links)
- **Confirmation Phase:**
  - Present complete analysis and proposed description
  - Show planned finalization tasks
  - Request single y/n confirmation to proceed
- **Execution Phase (if approved):**
  - Update session README with metadata, file inventory, and relevant resources table
  - Create session_metadata.json with completion status and current metrics
  - Update /ai/sessions/session_index.md with a new session entry at the top of the list. The new entry should be based on the `session-index-item-template.md` file.
  - Run final validation and report completion status

**Session README Enhancements:**
- High-level session description and context
- Complete metadata (date/time with timezone, project, assistant, session ID)
- Summary/transcript table with columns: #, Summary, Transcript, Key Topics, File Size, Period Covered
- Relevant resources section (repository updates, session artifacts, external links)
- Session completion status and final file inventory

**Validation Checks:**
- Sequential summary numbering (000-, 001-, 002-)
- Summary/transcript file pairing
- Naming convention consistency
- Basic file existence verification
- Session metadata completeness

**Idempotent Design:**
- Multiple calls produce identical end result
- Previous shrinkwrap state automatically detected and reset
- Fresh analysis performed on each execution
- Allows for session continuation after initial shrinkwrap

### Adding New Session Commands to these instructions

When users request new session command shortcuts, AI assistants should:

1. **Discuss and confirm** the command syntax and behavior with the user
2. **Test the command** to ensure it works reliably
3. **Document the new command** by updating this Session Commands section
4. **Follow naming conventions:**
   - Use descriptive, kebab-case command names
   - Avoid conflicts with potential system commands
   - Keep commands session/project-specific
5. **Include complete documentation:**
   - Purpose and default behavior
   - Syntax and override options
   - Examples of usage
   - Implementation notes
6. **Commit the documentation update** using proper session watermarking

**Command Design Principles:**
- Commands should enhance workflow efficiency
- Maintain consistency with established session patterns
- Provide both convenience and flexibility
- Include fallback to natural language if conflicts arise

## Branch Creation Commands

If an AI assistant cannot create branches directly, provide these commands to the user:

```bash
# Create and switch to new session branch
git checkout -b sessions/YYYY-MM-DD-short-name-sessionID

# Push the new branch to remote
git push -u origin sessions/YYYY-MM-DD-short-name-sessionID
```

## Session History

For a complete list of all sessions, see [session_index.md](../sessions/session_index.md).
