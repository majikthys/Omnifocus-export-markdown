import sqlite3
from collections import defaultdict
import os
import hashlib

def compute_md5(text):
    """Compute MD5 hash of the given text."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def format_task_dates(date_completed, date_due, date_planned, date_to_start):
    """Format task dates using Obsidian Tasks emoji format."""
    from datetime import datetime

    def format_date(date_value):
        if date_value is None:
            return None
        if isinstance(date_value, (int, float)):
            return datetime.fromtimestamp(date_value).strftime('%Y-%m-%d')
        return str(date_value)[:10]

    date_parts = []

    if date_completed:
        date_parts.append(f"✅ {format_date(date_completed)}")
    if date_due:
        date_parts.append(f"📅 {format_date(date_due)}")
    if date_planned:
        date_parts.append(f"⏳ {format_date(date_planned)}")
    if date_to_start:
        date_parts.append(f"🛫 {format_date(date_to_start)}")

    return f" {' '.join(date_parts)}" if date_parts else ""

def format_task_tags(task_tags, project_status=None):
    """Format task tags for display in markdown."""
    all_tags = []

    # Add original task tags
    if task_tags:
        all_tags.extend(f"#{tag.replace(' ', '-')}" for tag in task_tags)

    # Add project status tag if not 'active'
    if project_status and project_status.lower() != 'active':
        all_tags.append(f"#{project_status.replace(' ', '-')}")

    # Always add omnifocus tag
    all_tags.append("#omnifocus")

    return " " + " ".join(all_tags) if all_tags else " #omnifocus"

def fetch_tasks_with_project_info(database_path):
    """Extract tasks, their associated project name, project identifier,
    completion status, dropped status, flagged status, and date fields from the database."""
    query = """
    SELECT
        t1.name AS task_name,
        t1.persistentIdentifier AS task_identifier,
        t1.plainTextNote AS task_note,
        t2.name AS project_name,
        t2.persistentIdentifier AS project_identifier,
        t1.dateCompleted IS NOT NULL AS is_completed,
        t1.effectiveDateHidden IS NOT NULL AS is_dropped,
        t1.flagged AS is_flagged,
        t1.dateCompleted AS date_completed,
        t1.dateDue AS date_due,
        t1.datePlanned AS date_planned,
        t1.dateToStart AS date_to_start
    FROM
        Task t1
    LEFT JOIN
        Task t2
    ON
        t1.containingProjectInfo = t2.persistentIdentifier
    """
    with sqlite3.connect(database_path) as conn:
        return conn.execute(query).fetchall()

def fetch_task_tags(database_path):
    """Fetch all tags for tasks as a dictionary mapping task_id to list of tag names."""
    query = """
    SELECT
        tt.task AS task_id,
        c.name AS tag_name
    FROM
        TaskToTag tt
    JOIN
        Context c ON c.persistentIdentifier = tt.tag
    ORDER BY
        tt.task, tt.rankInTask
    """
    task_tags = defaultdict(list)
    with sqlite3.connect(database_path) as conn:
        results = conn.execute(query).fetchall()
        for task_id, tag_name in results:
            task_tags[task_id].append(tag_name)
    return dict(task_tags)

def fetch_projects_with_metadata_from_projectinfo(database_path):
    """Get metadata (name, identifier and status) for projects from the ProjectInfo table."""
    query = """
    SELECT 
        Task.name AS project_name,
        Task.persistentIdentifier AS project_identifier,
        ProjectInfo.effectiveStatus AS project_status
    FROM 
        Task
    JOIN
        ProjectInfo
    ON
        Task.persistentIdentifier = ProjectInfo.task
    """
    with sqlite3.connect(database_path) as conn:
        results = conn.execute(query).fetchall()
        print(len(results))
    return {project_id: (project_id, project_name, project_status) for project_name, project_id, project_status in results}

def sanitize_filename(filename):
    """Sanitize the filename by removing or replacing special characters."""
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename

def generate_md_metadata(project_info):
    """Generate Markdown metadata for a given project."""
    project_id, project_name, project_status = project_info
    if not project_id:
        return f"status: {project_status}\ntags: omnifocus\n"
    return f"status: {project_status}\ntags: omnifocus\n"

def format_note_as_subitems(note):
    """Format the note text as indented sub-items."""
    if not note:
        return ""
    lines = note.strip().split('\n')
    formatted_lines = []
    for line in lines:
        if line.strip():
            formatted_lines.append(f"\t- {line}")
    return '\n' + '\n'.join(formatted_lines) if formatted_lines else ""

def generate_md_content_with_title(tasks, project_id, task_tags, project_status):
    """Generate Markdown content for a given project, considering the task completion status and using the task that matches the project_id as the title."""
    content = ""

    # Find the task that matches the project_id and use it as the title
    title_task = None
    for task in tasks:
        if task[1] == project_id:
            title_task = task
            tasks.remove(task)
            break

    if title_task:
        (task_name, task_identifier, task_note, _, _, is_completed, _, is_flagged,
         date_completed, date_due, date_planned, date_to_start) = title_task
        formatted_note = format_note_as_subitems(task_note)
        # Include completion date for project title if completed
        dates_str = format_task_dates(date_completed if is_completed else None, date_due, date_planned, date_to_start)
        tags_str = format_task_tags(task_tags.get(task_identifier, []), project_status)
        flag_str = " 🔼" if is_flagged else ""
        content += f"# {task_name}{dates_str}{tags_str}{flag_str}{formatted_note}\n\n"

    # Add the rest of the tasks
    for (task_name, task_identifier, task_note, _, _, is_completed, is_dropped, is_flagged,
         date_completed, date_due, date_planned, date_to_start) in tasks:
        checkbox = "- [x]" if is_completed else ("- [c]" if is_dropped else "- [ ]")

        # Format dates - include completion date only for completed tasks
        dates_str = format_task_dates(
            date_completed if is_completed else None,
            date_due,
            date_planned,
            date_to_start
        )

        # Format tags
        tags_str = format_task_tags(task_tags.get(task_identifier, []), project_status)

        # Format flagged
        flag_str = " 🔼" if is_flagged else ""

        # Build task line without OmniFocus link
        task_line = f"{checkbox} {task_name}{dates_str}{tags_str}{flag_str}"

        formatted_note = format_note_as_subitems(task_note)
        content += f"{task_line}{formatted_note}\n"

    return content

def create_md_files(tasks_with_project_info, project_metadata, task_tags, output_directory):
    """Create Markdown files based on project name, project identifier and metadata, considering the task completion status."""
    tasks_grouped_by_project = defaultdict(list)
    for task in tasks_with_project_info:
        project_name, project_id = task[3], task[4]
        tasks_grouped_by_project[(project_name, project_id)].append(task)

    # Group by filename to handle multiple projects with same name
    files_by_name = defaultdict(list)
    for (project_name, project_id), tasks in tasks_grouped_by_project.items():
        project_info = project_metadata.get(project_id, (project_id, "Untitled", "N/A"))
        project_status = project_info[2]

        # Add status to filename unless it's 'active'
        status_suffix = f" ({project_status})" if project_status.lower() != 'active' else ""
        sanitized_name = sanitize_filename(f"{project_name if project_name else 'Inbox'}{status_suffix}")
        files_by_name[sanitized_name].append((project_name, project_id, tasks, project_status))

    os.makedirs(output_directory, exist_ok=True)

    for filename, project_groups in files_by_name.items():
        file_path = os.path.join(output_directory, f"{filename}.md")

        # Combine all projects with the same filename
        combined_content = ""
        for project_name, project_id, tasks, project_status in project_groups:
            md_metadata = generate_md_metadata(project_metadata.get(project_id, (project_id, "Untitled", "N/A")))
            project_content = "---\n" + md_metadata + "---\n" + generate_md_content_with_title(tasks, project_id, task_tags, project_status)
            combined_content += project_content + "\n\n"

        # Check if file already exists and content has changed
        if os.path.exists(file_path):
            with open(file_path, 'r') as md_file:
                existing_content = md_file.read()
            # If content hasn't changed, skip writing to the file
            if compute_md5(existing_content) == compute_md5(combined_content.strip()):
                continue

        with open(file_path, 'w') as md_file:
            md_file.write(combined_content.strip())

database_path = None
for root, dirs, files in os.walk(os.path.expanduser("~/Library/Group Containers")):
    if "OmniFocusDatabase.db" in files and "OmniFocus4" in root:
        database_path = os.path.join(root, "OmniFocusDatabase.db")
        break

if not database_path:
    raise Exception("OmniFocus 4 database not found in ~/Library/Group Containers")

print(f"Database path: {database_path}")
output_directory = "omnifocus_md"
tasks_with_project_info = fetch_tasks_with_project_info(database_path)
project_metadata = fetch_projects_with_metadata_from_projectinfo(database_path)
task_tags = fetch_task_tags(database_path)
create_md_files(tasks_with_project_info, project_metadata, task_tags, output_directory)
