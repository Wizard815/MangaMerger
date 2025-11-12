import os, json, datetime

def update_history(folder_path, volume_name, selected_files, export_type):
    history_path = os.path.join(folder_path, "history.json")

    if os.path.exists(history_path):
        with open(history_path, "r") as f:
            history = json.load(f)
    else:
        history = {}

    entry = {
        "type": export_type.upper(),
        "chapters": selected_files,
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    history[volume_name] = entry

    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)
