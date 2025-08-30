import configparser
from pathlib import Path

class ConfigManager:
    """
    Handles reading and writing configuration settings to a file (config.ini).
    """
    def __init__(self, config_file="config.ini"):
        self.config_path = Path(config_file)
        self.config = configparser.ConfigParser()
        self._load()

    def _load(self):
        """Loads the configuration from the file."""
        if self.config_path.exists():
            self.config.read(self.config_path)

    def _save(self):
        """Saves the current configuration to the file."""
        with self.config_path.open("w") as f:
            self.config.write(f)

    def get_setting(self, section: str, key: str, fallback: str | None = None) -> str | None:
        """Gets a specific setting value."""
        return self.config.get(section, key, fallback=fallback)

    def update_setting(self, section: str, key: str, value: str):
        """Updates or adds a specific setting."""
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))
        self._save()

    def delete_all_settings(self):
        """Deletes the entire configuration file."""
        if self.config_path.exists():
            self.config_path.unlink()
        # Reset the in-memory config object
        self.config = configparser.ConfigParser()

# Create a single instance to be used throughout the application
config_manager = ConfigManager()
