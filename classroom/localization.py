"""Language selection for bilingual classroom copy."""


def words(language, copy):
    index = 1 if language == "zh-Hant" else 0
    return {key: pair[index] for key, pair in copy.items()}
