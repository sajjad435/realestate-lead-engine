import re
from typing import Dict, List, Pattern, Tuple

class AntiSpamSanitizer:
    """
    Sanitizes cold email subject lines and body copy to ensure 100% primary inbox delivery.
    Replaces aggressive spam triggers, marketing hype, and spam filter red flags
    with natural, professional, and deliverable conversational wording.
    """
    SPAM_REPLACEMENTS: List[Tuple[Pattern, str]] = [
        # 1. High-severity financial / freebie spam triggers
        (re.compile(r"\bquick\s+free\b", re.IGNORECASE), "quick sample"),
        (re.compile(r"\bfree\b", re.IGNORECASE), "complimentary"),
        (re.compile(r"\b100%(?!\w)", re.IGNORECASE), "completely"),
        (re.compile(r"\bguarantee\b", re.IGNORECASE), "ensure"),
        (re.compile(r"\bguarantees\b", re.IGNORECASE), "ensures"),
        (re.compile(r"\bguaranteed\b", re.IGNORECASE), "ensured"),
        (re.compile(r"\brisk[- ]free\b", re.IGNORECASE), "seamless"),
        (re.compile(r"\bno[- ]cost\b", re.IGNORECASE), "complimentary"),
        
        # 2. Call-to-action & urgency pressure triggers
        (re.compile(r"\bclick here\b", re.IGNORECASE), "view here"),
        (re.compile(r"\bclick below\b", re.IGNORECASE), "take a look below"),
        (re.compile(r"\bact now\b", re.IGNORECASE), "take a look"),
        (re.compile(r"\blimited time\b", re.IGNORECASE), "currently"),
        (re.compile(r"\bspecial offer\b", re.IGNORECASE), "preview opportunity"),
        (re.compile(r"\border now\b", re.IGNORECASE), "reach out"),
        (re.compile(r"\burgent\b", re.IGNORECASE), "timely"),
        (re.compile(r"\bcheap\b", re.IGNORECASE), "affordable"),
        (re.compile(r"\binstant\b", re.IGNORECASE), "convenient"),
        (re.compile(r"\bcongratulations\b", re.IGNORECASE), "greetings"),
        
        # 3. Agency hype & buzzwords
        (re.compile(r"\bgrowth consultant\b", re.IGNORECASE), "Web Consultant"),
    ]

    PROMOTIONAL_EMOJIS_REGEX = re.compile(r"[👉🔥🚀💰⭐⚡🤑💸❗‼️💯✨💥🎯📢]")

    @classmethod
    def clean(cls, text: str) -> str:
        if not text:
            return ""

        result = text

        # 1. Replace spam triggers with natural context-preserving alternatives
        for pattern, replacement in cls.SPAM_REPLACEMENTS:
            result = pattern.sub(replacement, result)

        # 2. Strip promotional emojis that push emails into 'Promotions' or 'Spam'
        result = cls.PROMOTIONAL_EMOJIS_REGEX.sub("", result)

        # 3. Clean up any double spaces created by emoji removal
        result = re.sub(r"[ ]{2,}", " ", result)

        return result
