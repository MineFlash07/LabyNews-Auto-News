from datetime import datetime

from requests import post, patch


class Webhook:

    def __init__(self, url: str, target_role_id: int = None):
        self._url = url
        self._target_role = target_role_id

        # Old message objects
        self._sent_messages = {}

    def send(self, content: str = ""):
        json_payload = {
            "content": f"{content}",
            "tts": False,
        }
        # Add allowed mentions if not none
        if self._target_role is not None:
            json_payload["content"] = f"<@&{self._target_role}>\n" + json_payload["content"]
            json_payload["allowed_mentions"] = {
                "roles": [f"{self._target_role}"]
            }

        json_response: dict = post(self._url, json=json_payload).json()
        self._sent_messages[json_response["id"]] = json_response["content"]

    def edit(self, content_to_add: str, message_id: str):
        self._sent_messages[message_id] = f"{self._sent_messages[message_id]}\n**{datetime.now()}:** {content_to_add}"
        json_payload = {
            "content": self._sent_messages[message_id]
        }

        if self._target_role is not None:
            json_payload["allowed_mentions"] = {
                "roles": [f"{self._target_role}"]
            }

        patch(f"{self._url}/messages/{message_id}", json=json_payload)

