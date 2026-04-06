from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    current_app,
    session,
    send_from_directory,
    send_file,
)
from app import api
from app import db
from app.models import Setting, Download
from app.download_manager import download_manager
from flask_paginate import Pagination, get_page_parameter
import os
import threading

main = Blueprint("main", __name__)

@main.route("/captioning")
def captioning():
    return render_template("captioning.html")

@main.route("/gallery")
def gallery():
    return render_template("gallery.html")

@main.record
def record(state):
    download_manager.init_app(state.app)


@main.route("/")
def index():
    # Get NSFW filter parameter
    nsfw = request.args.get("nsfw", "false")

    # Get random models from the API
    try:
        params = {"limit": 10, "nsfw": nsfw == "true"}
        response = api.get_models(params, api_key=session.get("api_key"))
        random_models = response.get("items", [])
    except Exception as e:
        flash(f"Error fetching models from API: {e}", "error")
        random_models = []

    # Get featured images from the models
    featured_images = []
    for model in random_models:
        if model.get("modelVersions"):
            for version in model["modelVersions"]:
                if version.get("images"):
                    for img in version["images"]:
                        img_with_id = dict(img)
                        img_with_id["model_id"] = model.get("id")
                        featured_images.append(img_with_id)
    featured_images = featured_images[:5]

    # Get model types and base models from the API response
    model_types = list(set(model["type"] for model in random_models if model.get("type")))
    base_models = list(
        set(
            version["baseModel"]
            for model in random_models
            if model.get("modelVersions")
            for version in model["modelVersions"]
            if version.get("baseModel")
        )
    )

    return render_template(
        "index.html",
        random_models=random_models,
        featured_images=featured_images,
        model_types=model_types,
        base_models=base_models,
        current_nsfw=nsfw,
    )


# Constants for filters
MODEL_TYPES = [
    "Checkpoint",
    "Embedding",
    "Hypernetwork",
    "AestheticGradient",
    "LORA",
    "LyCORIS",
    "DoRA",
    "Controlnet",
    "Upscaler",
    "Motion",
    "VAE",
    "Poses",
    "Wildcards",
    "Workflows",
    "Detection",
    "Other",
]

SORT_OPTIONS = [
    ("Highest Rated", "Highest Rated"),
    ("Most Downloaded", "Most Downloaded"),
    ("Newest", "Newest"),
]

PERIOD_OPTIONS = [
    ("Day", "Day"),
    ("Week", "Week"),
    ("Month", "Month"),
    ("Year", "Year"),
    ("AllTime", "All Time"),
]

BASE_MODELS = [
    "Aura Flow",
    "Chroma",
    "CogVideoX",
    "Flux.1 S",
    "Flux.1 D",
    "Flux.1 Krea",
    "Flux.1 Kontext",
    "HiDream",
    "Hunyuan 1",
    "Hunyuan Video",
    "Illustrious",
    "Kolors",
    "LTXV",
    "Lumina",
    "Mochi",
    "NoobAI",
    "Other",
    "PixArt a",
    "PixArt Σ",
    "Pony",
    "Pony V7",
    "Qwen",
    "SD 1.4",
    "SD 1.5",
    "SD 1.5 LCM",
    "SD 1.5 Hyper",
    "SD 2.0",
    "SD 2.1",
    "SDXL 1.0",
    "SDXL Lightning",
    "SDXL Hyper",
    "Wan Video 1.3B t2v",
    "Wan Video 14B t2v",
    "Wan Video 14B i2v 480p",
    "Wan Video 14B i2v 720p",
    "Wan Video 2.2 TI2V-5B",
    "Wan Video 2.2 I2V-A14B",
    "Wan Video 2.2 T2V-A14B",
    "Wan Video 2.5 T2V",
    "Wan Video 2.5 I2V",
]

CHECKPOINT_TYPE_OPTIONS = [
    ("All", "All"),
    ("Trained", "Trained"),
    ("Merge", "Merge"),
]

FILE_FORMAT_OPTIONS = [
    ("SafeTensor", "SafeTensor"),
    ("PickleTensor", "PickleTensor"),
    ("GGUF", "GGUF"),
    ("Diffusers", "Diffusers"),
    ("Core ML", "Core ML"),
    ("ONNX", "ONNX"),
]

MODEL_STATUS_OPTIONS = [
    ("EarlyAccess", "Early Access"),
    ("OnSiteGeneration", "On-site Generation"),
    ("Featured", "Featured"),
]


@main.route("/models")
def models():
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = current_app.config["MODELS_PER_PAGE"]

    # Filter options
    type_filter = request.args.get("type")
    base_model_filter = request.args.get("base_model")
    sort_by = request.args.get("sort", "Newest")
    period = request.args.get("period", "AllTime")
    nsfw = request.args.get("nsfw", "false")
    tags = request.args.getlist("tags")
    
    # New filters
    checkpoint_type = request.args.get("checkpoint_type")
    file_format = request.args.get("format")
    status = request.args.get("status")

    # Fetch models from the API
    try:
        params = {
            "page": page,
            "limit": per_page,
            "types": type_filter,
            "sort": sort_by,
            "period": period,
            "nsfw": nsfw == "true",
            "tags": ",".join(tags),
        }
        if base_model_filter:
            params["baseModels"] = base_model_filter
            
        if checkpoint_type and checkpoint_type != "All":
            params["checkpointType"] = checkpoint_type
            
        if file_format:
            params["format"] = file_format
            
        if status:
            if status == "EarlyAccess":
                params["earlyAccess"] = "true"
            elif status == "OnSiteGeneration":
                params["supportsGeneration"] = "true"
            elif status == "Featured":
                params["featured"] = "true"

        response = api.get_models(params, api_key=session.get("api_key"))
        models = response.get("items", [])
        total = response.get("metadata", {}).get("totalItems", 0)
    except Exception as e:
        flash(f"Error fetching models from API: {e}", "error")
        models = []
        total = 0

    # Create a Pagination object
    pagination = Pagination(
        page=page, per_page=per_page, total=total, css_framework="bootstrap4"
    )

    # Get popular tags from the API
    try:
        tags_params = {"limit": 10, "sort": "Most Models"}
        tags_response = api.get_tags(tags_params, api_key=session.get("api_key"))
        # The tags API returns items with 'name' and 'link', but no count.
        # We will just use the name.
        popular_tags = [tag["name"] for tag in tags_response.get("items", [])]
    except Exception as e:
        flash(f"Error fetching tags from API: {e}", "error")
        popular_tags = []

    return render_template(
        "models.html",
        models=models,
        pagination=pagination,
        model_types=MODEL_TYPES,
        sort_options=SORT_OPTIONS,
        period_options=PERIOD_OPTIONS,
        base_models=BASE_MODELS,
        checkpoint_type_options=CHECKPOINT_TYPE_OPTIONS,
        file_format_options=FILE_FORMAT_OPTIONS,
        model_status_options=MODEL_STATUS_OPTIONS,
        popular_tags=popular_tags,
        current_filters={
            "type": type_filter,
            "base_model": base_model_filter,
            "sort": sort_by,
            "period": period,
            "nsfw": nsfw,
            "tags": tags,
            "checkpoint_type": checkpoint_type,
            "format": file_format,
            "status": status,
        },
    )


@main.route("/models/<int:model_id>")
def model_detail(model_id):
    try:
        model = api.get_model(model_id, api_key=session.get("api_key"))
    except Exception as e:
        flash(f"Error fetching model from API: {e}", "error")
        return redirect(url_for("main.index"))

    versions = model.get("modelVersions", [])
    preview_images = []
    for version in versions:
        preview_images.extend(version.get("images", []))

    tags = model.get("tags", [])

    # The API does not directly provide similar or related models.
    # We will leave these empty for now.
    similar_models = []
    related_by_type = []
    model_types = []

    return render_template(
        "model_detail.html",
        model=model,
        versions=versions,
        preview_images=preview_images,
        tags=tags,
        similar_models=similar_models,
        related_by_type=related_by_type,
        model_types=model_types,
    )


@main.route("/creators")
def creators():
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = current_app.config["CREATORS_PER_PAGE"]

    # Sort options
    sort_by = request.args.get("sort", "most-models")

    # Fetch creators from the API
    try:
        params = {"page": page, "limit": per_page, "sort": sort_by}
        response = api.get_creators(params, api_key=session.get("api_key"))
        creators = response.get("items", [])
        total = response.get("metadata", {}).get("totalItems", 0)
    except Exception as e:
        flash(f"Error fetching creators from API: {e}", "error")
        creators = []
        total = 0

    # Create a Pagination object
    pagination = Pagination(
        page=page, per_page=per_page, total=total, css_framework="bootstrap4"
    )

    # The API does not directly provide model types for the creator list.
    model_types = []

    return render_template(
        "creators.html",
        creators=creators,
        pagination=pagination,
        current_sort=sort_by,
        model_types=model_types,
    )


@main.route("/creators/<int:creator_id>")
def creator_detail(creator_id):
    try:
        creator = api.get_creator(creator_id, api_key=session.get("api_key"))
    except Exception as e:
        flash(f"Error fetching creator from API: {e}", "error")
        return redirect(url_for("main.creators"))

    # Get creator's models
    try:
        params = {"username": creator.get("username")}
        response = api.get_models(params, api_key=session.get("api_key"))
        models = response.get("items", [])
    except Exception as e:
        flash(f"Error fetching models from API: {e}", "error")
        models = []

    # Calculate statistics
    model_count = len(models)
    download_count = sum(model.get("stats", {}).get("downloadCount", 0) for model in models)

    # The API does not directly provide model types for the creator's model list.
    model_types = []

    return render_template(
        "creator_detail.html",
        creator=creator,
        models=models,
        model_count=model_count,
        download_count=download_count,
        model_types=model_types,
    )


@main.route("/search")
def search():
    query = request.args.get("q", "")
    base_model_filter = request.args.get("base_model", "")
    nsfw = request.args.get("nsfw", "false")
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = current_app.config["MODELS_PER_PAGE"]

    if not query:
        return redirect(url_for("main.index"))

    # Search models
    try:
        params = {
            "page": page,
            "limit": per_page,
            "query": query,
            "baseModels": base_model_filter,
            "nsfw": nsfw == "true",
        }
        response = api.get_models(params, api_key=session.get("api_key"))
        models = response.get("items", [])
        total = response.get("metadata", {}).get("totalItems", 0)
    except Exception as e:
        flash(f"Error fetching models from API: {e}", "error")
        models = []
        total = 0

    # Create a Pagination object for models
    model_pagination = Pagination(
        page=page, per_page=per_page, total=total, css_framework="bootstrap4"
    )

    # Search creators
    try:
        params = {"query": query, "limit": 5}
        response = api.get_creators(params, api_key=session.get("api_key"))
        creators = response.get("items", [])
    except Exception as e:
        flash(f"Error fetching creators from API: {e}", "error")
        creators = []

    # The API does not directly provide base models and model types for the search results.
    base_models = []
    model_types = []

    return render_template(
        "search.html",
        query=query,
        models=models,
        model_pagination=model_pagination,
        creators=creators,
        base_models=base_models,
        model_types=model_types,
        current_base_model=base_model_filter,
        current_nsfw=nsfw,
    )


@main.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "clear":
            session.pop("api_key", None)
            session.pop("user", None)
            flash("API Key cleared.", "info")
        else:
            # Handle API Key
            api_key = request.form.get("api_key")
            if api_key:
                user = api.get_user(api_key)
                session["api_key"] = api_key
                if user:
                    session["user"] = user
                    flash(f"Logged in as {user.get('username', 'Unknown')}", "success")
                else:
                    session.pop("user", None)
                    flash("API Key saved, but could not verify user details.", "warning")
            
            # Handle Directory Settings
            for model_type in MODEL_TYPES:
                dir_key = f"dir_{model_type}"
                dir_value = request.form.get(dir_key)
                if dir_value:
                    setting = Setting.query.get(dir_key)
                    if not setting:
                        setting = Setting(key=dir_key)
                        db.session.add(setting)
                    setting.value = dir_value
            
            db.session.commit()
            flash("Settings saved.", "success")
        
        return redirect(url_for("main.settings"))

    api_key = session.get("api_key")
    user = session.get("user")
    
    # Load directory settings
    directories = {}
    for model_type in MODEL_TYPES:
        setting = Setting.query.get(f"dir_{model_type}")
        directories[model_type] = setting.value if setting else ""
        
    return render_template("settings.html", api_key=api_key, user=user, model_types=MODEL_TYPES, directories=directories)


@main.route("/download/<int:model_id>/<int:version_id>")
def download(model_id, version_id):
    api_key = session.get("api_key")
    if not api_key:
        flash("You must be logged in to download models.", "warning")
        return redirect(url_for("main.settings"))

    download_manager.add_task(model_id, version_id, api_key)
    
    flash("Download added to queue.", "info")
    return redirect(request.referrer or url_for("main.model_detail", model_id=model_id))

@main.route("/api/downloads/status")
def download_status():
    return jsonify(download_manager.get_status())

@main.route("/settings/scan", methods=["POST"])
def scan_library():
    api_key = session.get("api_key")
    # Allow scan even if not logged in? 
    # Yes, but API lookup might be rate limited or restricted.
    # But we pass api_key if available.
    
    download_manager.add_task(task_type='scan', api_key=api_key)
    flash("Library scan started in background.", "info")
    return redirect(url_for("main.settings"))

@main.context_processor
def inject_downloaded_models():
    if not session.get("api_key"): # Only check if logged in? Or always?
        # Let's check always, but maybe cache or optimize?
        # For now, just query.
        pass
        
    # Get all downloads: {model_id: latest_version_id}
    # If multiple versions downloaded, we might want to know.
    # But for "Update Available", we need to know the *latest* downloaded version vs current.
    # Actually, we just need to know IF we have it, and WHICH version we have.
    # If we have version A, and model has version B (newer), it's an update.
    # Let's return a dict: {model_id: [list of version_ids]}
    
    downloads = Download.query.all()
    downloaded_models = {}
    for d in downloads:
        if d.model_id not in downloaded_models:
            downloaded_models[d.model_id] = []
        downloaded_models[d.model_id].append(d.version_id)
        
    return dict(downloaded_models=downloaded_models)

@main.route("/library")
def library():
    type_filter = request.args.get("type")
    
    query = Download.query
    if type_filter:
        query = query.filter_by(type=type_filter)
        
    models = query.all()
    
    # Get unique types for sidebar
    all_types = db.session.query(Download.type).distinct().all()
    types = [t[0] for t in all_types if t[0]]
    
    return render_template("library.html", models=models, types=types, current_type=type_filter)

@main.route("/files/<path:filename>")
def serve_file(filename):
    # Ensure filename is absolute
    if not filename.startswith('/'):
        filename = '/' + filename
        
    if not os.path.exists(filename):
        return "File not found", 404
        
    return send_file(filename)
