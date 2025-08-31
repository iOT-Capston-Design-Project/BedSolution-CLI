from core.config_manager import config_manager
from typing import Tuple, List


class ServerValidator:
    @staticmethod
    def validate_server_config() -> Tuple[bool, List[str]]:
        """
        Validates server configuration settings.
        Returns (is_valid, missing_settings_list)
        """
        missing_settings = []
        
        # Check Supabase URL
        url = config_manager.get_setting("supabase", "url", fallback=None)
        if not url or url.strip() == "":
            missing_settings.append("Supabase URL")
        
        # Check Supabase API Key
        api_key = config_manager.get_setting("supabase", "api_key", fallback=None)
        if not api_key or api_key.strip() == "":
            missing_settings.append("Supabase API Key")
        
        is_valid = len(missing_settings) == 0
        return is_valid, missing_settings

    @staticmethod
    def get_server_config_warning_message(missing_settings: List[str]) -> List[str]:
        """
        Generates warning message lines for missing server configuration.
        """
        if not missing_settings:
            return []
        
        lines = [
            "⚠️  Server configuration required",
            "",
            "Missing settings:",
        ]
        
        for setting in missing_settings:
            lines.append(f"  • {setting}")
        
        lines.extend([
            "",
            "Please configure these settings in:",
            "Settings → Server Connection",
            "",
            "Press 's' to go to Settings, 'q' to go back"
        ])
        
        return lines