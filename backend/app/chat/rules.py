"""Rule-based engine: no language model. Picks the data function(s) by keyword, then fills a
template in English, Hindi or Marathi with the returned numbers only. Used when no LLM is
configured, and by the evaluation in CI (deterministic)."""

from __future__ import annotations

import re

from sqlalchemy import select

from app.chat.tools import NAMES, SRC_METHODS, ToolContext, call
from app.models import District

# Well-known cities VayuKavach does not cover yet: mentioning one must not fall back to the
# selected city's data.
UNCOVERED = (
    "pune",
    "jaipur",
    "ahmedabad",
    "leh",
    "bhopal",
    "chandigarh",
    "indore",
    "surat",
    "nagpur",
    "goa",
    "agra",
    "varanasi",
    "guwahati",
    "bhubaneswar",
    "ranchi",
    "dehradun",
    "srinagar",
    "amritsar",
    "ludhiana",
    "noida",
    "gurgaon",
    "gurugram",
    "thane",
    "nashik",
    "पुणे",
    "पुण्यात",
    "पुण्यातील",
    "पुण्याची",
    "जयपुर",
    "अहमदाबाद",
    "भोपाल",
    "चंडीगढ़",
    "नागपूर",
    "नागपुर",
    "आग्रा",
    "वाराणसी",
)

KW = {
    "medical": (
        "medicine",
        "tablet",
        "doctor",
        "chest pain",
        "symptom",
        "dizzy",
        "faint",
        "collapsed",
        "heatstroke",
        "heat stroke",
        "vomit",
        "दवा",
        "डॉक्टर",
        "चक्कर",
        "बेहोश",
        "औषध",
        "डॉक्टर",
        "छाती",
    ),
    "politics": (
        "government",
        "hiding",
        "hide",
        "manipulat",
        "fake",
        "fudg",
        "cheat",
        "blame",
        "सरकार",
        "छुपा",
        "छिपा",
        "लपव",
        "खोटा",
    ),
    "help": (
        "what does",
        "what is",
        "how do you",
        "how is",
        "how does",
        "meaning",
        "explain",
        "मतलब",
        "क्या होता",
        "म्हणजे",
        "कसे काम",
    ),
    "find": (
        "where",
        "place",
        "trip",
        "travel",
        "vacation",
        "weekend",
        "escape",
        "go to",
        "जगह",
        "कहाँ",
        "घूम",
        "ठिकाण",
        "कुठे",
        "सहल",
    ),
    "shadow": (
        "shadow",
        "different",
        "differ",
        "your estimate",
        "real aqi",
        "true aqi",
        "अनुमान",
        "अंतर",
        "फरक",
        "खरी",
    ),
    "completeness": (
        "complete",
        "missing",
        "gap",
        "silent",
        "reliab",
        "trust",
        "stations",
        "डेटा पूरा",
        "स्टेशन",
        "अपूर्ण",
        "भरोसा",
        "विश्वास",
        "पूर्ण",
    ),
    "heat": (
        "heat",
        "hot",
        "wet-bulb",
        "wet bulb",
        "work outside",
        "outdoor work",
        "labour",
        "गर्मी",
        "गरमी",
        "लू",
        "उष्णता",
        "ऊन",
        "उकाडा",
    ),
    "forecast": (
        "tomorrow",
        "forecast",
        "next",
        "week",
        "coming days",
        "कल",
        "अगले",
        "उद्या",
        "पुढील",
        "येत्या",
    ),
    "safe": (
        "safe",
        "mask",
        "run",
        "jog",
        "walk",
        "exercise",
        "asthma",
        "child",
        "precaution",
        "सुरक्षित",
        "मास्क",
        "दौड़",
        "व्यायाम",
        "धावणे",
        "काळजी",
    ),
}

YESTERDAY = ("yesterday", "काल", "बीते कल", "पिछले दिन")


def has(text: str, key: str) -> bool:
    return any(
        re.search(r"\b" + re.escape(w) if w.isascii() else re.escape(w), text) for w in KW[key]
    )


def find_place(ctx: ToolContext, text: str, default: str | None) -> str | None:
    t = text.lower()
    for d in ctx.session.execute(select(District)).scalars():
        if re.search(r"\b" + re.escape(d.slug) + r"\b", t) or re.search(
            r"\b" + re.escape(d.name.lower()) + r"\b", t
        ):
            return d.slug
    for name, slug in NAMES.items():
        if name in text or (name.isascii() and re.search(r"\b" + re.escape(name) + r"\b", t)):
            return slug
    for name in UNCOVERED:
        if name in text or (name.isascii() and re.search(r"\b" + re.escape(name) + r"\b", t)):
            return name
    return default


# ---------------------------------------------------------------- templates

T = {
    "na": {
        "en": "Sorry, the data is not available: {reason}.",
        "hi": "माफ़ कीजिए, यह डेटा उपलब्ध नहीं है: {reason}।",
        "mr": "माफ करा, हा डेटा उपलब्ध नाही: {reason}.",
    },
    "aqi": {
        "en": "AQI in {place} ({when}): {aqi}, {category}. Main pollutant: {main}.",
        "hi": "{place} में AQI ({when}): {aqi}, {category}। मुख्य प्रदूषक: {main}।",
        "mr": "{place} मधील AQI ({when}): {aqi}, {category}. मुख्य प्रदूषक: {main}.",
    },
    "complete": {
        "en": "{place}, {date}: {pct}% of expected station readings arrived from {n} "
        "stations. {silent} station(s) were silent for 3+ hours.{flag}",
        "hi": "{place}, {date}: {n} स्टेशनों से अपेक्षित रीडिंग में से {pct}% मिलीं। "
        "{silent} स्टेशन 3+ घंटे बंद रहे।{flag}",
        "mr": "{place}, {date}: {n} स्टेशनकडून अपेक्षित नोंदींपैकी {pct}% मिळाल्या. "
        "{silent} स्टेशन 3+ तास बंद होती.{flag}",
    },
    "flag": {
        "en": " Missing readings clustered in the most polluted hours "
        "({p}% missing vs {c}% in the cleanest hours).",
        "hi": " गायब रीडिंग सबसे प्रदूषित घंटों में ज़्यादा थीं ({p}% बनाम {c}%)।",
        "mr": " गहाळ नोंदी सर्वाधिक प्रदूषित तासांमध्ये जास्त होत्या ({p}% विरुद्ध {c}%).",
    },
    "shadow": {
        "en": "Shadow AQI for {place}: {shadow} (likely {lo}–{hi}){official}. It fills "
        "missing station-hours from nearby stations; it is an estimate shown next "
        "to the official figure, never instead of it.",
        "hi": "{place} का शैडो AQI: {shadow} (संभावित {lo}–{hi}){official}। यह आस-पास के "
        "स्टेशनों से गायब घंटे भरता है; यह अनुमान है, आधिकारिक आंकड़े की जगह नहीं।",
        "mr": "{place} चा शॅडो AQI: {shadow} (शक्य {lo}–{hi}){official}. हा जवळच्या "
        "स्टेशनवरून गहाळ तास भरतो; हा अंदाज आहे, अधिकृत आकड्याऐवजी नाही.",
    },
    "official": {
        "en": "; official CPCB AQI {o}",
        "hi": "; आधिकारिक CPCB AQI {o}",
        "mr": "; अधिकृत CPCB AQI {o}",
    },
    "heat": {
        "en": "Heat in {place}: feels like {feels} °C, wet-bulb {wb} °C, level {level}. "
        "{instr} Safe work windows today: {windows}.",
        "hi": "{place} में गर्मी: महसूस {feels} °C, वेट-बल्ब {wb} °C, स्तर {level}। {instr} "
        "आज सुरक्षित काम का समय: {windows}।",
        "mr": "{place} मधील उष्णता: जाणवणारे {feels} °C, वेट-बल्ब {wb} °C, पातळी {level}. "
        "{instr} आज सुरक्षित कामाची वेळ: {windows}.",
    },
    "forecast": {
        "en": "{place} forecast (estimated): {items}.",
        "hi": "{place} का पूर्वानुमान (अनुमान): {items}।",
        "mr": "{place} चा अंदाज: {items}.",
    },
    "find": {
        "en": "From {place}, {kind}: {items}.",
        "hi": "{place} से, {kind}: {items}।",
        "mr": "{place} पासून, {kind}: {items}.",
    },
    "advice": {
        "en": "Official advice: {text}",
        "hi": "आधिकारिक सलाह: {text}",
        "mr": "अधिकृत सल्ला: {text}",
    },
    "doctor": {
        "en": "I can't give medical advice. Please see a doctor. If someone shows "
        "heatstroke signs (confusion, hot dry skin, fainting), call 108 and cool them.",
        "hi": "मैं चिकित्सा सलाह नहीं दे सकता। कृपया डॉक्टर से मिलें। हीटस्ट्रोक के लक्षण "
        "(भ्रम, गर्म सूखी त्वचा, बेहोशी) दिखें तो 108 पर कॉल करें और ठंडक दें।",
        "mr": "मी वैद्यकीय सल्ला देऊ शकत नाही. कृपया डॉक्टरांना भेटा. उष्माघाताची लक्षणे "
        "(गोंधळ, गरम कोरडी त्वचा, बेशुद्धी) दिसल्यास 108 वर कॉल करा आणि थंड ठेवा.",
    },
    "neutral": {
        "en": "VayuKavach reports data completeness and reliability only; it does not "
        "assign blame.",
        "hi": "VayuKavach केवल डेटा की पूर्णता और विश्वसनीयता बताता है; किसी पर दोष नहीं लगाता।",
        "mr": "VayuKavach फक्त डेटाची पूर्णता आणि विश्वसनीयता सांगते; कोणावर दोष ठेवत नाही.",
    },
}

HELP = {
    "en": "Measured values come from monitoring stations; Estimated values come from a model or "
    "are filled from nearby stations. The shadow AQI fills missing station-hours from "
    "stations within 15 km and is shown next to the official AQI with its error band. Data "
    "completeness is the share of expected hourly readings that arrived.",
    "hi": "मापे गए (Measured) मान स्टेशनों से आते हैं; अनुमानित (Estimated) मान मॉडल से या आस-पास "
    "के स्टेशनों से भरे जाते हैं। शैडो AQI 15 किमी के भीतर के स्टेशनों से गायब घंटे भरता है। "
    "डेटा पूर्णता = अपेक्षित घंटेवार रीडिंग में से कितनी मिलीं।",
    "mr": "मोजलेली (Measured) मूल्ये स्टेशनवरून येतात; अंदाजित (Estimated) मूल्ये मॉडेलमधून किंवा "
    "जवळच्या स्टेशनवरून भरली जातात. शॅडो AQI 15 किमीतील स्टेशनवरून गहाळ तास भरतो. डेटा "
    "पूर्णता = अपेक्षित तासिक नोंदींपैकी किती मिळाल्या.",
}

WHEN = {
    "en": {"today": "now", "yesterday": "yesterday"},
    "hi": {"today": "अभी", "yesterday": "कल"},
    "mr": {"today": "आता", "yesterday": "काल"},
}
POLLUTANT = {
    "pm25": "PM2.5",
    "pm10": "PM10",
    "no2": "NO₂",
    "so2": "SO₂",
    "co": "CO",
    "o3": "O₃",
    None: "–",
}


# Words the templates fill in, translated so Hindi/Marathi answers read in one language.
CATEGORY = {
    "hi": {
        "Good": "अच्छी",
        "Satisfactory": "संतोषजनक",
        "Moderate": "मध्यम",
        "Poor": "खराब",
        "Very poor": "बहुत खराब",
        "Severe": "गंभीर",
    },
    "mr": {
        "Good": "चांगली",
        "Satisfactory": "समाधानकारक",
        "Moderate": "मध्यम",
        "Poor": "वाईट",
        "Very poor": "अतिशय वाईट",
        "Severe": "गंभीर",
    },
}
LEVEL = {
    "hi": {"Normal": "सामान्य", "Caution": "सावधानी", "Danger": "खतरा", "Extreme": "अत्यधिक"},
    "mr": {"Normal": "सामान्य", "Caution": "सावधानता", "Danger": "धोका", "Extreme": "अतितीव्र"},
}
CITY = {
    "hi": {
        "Delhi": "दिल्ली",
        "Mumbai": "मुंबई",
        "Kolkata": "कोलकाता",
        "Chennai": "चेन्नई",
        "Bengaluru": "बेंगलुरु",
        "Hyderabad": "हैदराबाद",
        "Patna": "पटना",
        "Kanpur": "कानपुर",
        "Lucknow": "लखनऊ",
        "Shimla": "शिमला",
    },
}
CITY["mr"] = {**CITY["hi"], "Bengaluru": "बेंगळुरू"}
WORK_REST = {
    "hi": {
        "normal": "सामान्य काम करें। नियमित पानी पिएं।",
        "caution": "हर घंटे छाँव में आराम करें। हर 20 मिनट में एक कप पानी पिएं।",
        "danger": "भारी काम केवल सुबह 11 से पहले और शाम 4 के बाद। हर घंटे 30 मिनट छाँव में आराम।",
        "extreme": "भारी बाहरी काम बंद करें। छाँव में रहें, बार-बार पानी पिएं, एक-दूसरे का ध्यान रखें।",
    },
    "mr": {
        "normal": "नेहमीचे काम करा. नियमित पाणी प्या.",
        "caution": "दर तासाला सावलीत विश्रांती घ्या. दर 20 मिनिटांनी एक कप पाणी प्या.",
        "danger": "जड काम फक्त सकाळी 11 पूर्वी आणि दुपारी 4 नंतर. दर तासाला 30 मिनिटे सावलीत विश्रांती.",
        "extreme": "जड बाहेरील काम थांबवा. सावलीत राहा, वारंवार पाणी प्या, एकमेकांची काळजी घ्या.",
    },
}


def tr(kind: dict, lang: str, value):
    """Translate a filled-in word for hi/mr; English and unknown values pass through."""
    return kind.get(lang, {}).get(value, value) if value is not None else value


def _na(r: dict, lang: str) -> str:
    return T["na"][lang].format(reason=r.get("reason") or "no data")


def answer(ctx: ToolContext, text: str, place: str | None, lang: str) -> str:
    t = text.lower()
    place = find_place(ctx, text, place)
    parts: list[str] = []
    yesterday = any(w in t or w in text for w in YESTERDAY)
    day = "yesterday" if yesterday else "today"

    if re.search(r"\b(20[3-9]\d|21\d\d)\b", t):  # e.g. "AQI in 2030": not a forecast we have
        reason = {
            "en": "forecasts cover the next 10 days only",
            "hi": "पूर्वानुमान केवल अगले 10 दिनों का है",
            "mr": "अंदाज फक्त पुढील 10 दिवसांचा आहे",
        }[lang]
        return T["na"][lang].format(reason=reason)

    if has(t, "medical"):
        r = call(ctx, "get_aqi", {"place": place})
        if r["available"]:
            p = call(ctx, "get_precautions", {"level": r["category"]})
            parts.append(T["advice"][lang].format(text=" ".join(p["advice"])))
        if has(t, "heat"):
            h = call(ctx, "get_heat_risk", {"place": place})
            if h["available"]:
                p = call(ctx, "get_precautions", {"level": h["level"]})
                parts.append(T["advice"][lang].format(text=" ".join(p["advice"])))
        parts.append(T["doctor"][lang])
        return " ".join(parts)

    if has(t, "politics"):
        r = call(ctx, "get_completeness", {"place": place, "date": day})
        parts.append(_complete(r, lang))
        parts.append(T["neutral"][lang])
        return " ".join(parts)

    if has(t, "help") and not has(t, "heat") and not re.search(r"\baqi in\b", t):
        ctx.calls.append(
            {"tool": "help", "available": True, "source": SRC_METHODS, "time": None, "label": None}
        )
        return HELP[lang]

    if has(t, "find"):
        goal = "heat" if has(t, "heat") or "cool" in t or "ठंड" in text or "थंड" in text else "air"
        mode = (
            "vacation"
            if any(w in t for w in ("vacation", "holiday", "छुट्टी", "सुट्टी"))
            else "nearby"
            if any(w in t for w in ("near", "nearby", "पास", "जवळ"))
            else "daytrip"
        )
        r = call(ctx, "find_places", {"goal": goal, "mode": mode, "from_place": place})
        if not r["available"]:
            return _na(r, lang)
        unit = "AQI" if goal == "air" else "°C"
        items = "; ".join(
            f"{p['name']} ({p['distance_km']:.0f} km, {unit} {p['value']:g}, {p['label']})"
            for p in r["places"]
        )
        kind = {
            "en": "cleaner air" if goal == "air" else "cooler places",
            "hi": "साफ़ हवा" if goal == "air" else "ठंडी जगहें",
            "mr": "स्वच्छ हवा" if goal == "air" else "थंड ठिकाणे",
        }[lang]
        return T["find"][lang].format(place=tr(CITY, lang, r["from"]), kind=kind, items=items)

    if has(t, "shadow"):
        r = call(ctx, "get_shadow_aqi", {"place": place, "date": day})
        if not r["available"]:
            return _na(r, lang)
        off = T["official"][lang].format(o=r["official_aqi"]) if r["official_aqi"] else ""
        parts.append(
            T["shadow"][lang].format(
                place=tr(CITY, lang, r["place"]),
                shadow=r["shadow_aqi"],
                lo=r["band_low"],
                hi=r["band_high"],
                official=off,
            )
        )
        c = call(ctx, "get_completeness", {"place": place, "date": day})
        if c["available"]:
            parts.append(_complete(c, lang))
        return " ".join(parts)

    if has(t, "completeness"):
        return _complete(call(ctx, "get_completeness", {"place": place, "date": day}), lang)

    if has(t, "heat"):
        r = call(ctx, "get_heat_risk", {"place": place})
        if not r["available"]:
            return _na(r, lang)
        level_key = (r["level"] or "").lower()
        return T["heat"][lang].format(
            place=tr(CITY, lang, r["place"]),
            feels=r["feels_like_c"],
            wb=r["wet_bulb_c"],
            level=tr(LEVEL, lang, r["level"]),
            instr=WORK_REST.get(lang, {}).get(level_key, r["instruction"] or ""),
            windows=", ".join(r["safe_work_windows"]) or "–",
        )

    if has(t, "forecast") and not yesterday:
        r = call(ctx, "get_forecast", {"place": place, "days": 3})
        if not r["available"]:
            return _na(r, lang)
        items = "; ".join(f"{a['date']}: AQI {a['low']}–{a['high']}" for a in r["aqi"])
        parts.append(
            T["forecast"][lang].format(place=tr(CITY, lang, r["place"]), items=items or "–")
        )
        if has(t, "safe") and r["aqi"]:
            from app.analysis.aqi import category

            worst = category(r["aqi"][min(1, len(r["aqi"]) - 1)]["high"])
            if worst:
                p = call(ctx, "get_precautions", {"level": worst[1]})
                parts.append(T["advice"][lang].format(text=" ".join(p["advice"])))
        return " ".join(parts)

    r = call(ctx, "get_aqi", {"place": place, "date": day})
    if not r["available"]:
        return _na(r, lang)
    parts.append(
        T["aqi"][lang].format(
            place=tr(CITY, lang, r["place"]),
            when=WHEN[lang][day],
            aqi=r["aqi"],
            category=tr(CATEGORY, lang, r["category"]),
            main=POLLUTANT.get(r["main_pollutant"], r["main_pollutant"]),
        )
    )
    if has(t, "safe"):
        p = call(ctx, "get_precautions", {"level": r["category"]})
        if p["available"]:
            parts.append(T["advice"][lang].format(text=" ".join(p["advice"])))
    return " ".join(parts)


def _complete(r: dict, lang: str) -> str:
    if not r["available"]:
        return _na(r, lang)
    flag = ""
    if r.get("missing_when_it_mattered_flag"):
        flag = T["flag"][lang].format(
            p=r["polluted_hours_missing_pct"], c=r["clean_hours_missing_pct"]
        )
    return T["complete"][lang].format(
        place=tr(CITY, lang, r["place"]),
        date=r["date"],
        pct=r["completeness_pct"],
        n=r["stations"],
        silent=r["stations_silent_3h"],
        flag=flag,
    )
