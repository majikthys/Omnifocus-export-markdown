# OmniFocus Export to Markdown

Export your OmniFocus 4 database into organized Markdown files with full Obsidian Tasks plugin compatibility, including attachments and comprehensive metadata.

## Features

- **📁 Folder Hierarchy**: Preserves your OmniFocus folder structure in the exported markdown
- **📅 Full Date Support**: Exports all dates with Obsidian Tasks emoji format (due 📅, scheduled ⏳, start 🛫, completed ✅, created ➕, modified ✏️)
- **🏷️ Complete Tags**: Includes all contexts/tags as hashtags
- **📎 Attachments**: Exports full-resolution images from backups with fallback to preview thumbnails
- **⭐ Status Tracking**: Shows project status, flagged tasks (🔼), and completion state
- **📝 Notes**: Preserves task notes as properly formatted sub-items
- **🔗 No OmniFocus Dependencies**: Creates standalone markdown files without OmniFocus links

## Usage

### Basic Export (Preview Images Only)
```bash
python3 omnifocus2md.py
```

### Full Export with High-Resolution Attachments
```bash
python3 omnifocus2md.py "/Users/yourusername/Library/Containers/com.omnigroup.OmniFocus4/Data/Documents/Backups"
```

## Output Structure

### File Organization
```
omnifocus_md/
├── attachments/                    # Exported images
│   ├── task123_Photo.jpg          # Full-resolution from backup
│   └── task456_Document.jpg       # Preview if backup unavailable
├── Work/                          # Folder hierarchy preserved
│   ├── Projects/
│   │   └── Website Redesign.md
│   └── Miscellaneous (on-hold).md # Status in filename (unless 'active')
└── Personal/
    ├── Home Improvement.md
    └── Travel Planning.md
```

### Sample Output
```markdown
---
status: active
tags: omnifocus
---

# Project Name ⏳ 2024-01-10 #omnifocus

- [ ] Task Name 📅 2024-01-15 ⏳ 2024-01-10 ➕ 2023-12-01 ✏️ 2024-01-14 #urgent #computer #omnifocus 🔼
	- Task note details here
	- Another note line
	- 📎 ![Photo.jpg](attachments/task123_Photo.jpg) (486.0 KB)

- [x] Completed Task ✅ 2024-01-20 📅 2024-01-15 #omnifocus
	- 📎 Document.pdf (2.3 MB)

- [c] Dropped Task #omnifocus
```

## Date Format Reference

| Emoji | Meaning | OmniFocus Field |
|-------|---------|-----------------|
| ✅ | Completed | dateCompleted |
| 📅 | Due | dateDue |
| ⏳ | Scheduled/Planned | datePlanned |
| 🛫 | Start | dateToStart |
| ➕ | Created | dateAdded |
| ✏️ | Modified | dateModified |

## Tag System

- **Context Tags**: All OmniFocus contexts/tags appear as `#tag-name`
- **Project Status**: Added as hashtag unless status is 'active' (e.g., `#on-hold`, `#completed`)
- **Omnifocus Tag**: Every task gets `#omnifocus` for easy filtering

## Obsidian Tasks Compatibility

This export is fully compatible with the [Obsidian Tasks](https://github.com/obsidian-tasks-group/obsidian-tasks) plugin:

- Uses proper emoji date format
- Checkbox states: `[ ]` incomplete, `[x]` complete, `[c]` cancelled/dropped
- Inline metadata format
- Supports task queries and filtering

## Attachments

The script supports two attachment modes:

1. **Full-Resolution** (with backup directory): Extracts original images from OmniFocus backup files
2. **Preview Mode** (default): Uses small preview thumbnails from the database

### Finding Your Backup Directory
```bash
# Typical location:
~/Library/Containers/com.omnigroup.OmniFocus4/Data/Documents/Backups

# List available backups:
ls ~/Library/Containers/com.omnigroup.OmniFocus4/Data/Documents/Backups/
```

## Requirements

- Python 3.6+
- OmniFocus 4
- macOS (for accessing OmniFocus database)

## Automation

Set up periodic exports using:

- **Cron**: Add to crontab for scheduled exports
- **Keyboard Maestro**: Create automation workflows
- **Shortcuts**: macOS Shortcuts app integration

### Example Cron (daily at 9 AM):
```bash
0 9 * * * cd /path/to/script && python3 omnifocus2md.py "/path/to/backups"
```

## Technical Notes

- Automatically detects OmniFocus 4 database location
- Preserves folder hierarchy with proper path sanitization
- Handles multiple projects with same names by combining content
- Generates MD5 checksums to skip unchanged files
- Creates directory structure as needed

## Troubleshooting

**Database not found**: Ensure OmniFocus 4 is installed and has been run at least once.

**Backup directory errors**: Verify the path exists and contains `.ofocus-backup` folders.

**Missing attachments**: Check that backup directory contains recent backups with attachment data.