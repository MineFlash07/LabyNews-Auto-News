from requests import post


class Webhook:

    def __init__(self, url: str, target_role_id: int = None):
        self._url = url
        self._target_role = target_role_id

    def send(self, content: str = "", news: str = None):
        json_payload = {
            "content": f"{content}",
            "tts": False,
        }

        if news is not None and news != "":
            json_payload["content"] += f"\n\n```{news}```"
            news = news.replace("\n", "%0A").replace(" ", "%20")
            json_payload["components"] = [{
                "type": 1,
                "components": [{
                    "type": 2,
                    "style": 5,
                    "label": "Direct Tweet (Admin only)",
                    "url": f"https://twitter.com/intent/tweet?text={news}"
                }]
            }]

        # Add allowed mentions if not none
        if self._target_role is not None:
            json_payload["content"] = f"<@&{self._target_role}>\n" + json_payload["content"]
            json_payload["allowed_mentions"] = {
                "roles": [f"{self._target_role}"]
            }

        post(self._url, json=json_payload)
