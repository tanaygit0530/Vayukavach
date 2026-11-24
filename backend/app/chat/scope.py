"""Before any model call: is the question in scope, and which language is it in?

In scope: air quality, heat, weather, VayuKavach's data and the app. Everything else gets the
fixed refusal. A city name alone is not enough ("write a poem about Delhi" is out of scope)."""

from __future__ import annotations

import re
import unicodedata

IN_SCOPE = (
    # English
    "aqi",
    "air",
    "pollution",
    "polluted",
    "smog",
    "haze",
    "pm2.5",
    "pm 2.5",
    "pm25",
    "pm10",
    "no2",
    "so2",
    "ozone",
    "o3",
    "carbon monoxide",
    "dust",
    "mask",
    "breath",
    "asthma",
    "heat",
    "hot",
    "humid",
    "temperature",
    "weather",
    "rain",
    "uv",
    "sun",
    "wet-bulb",
    "wet bulb",
    "heatstroke",
    "heat stroke",
    "feels like",
    "forecast",
    "tomorrow",
    "station",
    "data",
    "complete",
    "missing",
    "gap",
    "silent",
    "shadow",
    "estimate",
    "reliab",
    "trust",
    "vayukavach",
    "app",
    "cleaner",
    "cooler",
    "clean place",
    "cool place",
    "trip",
    "vacation",
    "safe",
    "run",
    "jog",
    "walk",
    "exercise",
    "outdoor",
    "work outside",
    "precaution",
    "health",
    "measured",
    "category",
    "cpcb",
    "openaq",
    "cams",
    # Hindi
    "हवा",
    "वायु",
    "प्रदूषण",
    "धुआं",
    "धूल",
    "स्मॉग",
    "मास्क",
    "सांस",
    "दमा",
    "गर्मी",
    "गरमी",
    "लू",
    "तापमान",
    "मौसम",
    "बारिश",
    "धूप",
    "पूर्वानुमान",
    "डेटा",
    "स्टेशन",
    "सुरक्षित",
    "दौड़",
    "व्यायाम",
    "बाहर काम",
    "साफ",
    "ठंडी जगह",
    # Marathi
    "हवेची",
    "हवेचा",
    "प्रदूषणाची",
    "उष्णता",
    "ऊन",
    "उकाडा",
    "हवामान",
    "पाऊस",
    "तापमानाचा",
    "श्वास",
    "सुरक्षित आहे",
    "धावणे",
    "स्वच्छ हवा",
    "थंड ठिकाण",
)

# Clearly unrelated requests win even if a scope word appears ("tell me a joke about smog").
OUT_OF_SCOPE = (
    "joke",
    "poem",
    "song",
    "story",
    "cricket",
    "ipl",
    "match",
    "football",
    "movie",
    "film",
    "recipe",
    "stock",
    "share price",
    "bitcoin",
    "crypto",
    "python code",
    "write code",
    "program",
    "homework",
    "capital of",
    "president",
    "prime minister",
    "election",
    "vote",
    "hack",
    "system prompt",
    "your instructions",
    "your prompt",
    "pirate",
    "चुटकुला",
    "कविता",
    "क्रिकेट",
    "फिल्म",
    "चुनाव",
    "विनोद",
    "कविता लिहा",
    "सामना",
)

REFUSAL = {
    "en": "I can only answer questions about air quality, heat and VayuKavach's data.",
    "hi": "मैं केवल वायु गुणवत्ता, गर्मी और VayuKavach के डेटा से जुड़े सवालों के जवाब दे सकता हूँ।",
    "mr": "मी फक्त हवेची गुणवत्ता, उष्णता आणि VayuKavach च्या डेटाबद्दलच्या प्रश्नांची उत्तरे देऊ शकतो.",
}

MARATHI = (
    "आहे",
    "कशी",
    "काय",
    "आणि",
    "नाही",
    "मध्ये",
    "उद्या",
    "आज",
    "कुठे",
    "का?",
    "हवेची",
    "करू",
    "शकतो",
    "होईल",
    "होती",
)
HINDI = ("है", "कैसी", "क्या", "और", "नहीं", "में", "कल", "कहाँ", "होगा", "थी", "करना", "चाहिए")


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower()


def detect_language(text: str, requested: str | None = None) -> str:
    if requested in REFUSAL:
        return requested
    if not re.search(r"[ऀ-ॿ]", text):
        return "en"
    t = _norm(text)
    mr = sum(w in t for w in MARATHI)
    hi = sum(w in t for w in HINDI)
    return "mr" if mr > hi else "hi"


def _pattern(words: tuple[str, ...]) -> re.Pattern:
    """English words match on word boundaries ("air" not in "chair"; `*` = prefix stem);
    Devanagari words match as substrings (word boundaries are unreliable for Indic scripts)."""
    parts = []
    for w in words:
        if re.search(r"[\u0900-\u097F]", w):
            parts.append(re.escape(w))
        elif w.endswith("*"):
            parts.append(r"\b" + re.escape(w[:-1]) + r"\w*")
        else:
            parts.append(r"\b" + re.escape(w) + r"\b")
    return re.compile("|".join(parts))


_IN = _pattern(IN_SCOPE)
_OUT = _pattern(OUT_OF_SCOPE)


def in_scope(text: str) -> bool:
    t = _norm(text)
    if _OUT.search(t):
        return False
    return bool(_IN.search(t))
