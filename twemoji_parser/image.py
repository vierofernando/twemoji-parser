from emoji import UNICODE_EMOJI
from PIL import Image, ImageDraw, ImageFont
from aiohttp import ClientSession
from io import BytesIO
from .emote import emoji_to_url

class TwemojiParser:
    UNICODES = UNICODE_EMOJI.keys()
    NON_EMOJIS = list("abcdefghijklmnopqrstuvwxyz0123456789`~!@#$%^&*()_+-=[]\;',./{}|: <>?")

    @staticmethod
    def has_emoji(text: str, *args, **kwargs) -> bool:
        """ A static method that checks if a text has an emoji. """
        
        return TwemojiParser.count_emojis(text) > 0

    @staticmethod
    def count_emojis(text: str, *args, **kwargs) -> int:
        """ A static method that counts the emojis from a string. """
        
        _filter = list(filter(lambda x: (x not in TwemojiParser.NON_EMOJIS) and (x in TwemojiParser.UNICODES), list(text)))
        size = len(_filter)
        del _filter
        return size
    
    @staticmethod
    def get_emojis_from(text: str, *args, **kwargs) -> list:
        """ A static method that gets the list of emojis from a string. """
        
        return list(filter(lambda x: (x not in TwemojiParser.NON_EMOJIS) and (x in TwemojiParser.UNICODES), list(text)))

    def __init__(self, image: Image.Image, session: ClientSession = None, *args, **kwargs) -> None:
        """ Creates a parser from PIL.Image.Image object. """
        self.image = image
        self.draw = ImageDraw.Draw(image)
        self._emoji_cache = {}
        self._image_cache = {}
        self.__session = ClientSession() if (not session) else session
    
    async def getsize(self, text: str, font, check_for_url: bool = True, spacing: int = 4, *args, **kwargs) -> tuple:
        """ (BETA) Gets the size of a text. """
        
        _parsed = await self.__parse_text(text, check_for_url)
        if len(_parsed) == 1 and (not _parsed[0].startswith("https://")):
            return font.getsize(text)
        _width, _height = 0, font.getsize(text)[1]
        for i in _parsed:
            if not i.startswith("https://"):
                _width += font.getsize(i)[0] + spacing
            _width += _height + spacing
        return (_width - spacing, _height)
    
    async def __parse_text(self, text: str, check: bool) -> list:
        result = []
        temp_word = ""
        for letter in range(len(text)):
            if text[letter].isalpha() or text[letter].isnumeric() or (text[letter] in TwemojiParser.NON_EMOJIS):
                # basic text case
                if (letter == (len(text) - 1)) and temp_word != "":
                    result.append(temp_word + text[letter]) ; break
                temp_word += text[letter] ; continue
            
            # check if there is an empty string in the array
            if temp_word != "": result.append(temp_word)
            temp_word = ""
            
            if text[letter] in self._emoji_cache.keys():
                # store in cache so it uses less HTTP requests
                result.append(self._emoji_cache[text[letter]])
                continue

            # include_check will check the URL if it's valid. Disabling it will make the process faster, but more error-prone
            res = await emoji_to_url(text[letter], include_check=check, use_session=self.__session)
            if res != text[letter]:
                result.append(res)
                self._emoji_cache[text[letter]] = res
            else:
                result.append(text[letter])
        
        if result == []: return [text]
        return result

    async def __image_from_url(self, url: str) -> Image.Image:
        """ Gets an image from URL. """
        resp = await self.__session.get(url)
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
        convert_to_rgba: bool = True,
        
        *args, **kwargs
    ) -> None:
        """
        Draws a text with the emoji.
        clear_cache_after_usage will clear the cache after this method is finished. (defaults to False)
        """

        _parsed_text = await self.__parse_text(text, with_url_check)
        _font = font if font is not None else ImageFont.load_default()
        _font_size = 11 if not hasattr(_font, "size") else _font.size
        _current_x, _current_y = xy[0], xy[1]
        _origin_x = xy[0]

        if len([i for i in _parsed_text if i.startswith("https://twemoji.maxcdn.com/v/latest/72x72/")]) == 0:
            self.draw.text(xy, text, font=font, spacing=spacing, *args, **kwargs)
        else:
            for i in range(len(_parsed_text)):
                print(_parsed_text[i])
                if (_parsed_text[i].startswith("https://twemoji.maxcdn.com/v/latest/72x72")):
                    # check if image is in cache
                    if _parsed_text[i] in self._image_cache.keys():
                        _emoji_im = self._image_cache[_parsed_text[i]].copy()
                    else:
                        _emoji_im = await self.__image_from_url(_parsed_text[i])
                        _emoji_im = _emoji_im.resize((_font_size, _font_size)).convert("RGBA") if convert_to_rgba else _emoji_im.resize((_font_size, _font_size))
                        self._image_cache[_parsed_text[i]] = _emoji_im.copy()
                    
                    if _emoji_im.mode == "RGBA":
                        self.image.paste(_emoji_im, (_current_x, _current_y), _emoji_im)
                    else:
                        self.image.paste(_emoji_im, (_current_x, _current_y))
                    
                    _current_x += _font_size + spacing
                    continue
                _size = _font.getsize(_parsed_text[i].replace("\n", ""))
                if _parsed_text[i].count("\n") > 0:
                    _current_x = _origin_x - spacing
                    _current_y += (_font_size * _parsed_text[i].count("\n"))
                self.draw.text((_current_x, _current_y), _parsed_text[i], font=font, *args, **kwargs)
                _current_x += _size[0] + spacing
        
        if clear_cache_after_usage:
            await self.close(delete_all_attributes=bool(kwargs.get("delete_all_attributes")))
    
    async def close(self, delete_all_attributes: bool = False, *args, **kwargs):
        """ Closes the aiohttp ClientSession and clears all the cache. """
        
        await self.__session.close()
        
        if delete_all_attributes:
            del self._emoji_cache
            del self._image_cache
            del self.draw
            del self.image