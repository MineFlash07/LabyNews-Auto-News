import asyncio
import os
from abc import ABC, abstractmethod
from json import load as json_load, dump as json_dump

from dotenv import load_dotenv

import grabbers
from discord_implementation import Webhook


class AutoNewsService:

    def __init__(self):
        load_dotenv()
        webhook_target_role = os.getenv("DISCORD_ROLE")
        self._webhooks = [Webhook(url, webhook_target_role) for url in os.getenv("DISCORD_WEBHOOKS").split(";")]
        self._grabbers = [grabber_class(self) for grabber_class in grabbers.__dict__.values()
                          if isinstance(grabber_class, type)]
        self._max_interval = max(grabber.get_interval() for grabber in self._grabbers)
        self._current_tick = 0
        self.news_queue = []

        # Save data
        with open("./news_data.json", "r", encoding="UTF-8") as file_in:
            self._save_data = json_load(file_in)

        asyncio.run(self._ticker())

    def get_from_save_data(self, config_key: str):
        try:
            return self._save_data[config_key]
        except KeyError:
            return None

    async def add_save_data(self, config_key: str, value):
        self._save_data[config_key] = value
        # Write
        with open("./news_data.json", "w", encoding="UTF-8") as file:
            json_dump(self._save_data, file)

    async def _ticker(self):
        while True:
            for grabber in self._grabbers:
                if self._current_tick % grabber.get_interval() == 0:
                    await grabber.tick()

            for news in self.news_queue.copy():
                await news.tick()

            self._current_tick += 1
            if self._current_tick > self._max_interval:
                self._current_tick = 0


            await asyncio.sleep(60)

    async def send_tweet(self, tweet):
        pass

    async def create_news(self, message_content: str, tweet, waiting_time: int):
        # Queue news
        self.news_queue.append(News(self, tweet, waiting_time))
        # Send webhook
        for webhook in self._webhooks:
            webhook.send(message_content)


class News:

    def __init__(self, service: AutoNewsService, tweet, waiting_time: int):
        self._waiting_time = waiting_time
        self._tweet = tweet
        self._service = service

    async def tick(self):
        if self._waiting_time > 0:
            self._waiting_time -= 1
            return

        await self._service.send_tweet(self._tweet)


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
