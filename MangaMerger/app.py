from flask import Flask, render_template, jsonify, request
import json, os
from utils.file_scanner import scan_folders
from utils.combiner import combine_pdf, combine_cbz
from utils.history_manager import update_history
import sys
import logging

CONFIG_FILE = "config.json"

# --- Logging setup ---
LOG_FILE = os.path.join(os.path.dirname(__file__), "log.txt")

# Create a basic file logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Replace default print() to also log
def print(*args, **kwargs):
    text = " ".join(str(a) for a in args)
    logger.info(text)

from logging.handlers import RotatingFileHandler
for h in list(logger.handlers):
    if isinstance(h, logging.FileHandler):
        logger.removeHandler(h)
logger.addHandler(RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3))


def load_config():
    with open(CONFIG_FILE, "r") as f:
        cfg = json.load(f)
    if "sort_mode" not in cfg:
        cfg["sort_mode"] = "name"
    return cfg

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

app = Flask(__name__, static_folder="static", template_folder="templates")
config = load_config()

# ----------------------------------------------------
# Folder tree generator (nested structure for sidebar)
# ----------------------------------------------------
def build_folder_tree(path):
    """Recursively build folder tree for the left panel with chapter counts."""
    tree = []
    try:
        for item in sorted(os.listdir(path)):
            full = os.path.join(path, item)
            if os.path.isdir(full) and not item.startswith("."):
                # Count .pdf and .cbz files directly inside this folder
                files = [
                    f for f in os.listdir(full)
                    if f.lower().endswith((".pdf", ".cbz"))
                ]
                subtree = build_folder_tree(full)
                tree.append({
                    "name": item,
                    "path": os.path.relpath(full, config["main_path"]).replace("\\", "/"),
                    "count": len(files),
                    "children": subtree
                })
        return tree
    except Exception as e:
        print(f"⚠️ Error building tree at {path}: {e}")
        return []

# ---------- API: Folder Tree ----------
@app.route("/api/tree")
def api_tree():
    try:
        base = config["main_path"]
        tree = build_folder_tree(base)
        return jsonify(tree)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------- API: Folder Content ----------
@app.route("/api/folder")
def api_folder():
    """Return .pdf and .cbz files in the selected folder."""
    rel_path = request.args.get("path")
    if not rel_path:
        return jsonify({"error": "Missing path"}), 400
    folder_path = os.path.join(config["main_path"], rel_path)
    if not os.path.exists(folder_path):
        return jsonify({"error": "Folder not found"}), 404

    try:
        files = [f for f in os.listdir(folder_path)
                 if f.lower().endswith((".pdf", ".cbz"))]
        mode = config.get("sort_mode", "name")
        if mode == "date":
            files.sort(key=lambda x: os.path.getmtime(os.path.join(folder_path, x)))
        else:
            files.sort(key=lambda x: x.lower())
        return jsonify({"chapters": files})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------------------------------------------
# Recursive History Loader
# ----------------------------------------------------
def get_all_histories():
    """Recursively finds all history.json files and returns summaries."""
    main_path = config["main_path"]
    results = []
    for root, dirs, files in os.walk(main_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if "history.json" in files:
            history_path = os.path.join(root, "history.json")
            try:
                with open(history_path, "r") as f:
                    data = json.load(f)
                if not data:
                    continue
                last_vol = list(data.keys())[-1]
                last_entry = data[last_vol]
                last_date = last_entry.get("date", "Unknown")
                last_chapter = (
                    last_entry["chapters"][-1] if last_entry.get("chapters") else "None"
                )
                relative_name = os.path.relpath(root, main_path).replace("\\", "/")
                results.append({
                    "manga": relative_name,
                    "last_date": last_date,
                    "last_volume": last_vol,
                    "last_chapter": last_chapter
                })
            except Exception as e:
                print(f"⚠️ Error reading {history_path}: {e}")
                continue
    results.sort(key=lambda x: x["manga"].lower())
    return results

@app.route("/history")
def history_page():
    histories = get_all_histories()
    return render_template("history.html", histories=histories)

@app.route("/api/history/view", methods=["POST"])
def view_full_history():
    data = request.json
    manga = data.get("manga")
    history_path = os.path.join(config["main_path"], manga, "history.json")
    if not os.path.exists(history_path):
        return jsonify({"error": "No history found"}), 404
    try:
        with open(history_path, "r") as f:
            hist = json.load(f)
        return jsonify({"success": True, "data": hist})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/history/delete", methods=["POST"])
def delete_history_entry():
    data = request.json
    manga = data.get("manga")
    volume = data.get("volume")
    history_path = os.path.join(config["main_path"], manga, "history.json")
    if not os.path.exists(history_path):
        return jsonify({"error": "History file not found"}), 404
    try:
        with open(history_path, "r") as f:
            hist = json.load(f)
        if volume in hist:
            del hist[volume]
            with open(history_path, "w") as f:
                json.dump(hist, f, indent=2)
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Volume not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------------------------------------------
# Combine and Main Routes
# ----------------------------------------------------
@app.route("/api/combine", methods=["POST"])
def api_combine():
    data = request.json
    folder_name = data["folder"]
    selected_files = data["selected"]
    volume_name = data["name"]
    export_type = data["type"]

    folder_path = os.path.join(config["main_path"], folder_name)
    export_path = config["export_path"]

    if export_type == "pdf":
        result = combine_pdf(folder_path, selected_files, export_path, volume_name)
    else:
        result = combine_cbz(folder_path, selected_files, export_path, volume_name)

    if result:
        update_history(folder_path, volume_name, selected_files, export_type)
        return jsonify({"success": True, "path": result})
    else:
        return jsonify({"success": False, "error": "Combine failed."}), 500

@app.route("/")
def index():
    return render_template("index.html", main_path=config["main_path"], export_path=config["export_path"])

@app.route("/settings", methods=["GET", "POST"])
def settings():
    global config
    if request.method == "POST":
        data = request.json
        if "sort_mode" not in data:
            data["sort_mode"] = config.get("sort_mode", "name")
        save_config(data)
        config = load_config()
        return jsonify({"status": "updated"})
    return render_template("settings.html", config=config)

@app.route("/about")
def about():
    return "<h1>Manual Manga Combiner</h1><p>Web tool for merging manga chapters.</p>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.get("port", 3636), debug=True)
