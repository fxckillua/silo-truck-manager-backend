from flask import Flask
from flask_cors import CORS
from config import Config
from database import db
from routes.auth_routes import auth_bp
from routes.truck_routes import truck_bp
from routes.maintenance_routes import maintenance_bp
from routes.notification_routes import notification_bp
from routes.user_routes import user_bp

app = Flask(__name__)
app.config.from_object(Config)

# 🔴 CORS CONFIGURADO EXPLICITAMENTE
CORS(
    app,
    resources={r"/*": {"origins": [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://192.168.0.105:8080",   # IP da rede local (Vite Network)
        "http://26.240.168.24:8080",
        "http://172.20.10.3:8080", # IP do meu celular
        "http://192.168.15.68:8080",
        "http://10.1.170.153:8080/",
        "http://192.168.0.102:8080"  # IP virtual (se você usar esse)
    ]}},
    supports_credentials=True,
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

db.init_app(app)

app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(truck_bp, url_prefix="/trucks")
app.register_blueprint(maintenance_bp, url_prefix="/maintenances")
app.register_blueprint(notification_bp, url_prefix="/notifications")
app.register_blueprint(user_bp, url_prefix="/users")


@app.route("/")
def index():
    return {"message": "API Gestão de Frota rodando"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
