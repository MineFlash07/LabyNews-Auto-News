import logging
import os
from html.parser import HTMLParser

from requests import get

from auto_news import UpdateChecker


class VersionChecker(UpdateChecker):
    NEWS: str = "📥UPDATE:\n\nDie LabyMod Version {version} wurde veröffentlicht. Was es alles neues gibt, " \
                "seht ihr hier: "

    def get_interval(self) -> int:
        return 5

    def tick(self) -> None:
        # Check from versions.json to prevent unneeded html parsing
        online_version = get("https://dl.labymod.net/versions.json").json()["1.8.9"]["version"]

        current_version = self.service.get_from_save_data("labymod_version")
        self.service.add_save_data("labymod_version", online_version)
        logging.debug(f"VersionChecker: Got {online_version} and had {current_version}")
        if current_version is None:
            logging.warning("VersionChecker: No current version found in data.")
            return

        # Check news
        if online_version != current_version:
            # Add changelog later
            self.service.create_news(f"New LabyMod version **{online_version}** published. Please check!",
                                     self.NEWS.format(version=online_version))


class StaffChecker(UpdateChecker):
    NEW_STAFF_MEMBER = ("New staff member **{name}** as **{rank}**. Please check! Please adjust message if was"
                        " staff in the past", "👬TEAM-UPDATE:\n\n{name} ist nun {rank}. Herzlichen Glückwunsch und viel"
                                              " Erfolg im Team💪")
    NEW_RANK = ("**{name}** is now **{rank}**. Please check!", "👬TEAM-UPDATE:\n\n{name} ist nun {rank}. Herzlichen "
                                                               "Glückwunsch und weiterhin viel Erfolg im Team💪")
    NEW_RANK_PASSED = ("**{name}** is now **{rank}**. Please check!", "👬TEAM-UPDATE:\n\n{name} hat seine Testphase "
                                                                      "bestanden und ist nun {rank}. Herzlichen "
                                                                      "Glückwunsch und weiterhin viel Erfolg im Team💪")
    STAFF_LEAVE = ("Staff member **{name}** left as **{rank}**. Please check!", "👬TEAM-UPDATE:\n\n{name} ist kein "
                                                                                "{rank} mehr. Wir wünschen viel Glück "
                                                                                "weiterhin.")

    def __init__(self, service):
        super().__init__(service)
        self._parser = self._BadgeMemberParser()
        self._badge_uuid = os.getenv("STAFF_BADGE")
        logging.info(f"StaffChecker: Loaded {self._badge_uuid} as staff badge.")

    def get_interval(self) -> int:
        return 60

    def tick(self) -> None:
        # Feeding parser with badge website
        logging.debug("StaffChecker: Start parsing html.")
        self._parser.feed(get(f"https://laby.net/badge/{self._badge_uuid}").text)

        current_staff = self.service.get_from_save_data("labymod_staff")
        self.service.add_save_data("labymod_staff", self._parser.stored_staff_members)
        if current_staff is None:
            logging.warning("StaffChecker: No current staff data found.")
            return

        # Looping through to validate
        logging.debug("StaffChecker: Started new checking")
        for staff_uuid, staff_data in self._parser.stored_staff_members.items():
            if staff_uuid not in current_staff:
                self.service.create_news(self.NEW_STAFF_MEMBER[0].format(name=staff_data["name"],
                                                                         rank=staff_data["rank"]),
                                         self.NEW_STAFF_MEMBER[1].format(name=staff_data["name"],
                                                                         rank=staff_data["rank"]))
                continue
            old_rank = current_staff[staff_uuid]["rank"]
            if staff_data["rank"] == old_rank:
                logging.debug(f"StaffChecker: No change for {staff_uuid}")
                continue
            # Can only be new rank here - Checking for junior before
            change_message = self.NEW_RANK_PASSED if old_rank.startswith("Jr ") and old_rank[3:] == staff_data["rank"] \
                else self.NEW_RANK
            # Create news
            self.service.create_news(change_message[0].format(name=staff_data["name"], rank=staff_data["rank"]),
                                     change_message[1].format(name=staff_data["name"], rank=staff_data["rank"]))

        # Looping trough old to get leaves
        logging.debug("StaffChecker: Started old checking")
        for staff_uuid, staff_data in current_staff.items():
            if staff_uuid not in self._parser.stored_staff_members:
                self.service.create_news(self.STAFF_LEAVE[0].format(name=staff_data["name"],
                                                                    rank=staff_data["rank"]),
                                         self.STAFF_LEAVE[1].format(name=staff_data["name"],
                                                                    rank=staff_data["rank"]))
                continue
            logging.debug(f"StaffChecker: {staff_uuid} is still in team.")

    class _BadgeMemberParser(HTMLParser):

        def __init__(self):
            super().__init__()
            self._storing_started_prepared = False
            self._storing_started = False
            self._last_uuid = None
            self.stored_staff_members = {}

        def handle_starttag(self, tag, attributes):
            if tag == "div" and len(attributes) >= 1 and attributes[0][0] == "class":
                if attributes[0][1] == "ln-card users-list":
                    self._storing_started_prepared = True
                    logging.debug("StaffChecker: Prepared parsing.")
                    return
                if not self._storing_started_prepared or attributes[0][1] != "ln-card-body":
                    return
                logging.debug("StaffChecker: Started parsing.")
                self._storing_started = True
                self.stored_staff_members.clear()
                return

            if tag != "a" or not self._storing_started or len(attributes) < 3:
                return

            logging.debug(f"StaffChecker: Found a tag with {attributes}")
            rank = None
            for attribute_name, value in attributes:
                if attribute_name == "href":
                    # Removing the /@ from href
                    self._last_uuid = value[2:]
                    continue
                if attribute_name == "title":
                    rank = value

            if rank is None:
                logging.debug("No rank found.")
                return

            logging.debug(f"StaffChecker: Saved {self._last_uuid} with {rank}")
            self.stored_staff_members[self._last_uuid] = {
                "rank": rank
            }

        def handle_data(self, data):
            if self._storing_started and self._last_uuid is not None and data.replace("\n", "").strip() != "":
                logging.debug(f"StaffChecker: Found {data} for {self._last_uuid}")
                self.stored_staff_members[self._last_uuid]["name"] = data

        def handle_endtag(self, tag):
            if tag != "a" and self._storing_started:
                logging.debug("StaffChecker: Ended parsing.")
                self._storing_started = False
                self._storing_started_prepared = False


class ShopChecker(UpdateChecker):

    def __init__(self, service):
        super().__init__(service)
        self._parser = self._ShopItemParser()

    def get_interval(self) -> int:
        return 60

    def _check_banner(self) -> None:
        current_banners: list = self.service.get_from_save_data("top_banner")

        self.service.add_save_data("top_banner", self._parser.banners)
        if current_banners is None:
            logging.warning("ShopChecker (Banner): No current banner data found.")
            return

        new_banners = [banner for banner in self._parser.banners if banner not in current_banners]
        if len(new_banners) >= 1:
            self.service.create_news("**New event banners - Please check!**\n" + "\n".join(new_banners), "")

    def tick(self) -> None:
        # Getting shop and parse it to get items
        logging.debug("ShopChecker: Start parsing html.")
        self._parser.feed(get("https://labymod.net/shop").text)
        # Checking for banner
        logging.info("ShopChecker (Banner): Started grabbing event banners.")
        self._check_banner()
        # Filter shop items for emotes because it's not needed
        online_items = {item_id: item_data["name"] for item_id, item_data in self._parser.stored_items.items()
                        if item_data["category"] != "EMOTE"}

        current_shop = self.service.get_from_save_data("labymod_shop")
        self.service.add_save_data("labymod_shop", {
            "items": [item_id for item_id in online_items],
            "categories": self._parser.shop_categories
        })
        if current_shop is None:
            logging.warning("ShopChecker: No current shop data found.")
            return

        message_content = "Shop-Update - Please check!"
        items_to_announce = [item_name for item_id, item_name in online_items.items()
                             if item_id not in current_shop["items"]]
        if len(items_to_announce) >= 1:
            message_content += "\n**New shop items:** " + ", ".join(items_to_announce)
        categories_to_announce = [category for category in self._parser.shop_categories
                                  if category not in current_shop["categories"]]
        if len(categories_to_announce) >= 1:
            message_content += "\n**New categories/seasons:** " + ", ".join(categories_to_announce)

        if message_content != "Shop-Update - Please check!":
            self.service.create_news(message_content, "")

    class _ShopItemParser(HTMLParser):

        def __init__(self):
            super().__init__()
            self.shop_categories = []
            self.stored_items = {}
            self.banners = []
            self._banner_fetch = True
            self._banner_fetch_currently = False
            self._started_category_fetch = False

        def handle_starttag(self, tag, attributes):
            if tag == "html":
                logging.debug("ShopChecker: Clearing stored data.")
                self.stored_items.clear()
                self._banner_fetch = True
                self.shop_categories.clear()
                self.banners.clear()
                return

            # Check for banner
            if self._banner_fetch and tag == "div" and len(attributes) >= 1 and attributes[0][0] == "class" \
                    and attributes[0][1] == "info-bar":
                self._banner_fetch_currently = True
                # Add new banner element
                logging.debug("ShopChecker (Banner): Found new event bar.")
                self.banners.append("")
                return
            # Check for header to disable banner
            if tag == "header":
                logging.debug("ShopChecker (Banner): Finished banner parsing.")
                self._banner_fetch_currently = False
                self._banner_fetch = False
                return

            if tag == "ul" and len(attributes) == 1 and attributes[0][0] == "class" \
                    and attributes[0][1] == "nav shop-tabs nav-tabs":
                self._started_category_fetch = True
                logging.debug("ShopChecker: Started category parsing.")
                return

            if tag == "li" and self._started_category_fetch:
                logging.debug(f"ShopChecker: Found category with {attributes[0]}")
                self.shop_categories.append(attributes[0][1].replace("active", "").strip())
                return

            if tag != "article" or len(attributes) <= 4:
                return

            logging.debug(f"ShopChecker: Found a tag with {attributes}")
            data: dict = {}
            date_id: int = -1
            for attribute_name, value in attributes:
                if attribute_name == "data-item-category":
                    data["category"] = value
                    continue
                if attribute_name == "data-item-id":
                    try:
                        # Breaking if item already in
                        if int(value) in self.stored_items:
                            return
                        date_id = int(value)
                    except ValueError:
                        logging.error(f"ShopChecker: Found a cosmetic with invalid date-id: {value}")
                    continue
                if attribute_name == "data-item-name":
                    data["name"] = value
            if date_id != -1:
                logging.debug(f"ShopChecker: Found item {date_id} with {data}")
                self.stored_items[date_id] = data

        def handle_endtag(self, tag):
            if tag == "ul" and self._started_category_fetch:
                logging.debug("ShopChecker: Finished category parsing.")
                self._started_category_fetch = False
                return
            if self._banner_fetch and tag == "div" and self._banner_fetch_currently:
                logging.debug("ShopChecker (Banner): Finished an event banner.")
                self._banner_fetch_currently = False

        def handle_data(self, data):
            if self._banner_fetch and self._banner_fetch_currently:
                logging.debug(f"ShopChecker (Banner): Added part of event banner {data}")
                self.banners[-1] += data.replace("\n", "")


class IngameAdvertisementChecker(UpdateChecker):

    def __init__(self, service):
        super().__init__(service)
        self._title_filters = []
        filter_env = os.getenv("ADVERTISEMENT_FILTER")
        if filter_env is not None:
            self._title_filters = filter_env.split(";")
        logging.info(f"IngameAdvertisementChecker: Loaded {len(self._title_filters)} title filter(s).")

    def get_interval(self) -> int:
        return 30

    def tick(self) -> None:
        advertisement_json: dict = get("https://dl.labymod.net/advertisement/entries.json").json()
        online_advertisement = [advertisement["title"] for advertisement in
                                [*advertisement_json["left"], *advertisement_json["right"]]
                                if advertisement["visible"] and advertisement["isNew"] and
                                not any(title_filter in advertisement["title"] for title_filter in self._title_filters)]

        current_advertisement = self.service.get_from_save_data("ingame_advertisement")
        self.service.add_save_data("ingame_advertisement", online_advertisement)
        if current_advertisement is None:
            logging.warning("IngameAdvertisementChecker: No advertisement data found.")
            return

        new_advertisement = [advertisement for advertisement in online_advertisement if advertisement not
                             in current_advertisement]
        if len(new_advertisement) >= 1:
            self.service.create_news("**New ingame advertisement - Please check!**\n" + "\n".join(new_advertisement),
                                     "")
