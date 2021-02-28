"""
A python module made on top of PIL that draws emoji from text to image.
Feel free to make a pull request for a bug fix/new feature.

"""

from .emote import emoji_to_url
from .image import TwemojiParser

__version__ = "0.5.1"
__all__ = ["emoji_to_url", "TwemojiParser"]