import os
from config import Config
from inky.auto import auto
from utils.image_utils import resize_image, change_orientation
from plugins.plugin_registry import get_plugin_instance


class DisplayManager:
    def __init__(self, device_config : Config):
        """Manages the display and rendering of images."""
        self.device_config = device_config
        self.devmode = device_config.load_env_key("PLUGIN_DEV_MODE")
        if self.devmode:
            from inky.mock import InkyMockImpression
            (width, height) = device_config.get_resolution()
            self.inky_display = InkyMockImpression((width, height))
            #self.inky_display = auto(ask_user=True, verbose=True)
        else:
            self.inky_display = auto()
        
        self.inky_display.set_border(self.inky_display.BLACK)

        # store display resolution in device config
        if not device_config.get_config("resolution"):
            device_config.update_value("resolution",[int(self.inky_display.width), int(self.inky_display.height)], write=True)

    def display_image(self, image, image_settings=[]):
        """Displays the image provided, applying the image_settings."""
        if not image:
            raise ValueError(f"No image provided.")

        # Save the image
        image.save(self.device_config.current_image_file)

        # Resize and adjust orientation
        image = change_orientation(image, self.device_config.get_config("orientation"))
        image = resize_image(image, self.device_config.get_resolution(), image_settings)

        # Display the image on the Inky display
        self.inky_display.set_image(image)
        self.inky_display.show()
