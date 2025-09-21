import sqlite3
from collections import defaultdict
import os
import hashlib
import sys

def compute_md5(text):
    """Compute MD5 hash of the given text."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def format_task_dates(date_completed, date_due, date_planned, date_to_start, date_added, date_modified):
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
    if date_added:
        date_parts.append(f"➕ {format_date(date_added)}")
    if date_modified:
        date_parts.append(f"✏️ {format_date(date_modified)}")

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
        t1.dateToStart AS date_to_start,
        t1.dateAdded AS date_added,
        t1.dateModified AS date_modified
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

def fetch_task_attachments(database_path):
    """Fetch all attachments for tasks as a dictionary mapping task_id to list of attachment info."""
    query = """
    SELECT
        task AS task_id,
        name AS attachment_name,
        size AS attachment_size,
        previewPNGData AS preview_data,
        persistentIdentifier AS attachment_id,
        dataIdentifier AS data_identifier
    FROM
        Attachment
    WHERE
        task IS NOT NULL
    ORDER BY
        task, creationOrdinal
    """
    task_attachments = defaultdict(list)
    with sqlite3.connect(database_path) as conn:
        results = conn.execute(query).fetchall()
        for task_id, name, size, preview_data, attachment_id, data_identifier in results:
            attachment_info = {
                'name': name,
                'size': size,
                'preview_data': preview_data,
                'attachment_id': attachment_id,
                'dataIdentifier': data_identifier
            }
            task_attachments[task_id].append(attachment_info)
    return dict(task_attachments)

def fetch_folder_hierarchy(database_path):
    """Fetch folder hierarchy as a dictionary mapping folder_id to folder path."""
    query = """
    SELECT
        persistentIdentifier,
        name,
        parent
    FROM
        Folder
    ORDER BY
        rank
    """

    folders = {}
    folder_paths = {}

    with sqlite3.connect(database_path) as conn:
        results = conn.execute(query).fetchall()

        # First pass: store all folders
        for folder_id, name, parent_id in results:
            folders[folder_id] = {'name': name, 'parent': parent_id}

        # Second pass: build full paths
        def get_folder_path(folder_id):
            if folder_id not in folders:
                return ""

            if folder_id in folder_paths:
                return folder_paths[folder_id]

            folder = folders[folder_id]
            if folder['parent']:
                parent_path = get_folder_path(folder['parent'])
                path = f"{parent_path}/{folder['name']}" if parent_path else folder['name']
            else:
                path = folder['name']

            folder_paths[folder_id] = path
            return path

        # Build paths for all folders
        for folder_id in folders:
            get_folder_path(folder_id)

    return folder_paths

def fetch_projects_with_metadata_from_projectinfo(database_path):
    """Get metadata (name, identifier, status, and folder) for projects from the ProjectInfo table."""
    query = """
    SELECT
        Task.name AS project_name,
        Task.persistentIdentifier AS project_identifier,
        ProjectInfo.effectiveStatus AS project_status,
        ProjectInfo.folder AS folder_id
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
    return {project_id: (project_id, project_name, project_status, folder_id) for project_name, project_id, project_status, folder_id in results}

def sanitize_filename(filename):
    """Sanitize the filename by removing or replacing special characters."""
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename

def extract_attachment_from_backup(data_identifier, attachment_name, output_path, backup_dir):
    """Extract attachment from OmniFocus backup zip file."""
    import zipfile
    import glob

    # Find the most recent backup
    backup_folders = glob.glob(os.path.join(backup_dir, "OmniFocus *.ofocus-backup"))
    if not backup_folders:
        return False

    # Sort by modification time to get the most recent
    backup_folders.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    latest_backup = backup_folders[0]

    # Construct path to the data zip file
    zip_path = os.path.join(latest_backup, "data", f"{data_identifier}.zip")

    if not os.path.exists(zip_path):
        return False

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            # Extract the file directly to output path
            for file_info in zip_file.filelist:
                with zip_file.open(file_info) as source, open(output_path, 'wb') as target:
                    target.write(source.read())
                return True
    except Exception:
        return False

    return False

def save_attachment_previews(task_attachments, output_directory, backup_dir=None):
    """Save attachment images to disk, preferring full-resolution from backups when available."""
    import os

    attachments_dir = os.path.join(output_directory, "attachments")
    os.makedirs(attachments_dir, exist_ok=True)

    task_attachment_refs = {}

    for task_id, attachments in task_attachments.items():
        attachment_refs = []
        for i, attachment in enumerate(attachments):
            # Create sanitized filename
            base_name = sanitize_filename(attachment['name'] or f"attachment_{i}")
            filename = f"{task_id}_{base_name}"
            file_path = os.path.join(attachments_dir, filename)

            # Format size for display
            size_kb = attachment['size'] / 1024 if attachment['size'] else 0
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"

            # Try to get full-resolution from backup first
            full_res_extracted = False
            if backup_dir and 'dataIdentifier' in attachment and attachment['dataIdentifier']:
                full_res_extracted = extract_attachment_from_backup(
                    attachment['dataIdentifier'],
                    attachment['name'],
                    file_path,
                    backup_dir
                )

            # If no full-res available, fall back to preview
            if not full_res_extracted and attachment['preview_data']:
                # Save preview PNG data
                with open(file_path, 'wb') as f:
                    f.write(attachment['preview_data'])

                attachment_refs.append({
                    'name': attachment['name'],
                    'size_str': size_str,
                    'file_path': f"attachments/{filename}",
                    'has_preview': True,
                    'is_full_res': False
                })
            elif full_res_extracted:
                attachment_refs.append({
                    'name': attachment['name'],
                    'size_str': size_str,
                    'file_path': f"attachments/{filename}",
                    'has_preview': True,
                    'is_full_res': True
                })
            else:
                # No attachment data available
                attachment_refs.append({
                    'name': attachment['name'],
                    'size_str': size_str,
                    'file_path': None,
                    'has_preview': False,
                    'is_full_res': False
                })

        if attachment_refs:
            task_attachment_refs[task_id] = attachment_refs

    return task_attachment_refs

def generate_md_metadata(project_info):
    """Generate Markdown metadata for a given project."""
    project_id, project_name, project_status, folder_id = project_info
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

def format_attachments(attachment_refs):
    """Format attachment references for display in markdown."""
    if not attachment_refs:
        return ""

    attachment_lines = []
    for attachment in attachment_refs:
        if attachment['has_preview'] and attachment['file_path']:
            # Inline image with size info
            line = f"\t- 📎 ![{attachment['name']}]({attachment['file_path']}) ({attachment['size_str']})"
        else:
            # Text reference only
            line = f"\t- 📎 {attachment['name']} ({attachment['size_str']})"
        attachment_lines.append(line)

    return '\n' + '\n'.join(attachment_lines)

def generate_md_content_with_title(tasks, project_id, task_tags, project_status, task_attachment_refs):
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
         date_completed, date_due, date_planned, date_to_start, date_added, date_modified) = title_task
        formatted_note = format_note_as_subitems(task_note)
        attachments_str = format_attachments(task_attachment_refs.get(task_identifier, []))
        # Include completion date for project title if completed
        dates_str = format_task_dates(date_completed if is_completed else None, date_due, date_planned, date_to_start, date_added, date_modified)
        tags_str = format_task_tags(task_tags.get(task_identifier, []), project_status)
        flag_str = " 🔼" if is_flagged else ""
        content += f"# {task_name}{dates_str}{tags_str}{flag_str}{formatted_note}{attachments_str}\n\n"

    # Add the rest of the tasks
    for (task_name, task_identifier, task_note, _, _, is_completed, is_dropped, is_flagged,
         date_completed, date_due, date_planned, date_to_start, date_added, date_modified) in tasks:
        checkbox = "- [x]" if is_completed else ("- [c]" if is_dropped else "- [ ]")

        # Format dates - include completion date only for completed tasks
        dates_str = format_task_dates(
            date_completed if is_completed else None,
            date_due,
            date_planned,
            date_to_start,
            date_added,
            date_modified
        )

        # Format tags
        tags_str = format_task_tags(task_tags.get(task_identifier, []), project_status)

        # Format flagged
        flag_str = " 🔼" if is_flagged else ""

        # Build task line without OmniFocus link
        task_line = f"{checkbox} {task_name}{dates_str}{tags_str}{flag_str}"

        formatted_note = format_note_as_subitems(task_note)
        attachments_str = format_attachments(task_attachment_refs.get(task_identifier, []))
        content += f"{task_line}{formatted_note}{attachments_str}\n"

    return content

def create_md_files(tasks_with_project_info, project_metadata, task_tags, folder_hierarchy, task_attachment_refs, output_directory):
    """Create Markdown files based on project name, project identifier and metadata, considering the task completion status."""
    tasks_grouped_by_project = defaultdict(list)
    for task in tasks_with_project_info:
        project_name, project_id = task[3], task[4]
        tasks_grouped_by_project[(project_name, project_id)].append(task)

    # Group by full file path (including folder) to handle multiple projects with same name
    files_by_path = defaultdict(list)
    for (project_name, project_id), tasks in tasks_grouped_by_project.items():
        project_info = project_metadata.get(project_id, (project_id, "Untitled", "N/A", None))
        project_status = project_info[2]
        folder_id = project_info[3]

        # Get folder path
        folder_path = folder_hierarchy.get(folder_id, "") if folder_id else ""

        # Add status to filename unless it's 'active'
        status_suffix = f" ({project_status})" if project_status.lower() != 'active' else ""
        sanitized_name = sanitize_filename(f"{project_name if project_name else 'Inbox'}{status_suffix}")

        # Create full path with folder and status subfolder
        if folder_path:
            sanitized_folder_path = "/".join(sanitize_filename(part) for part in folder_path.split("/"))

            # Add status subfolder for non-active projects
            if project_status.lower() != 'active':
                if project_status.lower() == 'inactive':
                    status_folder = f"({sanitize_filename(project_status.lower())})"
                else:
                    status_folder = f".({sanitize_filename(project_status.lower())})"
                full_path = f"{sanitized_folder_path}/{status_folder}/{sanitized_name}"
            else:
                full_path = f"{sanitized_folder_path}/{sanitized_name}"
        else:
            # For projects without folders, use status subfolder at root level
            if project_status.lower() != 'active':
                if project_status.lower() == 'inactive':
                    status_folder = f"({sanitize_filename(project_status.lower())})"
                else:
                    status_folder = f".({sanitize_filename(project_status.lower())})"
                full_path = f"{status_folder}/{sanitized_name}"
            else:
                full_path = sanitized_name

        files_by_path[full_path].append((project_name, project_id, tasks, project_status))

    for full_path, project_groups in files_by_path.items():
        file_path = os.path.join(output_directory, f"{full_path}.md")

        # Create directory structure if needed
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Combine all projects with the same file path
        combined_content = ""
        for project_name, project_id, tasks, project_status in project_groups:
            md_metadata = generate_md_metadata(project_metadata.get(project_id, (project_id, "Untitled", "N/A", None)))
            project_content = "---\n" + md_metadata + "---\n" + generate_md_content_with_title(tasks, project_id, task_tags, project_status, task_attachment_refs)
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

def reorganize_empty_folders(output_directory):
    """Reorganize empty folders or folders containing only dot folders into sibling dot folders."""
    import shutil

    # Walk through all directories
    for root, dirs, files in os.walk(output_directory, topdown=False):
        # Skip if this is the root output directory
        if root == output_directory:
            continue

        # Get relative path from output directory
        rel_path = os.path.relpath(root, output_directory)
        path_parts = rel_path.split(os.sep)

        # Skip if this is already a dot folder
        if any(part.startswith('.') for part in path_parts):
            continue

        # Check folder contents
        has_regular_files = len(files) > 0
        has_regular_dirs = any(not d.startswith('.') and not d.startswith('(') for d in dirs)
        has_dot_dirs = any(d.startswith('.') for d in dirs)
        has_dropped_dirs = any('.(dropped)' in d for d in dirs)

        # Determine if folder should be moved
        should_move = False
        target_status = None

        if not has_regular_files and not has_regular_dirs:
            # Folder contains only dot folders or is empty
            if has_dropped_dirs:
                target_status = "dropped"
                should_move = True
            elif has_dot_dirs:
                target_status = "done"
                should_move = True
            elif len(dirs) == 0:  # Completely empty
                target_status = "done"
                should_move = True

        if should_move:
            # Determine parent directory and create target path
            parent_dir = os.path.dirname(root)
            folder_name = os.path.basename(root)
            target_dir = os.path.join(parent_dir, f".({target_status})")
            target_path = os.path.join(target_dir, folder_name)

            # Create target directory if it doesn't exist
            os.makedirs(target_dir, exist_ok=True)

            # Move the folder
            if os.path.exists(target_path):
                # If target exists, merge contents
                for item in os.listdir(root):
                    src = os.path.join(root, item)
                    dst = os.path.join(target_path, item)
                    if os.path.isdir(src):
                        if os.path.exists(dst):
                            # Merge directories recursively
                            shutil.copytree(src, dst, dirs_exist_ok=True)
                            shutil.rmtree(src)
                        else:
                            shutil.move(src, dst)
                    else:
                        shutil.move(src, dst)
                # Remove empty source directory
                os.rmdir(root)
            else:
                # Move entire folder
                shutil.move(root, target_path)

            print(f"Moved empty folder '{rel_path}' to '.({target_status})/{folder_name}'")

def main():
    # Parse command line arguments
    backup_dir = None
    if len(sys.argv) > 1:
        backup_dir = sys.argv[1]
        if not os.path.exists(backup_dir):
            print(f"Error: Backup directory '{backup_dir}' does not exist")
            sys.exit(1)
        print(f"Using backup directory: {backup_dir}")
    else:
        print("No backup directory provided. Will use preview images only.")
        print("Usage: python omnifocus2md.py [backup_directory_path]")

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
    folder_hierarchy = fetch_folder_hierarchy(database_path)
    task_attachments = fetch_task_attachments(database_path)
    task_attachment_refs = save_attachment_previews(task_attachments, output_directory, backup_dir)
    create_md_files(tasks_with_project_info, project_metadata, task_tags, folder_hierarchy, task_attachment_refs, output_directory)

    # Reorganize empty folders after file creation
    reorganize_empty_folders(output_directory)

if __name__ == "__main__":
    main()
