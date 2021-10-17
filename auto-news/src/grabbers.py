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
                self._storing_started = 1
                self.stored_staff_members.clear()
                return

            if tag != "a" or not self._storing_started or len(attributes) < 3:
                return

            logging.debug(f"StaffChecker: Found a tag with {attributes}")
            rank = None
            for attribute in attributes:
                if attribute[0] == "href":
                    # Removing the /@ from href
                    self._last_uuid = attribute[1][2:]
                    continue
                if attribute[0] == "title":
                    rank = attribute[1]

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
