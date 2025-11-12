import os

def scan_folders(base_path):
    """
    Recursively lists ALL subfolders under base_path, even if empty.
    These appear in the left panel regardless of content.
    """
    results = []

    for root, dirs, files in os.walk(base_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if root != base_path:
            relative = os.path.relpath(root, base_path)
            results.append({
                "name": relative.replace("\\", "/"),
                "count": len(files),
                "chapters": []  # filled later when user clicks folder
            })

    results.sort(key=lambda x: x["name"].lower())
    return results
