# Session Documentation Formatting Standards

**Purpose:** Ensure consistent formatting across all AI session documentation  
**Applies To:** Session summaries, transcripts, and related documentation  
**Updated:** 2026-06-08  

## 📅 Date/Time Format Standard

**Required Format:** `YYYY-MM-DD HH:MM:SS Eastern Time (UTC-05:00)`

**Examples:**
- `2026-06-08 00:39:07 Eastern Time (UTC-05:00)`
- `2026-12-25 14:30:15 Eastern Time (UTC-05:00)`

**Usage:**
- All session metadata headers
- Summary period timestamps
- Transcript period timestamps
- File creation timestamps

## 🎨 Emoji Usage Guidelines

### 📋 Section Headers (Summaries)
- 🎯 **Overview of Work Accomplished**
- 🔧 **Key Technical Decisions Made**
- 📁 **Files Created/Modified**
- 🚀 **Context for Future Sessions**
- ✅ **Session Completion Status**

### 🗂️ Subsection Categories
- 📋 Session Management Architecture
- 🏗️ Project Architecture Analysis
- 📝 AI Assistant Instructions
- 🗂️ Session Workspace Files
- 🌐 Repository Root Files
- 🏛️ Key Architectural Elements
- 🎯 Identified Enhancement Opportunities
- 🔍 Technical Insights
- 🔮 Next Session Recommendations

### 🔧 Tool Operations (Transcripts)
- 🔍 **Search Operations:** file search, content search, grep
- 📂 **Repository Operations:** directory browsing, file listing
- 📄 **File Operations:** file reading
- 📖 **Documentation Operations:** documentation file access
- 🏗️ **Creation Operations:** file creation, commits
- 🔧 **Configuration Operations:** setup and configuration changes
- ⚙️ **System Operations:** system configuration changes
- 🛠️ **Utility Operations:** tool and utility functions

### ✅ Result Status Indicators
- ✅ **Successful Operations:** positive results, successful completions
- ❌ **Error Results:** failures, "not found" results, errors
- ⏳ **In-Progress:** pending operations, ongoing processes
- 🎉 **Completion:** major milestones, session completion

### 🎯 Project-Specific Categories
- 🎯 **Goals and Objectives:** targets, aims, purposes
- 🚀 **Deployment and Launch:** deployment activities, releases
- 📊 **Performance and Metrics:** analysis, measurements, optimization
- 🧪 **Testing and Quality:** testing activities, quality assurance
- 📊 **Analysis and Profiling:** performance analysis, code review

## 📝 Template References

### Session Summary Template
**Location:** `/ai/instructions/session-summary-template.md`
**Usage:** Copy template structure for all session summaries
**Key Features:**
- Complete metadata header with timezone
- Emoji-organized section structure
- Consistent formatting patterns
- Future session context sections

### Session Transcript Template
**Location:** `/ai/instructions/session-transcript-template.md`
**Usage:** Copy template structure for all session transcripts
**Key Features:**
- Enhanced tool call formatting with emojis
- Complete conversation preservation
- Metadata tracking section
- Emoji reference guide

### Session Shrinkwrap Template
**Location:** `/ai/instructions/session-shrinkwrap-template.md`
**Usage:** Copy template structure for session completion reports
**Key Features:**
- ✅ Complete validation checklist
- 📁 Final file inventory with structure
- 📊 Comprehensive metrics tracking
- 🎯 Session accomplishments summary
- 🚀 Framework status and next steps

## 🔍 Quality Standards

### Technical Accuracy
- Preserve all code snippets exactly as discussed
- Maintain accurate file paths and technical details
- Apply proper JSON escaping for tool parameters
- Use consistent markdown formatting

### Visual Organization
- Use emojis consistently across documents
- Maintain clear section hierarchy
- Apply consistent spacing and formatting
- Ensure readability for both human and AI reference

### Documentation Completeness
- Include all required metadata fields
- Document all files created/modified
- Provide context for future sessions
- Maintain technical decision rationale

## 🛠️ Implementation Guidelines

### For AI Assistants
1. **Always reference templates** before creating summaries or transcripts
2. **Use consistent emoji patterns** as defined in this document
3. **Apply proper date/time formatting** in all metadata
4. **Preserve technical accuracy** in all documentation
5. **Follow established section structures** from templates

### For Session Commands
- `/update-notes` should use session-summary-template.md
- `/export-transcript` should use session-transcript-template.md
- Both commands should apply formatting standards automatically

### Quality Assurance
- Verify emoji usage matches established patterns
- Confirm date/time format includes timezone
- Check template structure compliance
- Ensure technical details are preserved accurately
