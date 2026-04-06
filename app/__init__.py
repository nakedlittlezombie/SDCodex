from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app.config import Config

db = SQLAlchemy()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    
    from app.routes import main
    app.register_blueprint(main)
    
    from app.api_gallery import gallery
    app.register_blueprint(gallery)
    
    with app.app_context():
        # Import models to ensure they are registered with SQLAlchemy
        from app import models
        db.create_all()
    
    return app