import os
import shutil
import sys

from kivy import Config
from kivy.storage.jsonstore import JsonStore

from katrain.core.constants import *
from katrain.core.utils import find_package_resource


class Player:
    def __init__(self, player="B", player_type=PLAYER_HUMAN, player_subtype=PLAYING_NORMAL, periods_used=0):
        self.player = player
        self.update(player_type, player_subtype)
        self.periods_used = periods_used

    def update(self, player_type=PLAYER_HUMAN, player_subtype=PLAYING_NORMAL):
        self.player_type = player_type
        self.player_subtype = player_subtype

    @property
    def ai(self):
        return self.player_type == PLAYER_AI

    @property
    def human(self):
        return self.player_type == PLAYER_HUMAN

    @property
    def being_taught(self):
        return self.player_type == PLAYER_HUMAN and self.player_subtype == PLAYING_TEACHING

    @property
    def strategy(self):
        return self.player_subtype if self.ai else AI_DEFAULT

    def __str__(self):
        return f"{self.player_type} ({self.player_subtype})"


class KaTrainBase:
    USER_CONFIG_FILE = os.path.expanduser("~/.katrain/config.json")
    PACKAGE_CONFIG_FILE = "katrain/config.json"

    """Settings, logging, and players functionality, so other classes like bots who need a katrain instance can be used without a GUI"""

    def __init__(self, **kwargs):
        self.debug_level = 0
        self.game = None

        self.logger = lambda message, level=OUTPUT_INFO: self.log(message, level)
        self.config_file = self._load_config()
        self.debug_level = self.config("general/debug_level", OUTPUT_INFO)

        Config.set("kivy", "log_level", "error")
        if self.debug_level >= OUTPUT_DEBUG:
            Config.set("kivy", "log_enable", 1)
            Config.set("kivy", "log_level", "info")
        if self.debug_level >= OUTPUT_EXTRA_DEBUG:
            Config.set("kivy", "log_level", "trace")
        self.players_info = {"B": Player("B"), "W": Player("W")}
        self.reset_players()

    def log(self, message, level=OUTPUT_INFO):
        if level == OUTPUT_ERROR:
            print(f"ERROR: {message}", file=sys.stderr)
        elif self.debug_level >= level:
            print(message)

    def _load_config(self):
        if len(sys.argv) > 1 and sys.argv[1].endswith(".json"):
            config_file = os.path.abspath(sys.argv[1])
            self.log(f"Using command line config file {config_file}", OUTPUT_INFO)
        else:
            user_config_file = find_package_resource(self.USER_CONFIG_FILE)
            package_config_file = find_package_resource(self.PACKAGE_CONFIG_FILE)
            try:
                if not os.path.exists(user_config_file):
                    os.makedirs(os.path.split(user_config_file)[0], exist_ok=True)
                    shutil.copyfile(package_config_file, user_config_file)
                    config_file = user_config_file
                    self.log(f"Copied package config to local file {config_file}", OUTPUT_INFO)
                else:  # user file exists
                    version = JsonStore(user_config_file, indent=4).get("general")["version"]
                    if version < CONFIG_MIN_VERSION:
                        backup = user_config_file + f".{version}.backup"
                        shutil.copyfile(user_config_file, backup)
                        shutil.copyfile(package_config_file, user_config_file)
                        self.log(
                            f"Copied package config file to {user_config_file} as user file is outdated (<{CONFIG_MIN_VERSION}). Old version stored as {backup}",
                            OUTPUT_INFO,
                        )
                    config_file = user_config_file
                    self.log(f"Using user config file {config_file}", OUTPUT_INFO)
            except Exception as e:
                config_file = package_config_file
                self.log(
                    f"Using package config file {config_file} (exception {e} occurred when finding or creating user config)",
                    OUTPUT_INFO,
                )
        try:
            self._config_store = JsonStore(config_file, indent=4)
        except Exception as e:
            self.log(f"Failed to load config {config_file}: {e}", OUTPUT_ERROR)
            sys.exit(1)
        self._config = dict(self._config_store)
        return config_file

    def save_config(self):
        for k, v in self._config.items():
            self._config_store.put(k, **v)

    def config(self, setting, default=None):
        try:
            if "/" in setting:
                cat, key = setting.split("/")
                return self._config[cat].get(key, default)
            else:
                return self._config[setting]
        except KeyError:
            self.log(f"Missing configuration option {setting}", OUTPUT_ERROR)

    def update_player(self, bw, **kwargs):
        self.players_info[bw].update(**kwargs)

    def reset_players(self):
        self.update_player("B")
        self.update_player("W")
        for v in self.players_info.values():
            v.periods_used = 0

    @property
    def last_player_info(self) -> Player:
        return self.players_info[self.game.current_node.player]

    @property
    def next_player_info(self) -> Player:
        return self.players_info[self.game.current_node.next_player]
