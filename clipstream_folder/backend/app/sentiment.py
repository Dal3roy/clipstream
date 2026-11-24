"""Sentiment analysis for comments.

Step 3 uses a word list so the API works offline. Step 5 replaces the body of
analyse() with a call to Azure AI Language. The return shape must stay the same,
because the frontend reads label and scores directly.
"""
import re

POSITIVE = {
    "love", "great", "amazing", "good", "clean", "worked", "best", "favourite", "nice",
    "perfect", "thanks", "awesome", "brilliant", "saving", "satisfying",
}
NEGATIVE = {
    "bad", "hate", "worst", "boring", "awful", "terrible", "wrong", "fail", "broken",
    "annoying", "disappointed", "blurry",
}


def analyse(text: str) -> dict:
    words = re.findall(r"[a-z']+", text.lower())
    pos = sum(word in POSITIVE for word in words)
    neg = sum(word in NEGATIVE for word in words)

    if pos > neg:
        label = "positive"
    elif neg > pos:
        label = "negative"
    else:
        label = "neutral"

    total = pos + neg + 2
    return {
        "label": label,
        "scores": {
            "positive": round((pos + 1) / total, 2),
            "neutral": round(1 / total, 2),
            "negative": round((neg + 1) / total, 2),
        },
    }
