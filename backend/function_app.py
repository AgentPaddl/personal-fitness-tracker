import azure.functions as func

from api.food_analysis import bp as food_analysis_bp
from api.health import bp as health_bp
from config import validate_config

# Fail closed at startup on invalid configuration (e.g. a malformed gateway
# URL or an out-of-bounds timeout) rather than at first request time.
validate_config()

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
app.register_functions(health_bp)
app.register_functions(food_analysis_bp)