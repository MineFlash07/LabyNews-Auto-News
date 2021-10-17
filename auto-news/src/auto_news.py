import asyncio
import logging
import os
import sys
from abc import ABC, abstractmethod
from json import load as json_load, dump as json_dump
from time import sleep

from dotenv import load_dotenv

import grabbers
from discord_implementation import Webhook


class AutoNewsService:

    def __init__(self):
        load_dotenv()
        # Setup logging
        logging.basicConfig(filename="auto_news.log", filemode="w", encoding="utf-8",
                            level=logging.DEBUG if os.getenv("DEBUG") == "TRUE" else logging.INFO,
                            format="(%(asctime)s) [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.addFilter(LevelRangeLoggingFilter(logging.DEBUG, logging.INFO))
        formatter = logging.Formatter("(%(asctime)s) [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S", "%")
        stream_handler.setFormatter(formatter)
        logging.root.addHandler(stream_handler)
        error_handler = logging.StreamHandler(sys.stderr)
        error_handler.addFilter(LevelRangeLoggingFilter(logging.WARNING, logging.CRITICAL))
        error_handler.setFormatter(formatter)
        logging.root.addHandler(error_handler)

        webhook_target_role = os.getenv("DISCORD_ROLE")
        logging.info(f"Loaded {webhook_target_role} as target role.")
        self._webhooks = [Webhook(url, webhook_target_role) for url in os.getenv("DISCORD_WEBHOOKS").split(";")]
        logging.info(f"Loaded {len(self._webhooks)} webhook(s).")
        self._grabbers = [grabbers.VersionChecker(self)]
        logging.info(f"Got {len(self._grabbers)} grabber(s).")
        self._max_interval = max(grabber.get_interval() for grabber in self._grabbers)
        logging.debug(f"Max interval of {self._max_interval}")
        self._current_tick = 0

        # Save data
        try:
            with open("./news_data.json", "r", encoding="UTF-8") as file_in:
                self._save_data = json_load(file_in)
            logging.info("Loaded save data from file.")
        except FileNotFoundError:
            self._save_data = {}
            logging.warning("No save date file found.")

        logging.info("Ticket start")
        try:
            self._ticker()
        except KeyboardInterrupt:
            pass

        logging.info("App stopped.")

    async def get_from_save_data(self, config_key: str):
        try:
            return self._save_data[config_key]
        except KeyError:
            return None

    async def add_save_data(self, config_key: str, value):
        self._save_data[config_key] = value
        # Write
        with open("./news_data.json", "w", encoding="UTF-8") as file:
            json_dump(self._save_data, file, indent=4)
        logging.debug(f"Wrote to data:  {config_key} : {value}")

    def _ticker(self):
        while True:
            logging.debug(f"Started tick {self._current_tick}")
            for grabber in self._grabbers:
                if self._current_tick % grabber.get_interval() == 0:
                    logging.info(f"Run grabber: {type(grabber).__name__}")
                    asyncio.run(grabber.tick())

            self._current_tick += 1
            if self._current_tick >= self._max_interval:
                self._current_tick = 0

            sleep(60)

    async def create_news(self, message_content: str, news_content: str):
        # Send webhook
        logging.info(f"News created: {message_content}")
        for webhook in self._webhooks:
            webhook.send(message_content, news_content)


class LevelRangeLoggingFilter(logging.Filter):

    def __init__(self, small_level: int, big_level: int):
        super().__init__()
        self._min = small_level
        self._max = big_level

    def filter(self, record):
        return self._min <= record.levelno <= self._max


class UpdateChecker(ABC):

    def __init__(self, service: AutoNewsService):
        self.service = service

    @abstractmethod
    def get_interval(self) -> int:
        pass

    @abstractmethod
    async def tick(self) -> None:
        pass


def main():
    AutoNewsService()


if __name__ == "__main__":
    main()
