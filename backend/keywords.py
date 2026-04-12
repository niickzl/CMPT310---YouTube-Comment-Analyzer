from collections import Counter

import spacy

nlp = None


def getnlp():
    global nlp
    if nlp is None:
        nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
    return nlp


def extract_keywords(
    texts: list[str],
    top_n: int = 5,
) -> list[tuple[str, int]]:
    if not texts:
        return []

    nlp = getnlp()
    counter: Counter = Counter()

    for doc in nlp.pipe(texts, batch_size=50):
        for token in doc:
            if (
                token.pos_ in ("NOUN", "PROPN")
                and not token.is_stop
                and len(token.text) > 2
            ):
                counter[token.lemma_.lower()] += 1

    return counter.most_common(top_n)