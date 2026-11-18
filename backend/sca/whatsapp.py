"""WhatsApp messages the teacher sends to the class group.

The app never reads the group: WhatsApp has no supported way to read a personal group, and the unofficial
libraries that do so break WhatsApp's terms and can get the teacher's number banned. Instead the teacher posts
from the app through Android's share sheet, and membership is checked with the group code (see app.py).
"""

from datetime import datetime
from urllib.parse import quote

from sca.studio import IST, pick

TEXT = {
    "class": {
        "en": "🧘 {studio} · {name}\n📅 {day}, {time} IST ({minutes} min)\n🔗 Join: {link}\n\nOpen the app to check in before class.",
        "hi": "🧘 {studio} · {name}\n📅 {day}, {time} IST ({minutes} मिनट)\n🔗 जुड़ें: {link}\n\nकक्षा से पहले ऐप में चेक-इन करें।",
        "mr": "🧘 {studio} · {name}\n📅 {day}, {time} IST ({minutes} मिनिटे)\n🔗 सामील व्हा: {link}\n\nवर्गापूर्वी ॲपमध्ये चेक-इन करा.",
    },
    "invite": {
        "en": "🙏 Join {studio} in the app.\nSign up with your WhatsApp number and this group code: *{code}*",
        "hi": "🙏 ऐप में {studio} से जुड़ें।\nअपने व्हाट्सऐप नंबर और इस ग्रुप कोड से साइन अप करें: *{code}*",
        "mr": "🙏 ॲपमध्ये {studio} मध्ये सामील व्हा.\nतुमचा व्हॉट्सॲप नंबर आणि हा ग्रुप कोड वापरून साइन अप करा: *{code}*",
    },
}
DAY_NAMES = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "hi": ["सोम", "मंगल", "बुध", "गुरु", "शुक्र", "शनि", "रवि"],
    "mr": ["सोम", "मंगळ", "बुध", "गुरु", "शुक्र", "शनि", "रवि"],
}


def class_message(studio: dict, class_name: str, starts_at: datetime, minutes: int, link: str, lang: str) -> str:
    local = starts_at.astimezone(IST)
    day = f"{DAY_NAMES[lang][local.weekday()]} {local.day} {local.strftime('%b')}"
    return pick(TEXT["class"], lang).format(
        studio=pick(studio["name"], lang), name=class_name, day=day, time=local.strftime("%-I:%M %p"), minutes=minutes, link=link
    )


SERVER_LINE = {
    "en": "In the app, under Server address, enter: {url}",
    "hi": "ऐप में सर्वर पता डालें: {url}",
    "mr": "ॲपमध्ये सर्व्हर पत्ता टाका: {url}",
}


def invite_message(studio: dict, code: str, lang: str, server_url: str | None = None) -> str:
    text = pick(TEXT["invite"], lang).format(studio=pick(studio["name"], lang), code=code)
    return text if server_url is None else f"{text}\n{pick(SERVER_LINE, lang).format(url=server_url)}"


def share_url(text: str) -> str:
    """A wa.me link that opens WhatsApp with `text` ready to send; the sender picks the group."""
    return "https://wa.me/?text=" + quote(text)
