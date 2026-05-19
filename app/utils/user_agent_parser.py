from __future__ import annotations

from typing import NamedTuple

from user_agents import parse as ua_parse


class ParsedUA(NamedTuple):
    browser: str
    os: str
    device: str


def parse_user_agent(ua_string: str | None) -> ParsedUA:
    if not ua_string:
        return ParsedUA(browser="Unknown", os="Unknown", device="Other")

    ua = ua_parse(ua_string)

    browser = ua.browser.family or "Unknown"
    os = ua.os.family or "Unknown"

    if ua.is_mobile:
        device = "Mobile"
    elif ua.is_tablet:
        device = "Tablet"
    elif ua.is_bot:
        device = "Bot"
    else:
        device = "Desktop"

    return ParsedUA(browser=browser, os=os, device=device)
