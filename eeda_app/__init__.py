from pathlib import Path

from flask import Flask

from .analysis import blueprint as analysis_blueprint
from .charts import blueprint as charts_blueprint
from .datasets import blueprint as datasets_blueprint
from .edits import blueprint as edits_blueprint


def create_app():
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
    )
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
    app.register_blueprint(datasets_blueprint)
    app.register_blueprint(edits_blueprint)
    app.register_blueprint(analysis_blueprint)
    app.register_blueprint(charts_blueprint)
    return app
