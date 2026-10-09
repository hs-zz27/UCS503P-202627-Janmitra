"""Query expansion shared by published and pending catalogue searches."""

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class NeedConcept:
    """Retrieval hints, never eligibility rules or promises of scheme coverage."""

    name: str
    phrases: tuple[str, ...]
    slugs: tuple[str, ...]


# Keep vocabulary separate from routing. Each route names only a bundled programme;
# missing domains intentionally have no candidate rather than a fabricated match.
NEED_CONCEPTS = (
    NeedConcept(
        "housing",
        (
            "housing",
            "need a house",
            "need house",
            "home repair",
            "repair our house",
            "repair my house",
            "damaged house",
            "leaking roof",
            "roof leaks",
            "homeless",
            "eviction",
            "evicted",
            "shelter",
            "rent",
            "hut",
            "कच्चा",
            "मकान नहीं",
            "मकान चाहिए",
            "बेघर",
            "छत टूट",
            "किराया",
            "घर चाहिए",
            "घर नहीं",
            "ਘਰ ਚਾਹੀਦਾ",
            "ਮਕਾਨ ਨਹੀਂ",
            "ਬੇਘਰ",
            "ਛੱਤ ਟੁੱਟ",
            "ਕਿਰਾਇਆ",
            "mujhe ghar",
            "ghar chahiye",
            "makaan chahiye",
            "makan nahi",
        ),
        ("pmay-g",),
    ),
    NeedConcept(
        "food",
        (
            "food",
            "ration",
            "hungry",
            "hunger",
            "grain",
            "groceries",
            "राशन",
            "अनाज",
            "भूख",
            "खाना",
            "ਰਾਸ਼ਨ",
            "ਅਨਾਜ",
            "ਭੁੱਖ",
            "ਖਾਣਾ",
            "rashan",
            "ration",
            "khana",
        ),
        ("pmgkay",),
    ),
    NeedConcept(
        "employment",
        (
            "job",
            "jobs",
            "work",
            "unemployed",
            "unemployment",
            "wages",
            "livelihood",
            "रोजगार",
            "रोज़गार",
            "नौकरी",
            "बेरोजगार",
            "मजदूरी",
            "काम",
            "ਰੁਜ਼ਗਾਰ",
            "ਨੌਕਰੀ",
            "ਬੇਰੁਜ਼ਗਾਰ",
            "ਮਜ਼ਦੂਰੀ",
            "ਕੰਮ",
            "naukri",
            "berozgar",
            "rozgar",
            "mazdoori",
        ),
        ("mgnrega", "day-nrlm"),
    ),
    NeedConcept(
        "medical",
        (
            "hospital",
            "treatment",
            "medical",
            "health",
            "surgery",
            "operation",
            "illness",
            "sick",
            "अस्पताल",
            "इलाज",
            "बीमार",
            "स्वास्थ्य",
            "ਹਸਪਤਾਲ",
            "ਇਲਾਜ",
            "ਬਿਮਾਰ",
            "ilaaj",
            "ilaj",
            "bimar",
        ),
        ("pm-jay",),
    ),
    NeedConcept(
        "enterprise",
        (
            "business",
            "shop",
            "enterprise",
            "self employed",
            "self-employed",
            "startup",
            "start up",
            "दुकान",
            "व्यापार",
            "कारोबार",
            "धंधा",
            "ਦੁਕਾਨ",
            "ਕਾਰੋਬਾਰ",
            "ਵਪਾਰ",
            "dukan",
            "dukkan",
            "karobar",
        ),
        ("pmmy", "pmegp"),
    ),
    NeedConcept(
        "credit",
        (
            "loan",
            "credit",
            "borrow",
            "borrowed",
            "borrowing",
            "loans",
            "owe",
            "owes",
            "debt",
            "repayment",
            "moneylender",
            "ऋण",
            "कर्ज",
            "क़र्ज़",
            "कर्ज़",
            "उधार",
            "लोन",
            "ਕਰਜ਼",
            "ਕਰਜ਼ਾ",
            "ਕਰਜ",
            "karz",
            "karja",
            "udhar",
            "rin",
        ),
        ("pmmy", "kcc", "pmegp", "pm-vishwakarma"),
    ),
    NeedConcept(
        "financial",
        (
            "financial",
            "finance",
            "financial schemes",
            "financial scheme",
            "financial support",
            "financial help",
            "financial assistance",
            "money help",
            "need money",
            "no money",
            "no income",
            "money problems",
            "cannot make ends meet",
            "struggling financially",
            "पैसे",
            "आर्थिक",
            "पैसा",
            "ਪੈਸੇ",
            "ਆਰਥਿਕ",
            "paise",
            "paisa",
        ),
        ("mgnrega", "pmjdy", "nsap", "pmmy"),
    ),
    NeedConcept(
        "farming",
        (
            "farmer",
            "farming",
            "agriculture",
            "crop",
            "crops",
            "harvest",
            "cultivate",
            "cultivation",
            "किसान",
            "खेती",
            "फसल",
            "ਕਿਸਾਨ",
            "ਖੇਤੀ",
            "ਫਸਲ",
            "kisan",
            "kisaan",
            "fasal",
            "kheti",
        ),
        ("kcc", "pm-kisan", "pmfby"),
    ),
    NeedConcept(
        "crop_insurance",
        (
            "crop insurance",
            "crop loss",
            "crop failed",
            "crop failure",
            "crop damage",
            "failed harvest",
            "flooded field",
            "फसल बीमा",
            "फसल खराब",
            "ਫਸਲ ਬੀਮਾ",
            "fasal bima",
            "fasal beema",
            "fasal kharab",
        ),
        ("pmfby",),
    ),
    NeedConcept(
        "pension",
        (
            "pension",
            "elderly",
            "old age",
            "widow",
            "disability pension",
            "पेंशन",
            "बुजुर्ग",
            "विधवा",
            "ਪੈਨਸ਼ਨ",
            "ਬਜ਼ੁਰਗ",
            "ਵਿਧਵਾ",
            "buzurg",
            "vidhwa",
        ),
        ("nsap", "apy", "pm-sym"),
    ),
    NeedConcept(
        "retirement",
        ("retirement", "retire", "save for old age", "रिटायरमेंट", "सेवानिवृत्ति"),
        ("apy", "pm-sym"),
    ),
    NeedConcept(
        "banking",
        (
            "bank account",
            "unbanked",
            "savings account",
            "zero balance",
            "बैंक खाता",
            "बैंक अकाउंट",
            "ਬੈਂਕ ਖਾਤਾ",
            "bank khata",
        ),
        ("pmjdy",),
    ),
    NeedConcept(
        "cooking",
        (
            "cooking gas",
            "lpg",
            "gas connection",
            "firewood",
            "chulha",
            "उज्ज्वला",
            "चूल्हा",
            "रसोई गैस",
            "लकड़ी",
            "ਚੁੱਲ੍ਹਾ",
            "ਰਸੋਈ ਗੈਸ",
        ),
        ("pmuy",),
    ),
    NeedConcept(
        "artisan",
        (
            "artisan",
            "craftsman",
            "craftsperson",
            "carpenter",
            "tailor",
            "cobbler",
            "blacksmith",
            "potter",
            "कारीगर",
            "बढ़ई",
            "दर्जी",
            "ਕਾਰੀਗਰ",
            "ਦਰਜ਼ੀ",
            "karigar",
            "darzi",
        ),
        ("pm-vishwakarma",),
    ),
    NeedConcept(
        "women_group",
        (
            "self help group",
            "self-help group",
            "women group",
            "महिला समूह",
            "स्वयं सहायता",
            "ਮਹਿਲਾ ਸਮੂਹ",
            "shg",
        ),
        ("day-nrlm",),
    ),
    NeedConcept(
        "insurance",
        ("insurance", "बीमा", "ਬੀਮਾ", "bima", "beema"),
        ("pmjjby", "pmsby", "pmfby", "pm-jay"),
    ),
    NeedConcept(
        "life_insurance",
        (
            "life insurance",
            "death insurance",
            "life cover",
            "जीवन बीमा",
            "ਜੀਵਨ ਬੀਮਾ",
            "jeevan bima",
        ),
        ("pmjjby",),
    ),
    NeedConcept(
        "accident_insurance",
        ("accident", "दुर्घटना", "ਹਾਦਸਾ", "durghatna"),
        ("pmsby",),
    ),
)


def contains_phrase(text: str, phrase: str) -> bool:
    """Match whole phrases, including scripts whose vowel marks are not regex \\w."""
    text = unicodedata.normalize("NFKC", text).casefold()
    phrase = unicodedata.normalize("NFKC", phrase).casefold()
    pattern = (
        r"(?<![\w\u0900-\u097f\u0a00-\u0a7f])"
        + re.escape(phrase)
        + r"(?![\w\u0900-\u097f\u0a00-\u0a7f])"
    )
    return re.search(pattern, text) is not None


def query_needs(query: str) -> tuple[NeedConcept, ...]:
    concepts = [
        concept
        for concept in NEED_CONCEPTS
        if any(contains_phrase(query, p) for p in concept.phrases)
    ]
    names = {concept.name for concept in concepts}
    # A specific need replaces its generic parent, leaving unrelated needs intact.
    suppressed = set()
    if any(
        contains_phrase(query, phrase)
        for phrase in (
            "don't want a loan",
            "do not want a loan",
            "don't want loans",
            "not looking for a loan",
            "no more loans",
            "cannot take another loan",
            "कर्ज नहीं चाहिए",
            "लोन नहीं चाहिए",
            "karz nahi chahiye",
        )
    ):
        suppressed.add("credit")
    if "crop_insurance" in names:
        suppressed.add("farming")
    if "insurance" in names and "farming" in names:
        concepts = [NeedConcept("crop_insurance", (), ("pmfby",)), *concepts]
        suppressed.add("farming")
    if names & {"crop_insurance", "life_insurance", "accident_insurance", "medical", "farming"}:
        suppressed.add("insurance")
    if "farming" in names and "credit" in names and "credit" not in suppressed:
        concepts = [NeedConcept("farm_credit", (), ("kcc",)), *concepts]
        suppressed.update({"farming", "credit"})
    if "enterprise" in names or "artisan" in names:
        suppressed.add("credit")
    if "retirement" in names:
        suppressed.add("pension")
    if "pension" in names and any(
        contains_phrase(query, term)
        for term in ("unorganised", "unorganized", "labour", "informal worker", "असंगठित", "ਮਜ਼ਦੂਰ")
    ):
        concepts = [NeedConcept("worker_pension", (), ("pm-sym",)), *concepts]
        suppressed.add("pension")
    return tuple(concept for concept in concepts if concept.name not in suppressed)


QUERY_EXPANSIONS = {
    "किसान": "farmer",
    "खेती": "farming",
    "फसल": "crop",
    "बीमा": "insurance",
    "ऋण": "loan",
    "लोन": "loan",
    "पेंशन": "pension",
    "राशन": "ration",
    "घर": "housing",
    "रोजगार": "employment",
    "ਕਿਸਾਨ": "farmer",
    "ਫਸਲ": "crop",
    "ਬੀਮਾ": "insurance",
    "ਕਰਜ਼": "loan",
    "ਪੈਨਸ਼ਨ": "pension",
}
TRANSLITERATIONS = {
    "kisan": "farmer",
    "kisaan": "farmer",
    "fasal": "crop",
    "bima": "insurance",
    "beema": "insurance",
    "karz": "loan",
    "rin": "loan",
}


def expand_query(query: str) -> str:
    normalized = unicodedata.normalize("NFKC", query).casefold()
    expansions = [value for phrase, value in QUERY_EXPANSIONS.items() if phrase in normalized]
    words = set(re.findall(r"[a-z]+", normalized))
    expansions.extend(value for word, value in TRANSLITERATIONS.items() if word in words)
    return normalized + " " + " ".join(expansions)
