import re
from .emote import valid_src
regex = re.compile("<:(.*?)>")


def separate(text) -> list: # seperates the text from the <:EMOJI_NAME:EMOJI_ID>
    total = []
    last_span = 0
    for res in regex.finditer(text):
        span = res.span() # find the span of the <:EMOJI_NAME:EMOJI_ID>
        total.extend((text[last_span:span[0]], text[span[0]:span[1]])) # extend the array with the previous text and the supposed emoji
        last_span = span[1]
    total.append(text[last_span:]) # in case there is a missing element
    return [i for i in total if i != ""] # return an array with no empty string


async def parse_custom_emoji(text_list: list, session) -> list:
    result = []
    for text in text_list:
        if text.startswith("https://twemoji.maxcdn.com/v/latest/72x72/") and text.endswith(".png"):
            result.append(text) # definitely a twemoji, skip
            continue
        
        text = text.replace("<a:", "<:")
        _list = separate(text) # seperate the text using regex in case there is a <:EMOJI_NAME:EMOJI_ID>
        for _text in _list:
            try:
                assert _text.startswith("<:") and _text.endswith(">") # not an emoji
                _emoji_id = _text.split(":")[2][:-1]
                assert _emoji_id.isnumeric() # emoji IDs must be a number
                assert await valid_src(f"https://cdn.discordapp.com/emojis/{_emoji_id}.png", session) # must be a valid discord emoji
                result.append(f"https://cdn.discordapp.com/emojis/{_emoji_id}.png") # discord custom emoji case
            except:
                result.append(_text) # basic text case
    
    return result