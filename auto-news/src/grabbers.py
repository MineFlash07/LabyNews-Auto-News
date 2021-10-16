import logging

from requests import get

from auto_news import UpdateChecker


class VersionChecker(UpdateChecker):

    NEWS: str = "📥UPDATE:\n\nDie LabyMod Version {version} wurde veröffentlicht. Was es alles neues gibt, " \
                "seht ihr hier: "

    def get_interval(self) -> int:
        return 5

    async def tick(self) -> None:
        # Check from versions.json to prevent unneeded html parsing
        online_version = get("https://dl.labymod.net/versions.json").json()["1.8.9"]["version"]

        current_version = await self.service.get_from_save_data("labymod_version")
        await self.service.add_save_data("labymod_version", online_version)
        logging.debug(f"VersionChecker: Got {online_version} and had {current_version}")
        if current_version is None:
            return

        # Check news
        if online_version != current_version:
            # Add changelog later
            await self.service.create_news(f"New LabyMod version **{online_version}** published. Please check!",
                                           self.NEWS.format(version=online_version))
