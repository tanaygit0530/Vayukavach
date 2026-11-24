"""Alert texts from templates (no language model): every number with its source, time and
Measured/Estimated label. Hindi and Marathi advice are short renderings of the CPCB health
impacts and NDMA heat advice."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.analysis.time import IST
from app.chat.rules import CATEGORY, CITY, LEVEL, tr
from app.models import District
from app.services.air import air_now
from app.services.reference import CPCB_HEALTH
from app.services.weather import heat_report

AQI_ALARM = ("verypoor", "severe")
AQI_ORDER = ("good", "satisfactory", "moderate", "poor", "verypoor", "severe")
HEAT_ALARM = ("danger", "extreme")
AQI_SOURCE = {
    "official": "CPCB via data.gov.in",
    "measured": "CPCB/SPCB stations via OpenAQ",
    "cams": "CAMS model via Open-Meteo",
}
HEAT_SOURCE = "Open-Meteo"

AIR_ADVICE = {
    "hi": {
        "good": "न्यूनतम असर।",
        "satisfactory": "संवेदनशील लोगों को साँस लेने में हल्की तकलीफ़ हो सकती है।",
        "moderate": "फेफड़े या हृदय रोग वाले लोगों, बच्चों और बुज़ुर्गों को साँस लेने में तकलीफ़ हो सकती है।",
        "poor": "लंबे समय तक बाहर रहने पर साँस लेने में तकलीफ़ हो सकती है।",
        "verypoor": "लंबे समय तक बाहर रहने पर साँस की बीमारी हो सकती है। बाहर की मेहनत कम करें।",
        "severe": "स्वस्थ लोगों पर भी साँस का असर। बाहर कम से कम निकलें।",
    },
    "mr": {
        "good": "किमान परिणाम.",
        "satisfactory": "संवेदनशील लोकांना श्वास घेण्यास थोडा त्रास होऊ शकतो.",
        "moderate": "फुफ्फुस किंवा हृदयविकार असलेले लोक, मुले आणि वृद्धांना श्वास घेण्यास त्रास होऊ शकतो.",
        "poor": "दीर्घकाळ बाहेर राहिल्यास श्वास घेण्यास त्रास होऊ शकतो.",
        "verypoor": "दीर्घकाळ बाहेर राहिल्यास श्वसनाचे आजार होऊ शकतात. बाहेरील श्रम कमी करा.",
        "severe": "निरोगी लोकांवरही श्वसनावर परिणाम. शक्यतो बाहेर जाऊ नका.",
    },
}
HEAT_ADVICE = {
    "en": {
        "caution": "Drink water often and avoid the sun from 12 to 3 pm.",
        "danger": "Avoid outdoor work in the afternoon; rest in shade, drink water or ORS.",
        "extreme": "Stay indoors. For confusion, hot dry skin or fainting, call 108.",
    },
    "hi": {
        "caution": "बार-बार पानी पिएँ और दोपहर 12 से 3 बजे तक धूप से बचें।",
        "danger": "दोपहर में बाहर काम न करें; छाया में आराम करें, पानी या ORS लें।",
        "extreme": "घर के अंदर रहें। भ्रम, गर्म सूखी त्वचा या बेहोशी हो तो 108 पर कॉल करें।",
    },
    "mr": {
        "caution": "वारंवार पाणी प्या आणि दुपारी 12 ते 3 उन्हात जाणे टाळा.",
        "danger": "दुपारी बाहेर काम करू नका; सावलीत विश्रांती घ्या, पाणी किंवा ORS घ्या.",
        "extreme": "घरातच रहा. गोंधळ, गरम कोरडी त्वचा किंवा बेशुद्धी असल्यास 108 वर कॉल करा.",
    },
}

L = {
    "measured": {"en": "Measured", "hi": "मापा गया", "mr": "मोजलेले"},
    "estimated": {"en": "Estimated", "hi": "अनुमानित", "mr": "अंदाजित"},
    "air": {
        "en": "Air: AQI {aqi} ({cat}){main}. {src}, {time}, {label}.",
        "hi": "हवा: AQI {aqi} ({cat}){main}। {src}, {time}, {label}।",
        "mr": "हवा: AQI {aqi} ({cat}){main}. {src}, {time}, {label}.",
    },
    "main": {"en": ", mainly {p}", "hi": ", मुख्य प्रदूषक {p}", "mr": ", मुख्य प्रदूषक {p}"},
    "air_na": {
        "en": "Air: no AQI reading in the last 6 hours.",
        "hi": "हवा: पिछले 6 घंटों में AQI उपलब्ध नहीं।",
        "mr": "हवा: मागील 6 तासांत AQI उपलब्ध नाही.",
    },
    "heat": {
        "en": "Heat: {level}, feels like {feels}°C. {src}, {time}, {label}.",
        "hi": "गर्मी: {level}, महसूस {feels}°C। {src}, {time}, {label}।",
        "mr": "उष्णता: {level}, जाणवणारे {feels}°C. {src}, {time}, {label}.",
    },
    "heat_na": {
        "en": "Heat: no weather data for this hour.",
        "hi": "गर्मी: इस घंटे का मौसम डेटा उपलब्ध नहीं।",
        "mr": "उष्णता: या तासाचा हवामान डेटा उपलब्ध नाही.",
    },
    "work": {
        "en": "Safer hours for outdoor work: {w}.",
        "hi": "बाहर काम के लिए सुरक्षित समय: {w}।",
        "mr": "बाहेरील कामासाठी सुरक्षित वेळ: {w}.",
    },
    "daily_head": {
        "en": "VayuKavach · {city} · {date}",
        "hi": "वायुकवच · {city} · {date}",
        "mr": "वायुकवच · {city} · {date}",
    },
    "aqi_alert": {
        "en": "VayuKavach alert · {city}: air is now {cat} (AQI {aqi}). {src}, {time}, {label}.",
        "hi": "वायुकवच चेतावनी · {city}: हवा अब {cat} है (AQI {aqi})। {src}, {time}, {label}।",
        "mr": "वायुकवच इशारा · {city}: हवा आता {cat} आहे (AQI {aqi}). {src}, {time}, {label}.",
    },
    "heat_alert": {
        "en": "VayuKavach alert · {city}: heat level is now {level} (feels like {feels}°C). "
        "{src}, {time}, {label}.",
        "hi": "वायुकवच चेतावनी · {city}: गर्मी का स्तर अब {level} है (महसूस {feels}°C)। "
        "{src}, {time}, {label}।",
        "mr": "वायुकवच इशारा · {city}: उष्णतेची पातळी आता {level} आहे (जाणवणारे {feels}°C). "
        "{src}, {time}, {label}.",
    },
    "stop": {"en": "Stop alerts: {url}", "hi": "अलर्ट बंद करें: {url}", "mr": "इशारे बंद करा: {url}"},
    "code": {
        "en": "Your VayuKavach code is {code}. It expires in 15 minutes. If you did not ask for "
        "alerts, ignore this message.",
        "hi": "आपका वायुकवच कोड {code} है। यह 15 मिनट में समाप्त होगा। अगर आपने अलर्ट नहीं माँगे, "
        "तो इसे अनदेखा करें।",
        "mr": "तुमचा वायुकवच कोड {code} आहे. तो 15 मिनिटांत संपेल. तुम्ही इशारे मागितले नसल्यास "
        "हा संदेश दुर्लक्षित करा.",
    },
    "subject_daily": {
        "en": "Today's air and heat",
        "hi": "आज की हवा और गर्मी",
        "mr": "आजची हवा आणि उष्णता",
    },
    "subject_alert": {"en": "Alert", "hi": "चेतावनी", "mr": "इशारा"},
    "subject_code": {"en": "Your code", "hi": "आपका कोड", "mr": "तुमचा कोड"},
}


def _t(key: str, lang: str, **kw) -> str:
    table = L[key]
    return table.get(lang, table["en"]).format(**kw)


def fmt_time(ts: datetime | None) -> str:
    return ts.astimezone(IST).strftime("%d %b, %H:%M IST") if ts else "time unknown"


def air_facts(session: Session, d: District, now: datetime) -> dict | None:
    a = air_now(session, d, now)
    if a["aqi"] is None:
        return None
    kind = a["aqi_kind"]
    return {
        "aqi": a["aqi"],
        "key": a["category_key"],
        "category": a["category"],
        "main": a["main_pollutant"],
        "source": AQI_SOURCE[kind],
        "time": a["hour"] + timedelta(hours=1) if a["hour"] else None,  # end of the hour
        "label": "estimated" if kind == "cams" else "measured",
    }


def heat_facts(session: Session, d: District, now: datetime) -> dict | None:
    h = heat_report(session, d, now)
    if h["level"] is None:
        return None
    return {
        "level": h["level"],
        "name": h["level_name"],
        "feels": round(h["feels_like"]) if h["feels_like"] is not None else None,
        "windows": [
            f"{w['from_hour']:02d}:00–{w['to_hour']:02d}:00" for w in h["safe_work_windows"]
        ],
        "source": HEAT_SOURCE,
        "time": h["hour"],
        "label": "estimated",
    }


def _air_line(a: dict, lang: str) -> str:
    main = _t("main", lang, p=a["main"].upper().replace("PM25", "PM2.5")) if a["main"] else ""
    return _t(
        "air", lang, aqi=a["aqi"], cat=tr(CATEGORY, lang, a["category"]), main=main,
        src=a["source"], time=fmt_time(a["time"]), label=L[a["label"]][lang],
    )  # fmt: skip


def _air_advice(key: str, lang: str) -> str:
    return CPCB_HEALTH[key] + " (CPCB)" if lang == "en" else AIR_ADVICE[lang][key] + " (CPCB)"


def _heat_line(h: dict, lang: str) -> str:
    return _t(
        "heat", lang, level=tr(LEVEL, lang, h["name"]), feels=h["feels"], src=h["source"],
        time=fmt_time(h["time"]), label=L[h["label"]][lang],
    )  # fmt: skip


def _heat_advice(level: str, lang: str) -> str | None:
    text = HEAT_ADVICE[lang].get(level)
    return f"{text} (NDMA)" if text else None


def daily(session: Session, d: District, lang: str, now: datetime, stop_url: str) -> str:
    city = tr(CITY, lang, d.name)
    lines = [_t("daily_head", lang, city=city, date=now.astimezone(IST).strftime("%d %b %Y"))]
    a = air_facts(session, d, now)
    if a:
        lines += [_air_line(a, lang), _air_advice(a["key"], lang)]
    else:
        lines.append(_t("air_na", lang))
    h = heat_facts(session, d, now)
    if h:
        lines.append(_heat_line(h, lang))
        if advice := _heat_advice(h["level"], lang):
            lines.append(advice)
        if h["windows"] and h["level"] != "normal":
            lines.append(_t("work", lang, w=", ".join(h["windows"])))
    else:
        lines.append(_t("heat_na", lang))
    lines.append(_t("stop", lang, url=stop_url))
    return "\n".join(lines)


def aqi_alert(d: District, a: dict, lang: str, stop_url: str) -> str:
    head = _t(
        "aqi_alert", lang, city=tr(CITY, lang, d.name), cat=tr(CATEGORY, lang, a["category"]),
        aqi=a["aqi"], src=a["source"], time=fmt_time(a["time"]), label=L[a["label"]][lang],
    )  # fmt: skip
    return "\n".join([head, _air_advice(a["key"], lang), _t("stop", lang, url=stop_url)])


def heat_alert(d: District, h: dict, lang: str, stop_url: str) -> str:
    head = _t(
        "heat_alert", lang, city=tr(CITY, lang, d.name), level=tr(LEVEL, lang, h["name"]),
        feels=h["feels"], src=h["source"], time=fmt_time(h["time"]), label=L[h["label"]][lang],
    )  # fmt: skip
    parts = [head, _heat_advice(h["level"], lang)]
    if h["windows"]:
        parts.append(_t("work", lang, w=", ".join(h["windows"])))
    parts.append(_t("stop", lang, url=stop_url))
    return "\n".join(p for p in parts if p)


def code_text(code: str, lang: str) -> str:
    return _t("code", lang, code=code)


def subject(kind: str, lang: str, city: str) -> str:
    return f"VayuKavach · {tr(CITY, lang, city)} · {_t('subject_' + kind, lang)}"
