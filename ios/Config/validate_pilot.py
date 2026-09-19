"""Build-time validation of the opt-in pilot configuration; no network access."""

import os
import sys
from urllib.parse import urlsplit
from uuid import UUID


def validate(values):
    if values.get("PILOT_BUILD", "NO") != "YES":
        return
    if (values.get("CONFIGURATION") != "Release"
            or values.get("PRODUCT_BUNDLE_IDENTIFIER") != "com.benedikt.Trainingsplan"
            or values.get("DEVELOPMENT_TEAM") != "2SF7PV3WCD"
            or values.get("CURRENT_PROJECT_VERSION") not in {"5", "6", "7"}):
        raise ValueError("Pilot requires the unchanged Release app identity and reviewed build 5, 6 or 7.")
    for public, pilot in (("API_BASE_URL", "PILOT_API_BASE_URL"), ("ENTRA_TENANT_ID", "PILOT_ENTRA_TENANT_ID"),
                          ("ENTRA_CLIENT_ID", "PILOT_ENTRA_CLIENT_ID"), ("ENTRA_API_SCOPE", "PILOT_ENTRA_API_SCOPE")):
        if not values.get(pilot) or values.get(public) != values[pilot] or "$" in values[pilot]:
            raise ValueError("Pilot deployment outputs are missing or overridden.")
    url = urlsplit(values["API_BASE_URL"])
    if (url.scheme != "https" or not url.hostname or not url.hostname.endswith(".azurewebsites.net")
            or not url.hostname.startswith("pft-pilot-") or url.username or url.password
            or url.port not in (None, 443) or url.path != "/api" or url.query or url.fragment):
        raise ValueError("Pilot requires the private deployment's HTTPS backend output.")
    for name in ("ENTRA_TENANT_ID", "ENTRA_CLIENT_ID"):
        if str(UUID(values[name])) != values[name]:
            raise ValueError("Pilot requires concrete Entra deployment identifiers.")
    scope = values["ENTRA_API_SCOPE"]
    if not scope.startswith("api://") or not scope.endswith("/FoodAnalysis.Access"):
        raise ValueError("Pilot API scope is incomplete.")
    UUID(scope.removeprefix("api://").removesuffix("/FoodAnalysis.Access"))
    if values.get("ENTRA_REDIRECT_URI") != "msauth.com.benedikt.Trainingsplan://auth":
        raise ValueError("Pilot redirect must preserve the installed app identity.")


if __name__ == "__main__":
    try:
        validate(os.environ)
    except (ValueError, KeyError):
        print("error: Incomplete or incompatible pilot configuration. Generate Pilot.local.xcconfig from reviewed deployment outputs.", file=sys.stderr)
        raise SystemExit(1)