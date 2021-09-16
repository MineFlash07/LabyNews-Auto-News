from requests import get

from auto_news import UpdateChecker


class VersionChecker(UpdateChecker):

    def get_interval(self) -> int:
        return 5

    async def tick(self) -> None:
        # Check from versions.json to prevent unneeded html parsing
        online_version = get("https://dl.labymod.net/versions.json").json()["1.8.9"]["version"]

        current_version = self.service.get_from_save_data("labymod_version")
        if current_version is None:
            await self.service.add_save_data("labymod_version", online_version)
            return

        # Check news
        if online_version != current_version:
            # Add changelog later
            await self.service.create_news(f"New labymod version **{online_version}** published. Please check!", None,
                                           30)
