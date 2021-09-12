from os import getenv
from flask import Flask, request, abort
from dotenv import load_dotenv
from datetime import datetime
from requests import post, HTTPError
from pathlib import Path
import json

# Loading .env file
load_dotenv()


class CodeRequest:
    _discord_client_id: str = getenv("DISCORD_CLIENT_ID")
    _discord_client_secret: str = getenv("DISCORD_CLIENT_SECRET")
    _discord_redirect_url: str = getenv("DISCORD_REDIRECT_URL")

    def __init__(self, code: str):
        self._code: str = code
        self.failed = False
        self._data = None
        # Timestamp of the request
        self._timestamp = str(datetime.now())

    def authenticate(self):
        # Do request to discord
        auth_request = post("https://discord.com/api/oauth2/token", data={
            "client_id": self._discord_client_id,
            "client_secret": self._discord_client_secret,
            "grant_type": "authorization_code",
            "code": self._code,
            "redirect_uri": self._discord_redirect_url
        }, headers={"Content-Type": "application/x-www-form-urlencoded"})

        try:
            auth_request.raise_for_status()
            self._data = auth_request.json()
        except (HTTPError, json.JSONDecodeError):
            self.failed = True
            return self

        self._write()

        return self

    def _write(self):
        # Create file if not exists
        Path("./auths").mkdir(exist_ok=True)
        # Open and write file
        with open(f"./auths/{self._timestamp.replace(':', '-')}.json", "w", encoding="UTF-8") as file:
            json.dump(self._data, file, indent=4)


web_app = Flask(__name__)


@web_app.route("/", methods=["GET"])
def apply_discord_code():
    # Check for code from discord
    discord_code: str = request.args.get("code")
    if discord_code is None:
        abort(400)

    # Make request and check if failed
    if CodeRequest(discord_code).authenticate().failed:
        abort(400)

    return "", 204
