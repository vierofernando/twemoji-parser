from os.path import isfile
from emoji import UNICODE_EMOJI
from PIL import Image, ImageDraw, ImageFont
from aiohttp import ClientSession
from io import BytesIO
from .emote import emoji_to_url
from .discord_emoji import parse_custom_emoji
import gc

class TwemojiParser:
    UNICODES = UNICODE_EMOJI.get('en', UNICODE_EMOJI).keys()


    @staticmethod
    def is_twemoji_url(text: str) -> bool:
        """ A static method that says if a url is a twemoji url """

        return text.startswith("https://twemoji.maxcdn.com/v/latest/72x72/") and text.endswith(".png") and text.count(" ") == 0


    @staticmethod
    def has_emoji(text: str) -> bool:
        """ A static method that checks if a text has an emoji. """
        
        for char in text:
            if char in TwemojiParser.UNICODES:
                return True
        return False
        

    @staticmethod
    def count_emojis(text: str) -> int:
        """ A static method that counts the emojis from a string. """
        
        return len(TwemojiParser.get_emojis_from(text))

    
    @staticmethod
    def get_emojis_from(text: str) -> list:
        """ A static method that gets the list of emojis from a string. """
        
        return list(filter(lambda x: (x in TwemojiParser.UNICODES), list(text)))


    def __is_emoji_url(self, text: str) -> bool:
        if not self.parse_discord_emoji:
            return text.startswith("https://twemoji.maxcdn.com/v/latest/72x72/") and text.endswith(".png") and (" " not in text)
        
        return (text.startswith("https://twemoji.maxcdn.com/v/latest/72x72/") or text.startswith("https://cdn.discordapp.com/emojis/")) and text.endswith(".png") and text.count(" ")


    def __init__(self, image, parse_discord_emoji: bool = False, session: ClientSession = None, *args, **kwargs) -> None:
        """ Creates a parser from PIL.Image.Image object. """
        
        if isinstance(image, bytes):
            self.image = Image.open(BytesIO(image))
        elif isinstance(image, BytesIO):
            self.image = Image.open(image)
        elif isinstance(image, str) and isfile(image):
            self.image = Image.open(image)
        else:
            self.image = image
        
        self.draw = ImageDraw.Draw(image)
        self._emoji_cache = {}
        self._image_cache = {}
        self.__session = session if session else ClientSession()
        self.parse_discord_emoji = parse_discord_emoji

    
    async def getsize(self, text: str, font, check_for_url: bool = True, spacing: int = 4, *args, **kwargs) -> tuple:
        """ Gets the size of a text. """
        
        _parsed = await self.__parse_text(text, check_for_url)
        
        if self.parse_discord_emoji:
            _parsed = await parse_custom_emoji(text, self.__session)
        
        _width, _height = 0, font.getsize(text)[1]
        _, _font_descent = font.getmetrics()
        for word in _parsed:
            _width += (_height + _font_descent + spacing if self.is_twemoji_url(word) else font.getsize(word)[0] + spacing)
        return (_width - spacing, _height)

    
    async def __parse_text(self, text: str, check: bool) -> list:
        result = []
        temp_word = ""
        for letter in range(len(text)):
            if text[letter] not in TwemojiParser.UNICODES:
                # basic text case
                if (letter == (len(text) - 1)) and temp_word:
                    result.append(temp_word + text[letter]) ; break
                temp_word += text[letter] ; continue
            
            # check if there is an empty string in the array
            if temp_word: result.append(temp_word)
            temp_word = ""
            
            if text[letter] in self._emoji_cache:
                # store in cache so it uses less HTTP requests
                result.append(self._emoji_cache[text[letter]])
                continue

            # include_check will check the URL if it's valid. Disabling it will make the process faster, but more error-prone
            res = await emoji_to_url(text[letter], check, self.__session)
            if res != text[letter]:
                result.append(res)
                self._emoji_cache[text[letter]] = res
            else:
                result.append(text[letter])
        
        return (result or [text])


    async def __image_from_url(self, url: str) -> Image.Image:
        """ Gets an image from URL. """
        async with self.__session.get(url) as resp:
            _byte = await resp.read()
        return Image.open(BytesIO(_byte))


    async def draw_text(
        self,
        # Same PIL options
        xy: tuple,
        text: str,
        font=None,
        spacing: int = 4,
        
        # Parser options
        with_url_check: bool = True,
        clear_cache_after_usage: bool = False,
        
        *args, **kwargs
    ) -> None:
        """
        Draws a text with the emoji.
        clear_cache_after_usage will clear the cache after this method is finished. (defaults to False)
        """

        _parsed_text = await self.__parse_text(text, with_url_check)
        _font = font or ImageFont.load_default()
        _font_size = getattr(_font, "size", 11)
        _, _font_descent = font.getmetrics()
        _current_x, _current_y = xy[0], xy[1]
        _origin_x = xy[0]
        if self.parse_discord_emoji:
            _parsed_text = await parse_custom_emoji(_parsed_text, self.__session)

        if not [i for i in _parsed_text if self.__is_emoji_url(i)]:
            self.draw.text(xy, text, font=font, spacing=spacing, *args, **kwargs)
        else:
            for word in _parsed_text:
                if self.__is_emoji_url(word):
                    # check if image is in cache
                    if word in self._image_cache:
                        _emoji_im = self._image_cache[word].copy()
                    else:
                        _emoji_im = await self.__image_from_url(word)
                        _emoji_im = _emoji_im.resize((_font_size+_font_descent, _font_size+_font_descent)).convert("RGBA")
                        self._image_cache[word] = _emoji_im.copy()

                    self.image.paste(_emoji_im, (_current_x, _current_y), _emoji_im)                    
                    _current_x += _font_size + _font_descent + spacing
                    continue

                _size = _font.getsize(word.replace("\n", ""))
                if word.count("\n") > 0:
                    _current_x = _origin_x - spacing
                    _current_y += (_font_size * word.count("\n"))
                self.draw.text((_current_x, _current_y), word, font=font, *args, **kwargs)
                _current_x += _size[0] + spacing
        
        if clear_cache_after_usage:
            self._emoji_cache = {}
            self._image_cache = {}
            gc.collect()
            
    async def close(self, delete_all_attributes: bool = True, close_session: bool = True):
        """ Closes the aiohttp ClientSession and clears all the cache. """
        
        if close_session:
            await self.__session.close()

        if delete_all_attributes:
            del self._emoji_cache
            del self._image_cache
            del self.draw
            del self.image
            del self.parse_discord_emoji

            gc.collect() # if the cache is large it is better to explicitly call this
