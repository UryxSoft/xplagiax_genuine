from app.infrastructure.chunking.word_token_counter import WordTokenCounter


def test_counts_words_and_punctuation_separately() -> None:
    counter = WordTokenCounter()
    assert counter.tokenize("Hola, mundo.") == ["Hola", ",", "mundo", "."]
    assert counter.count("Hola, mundo.") == 4


def test_empty_string_has_zero_tokens() -> None:
    counter = WordTokenCounter()
    assert counter.count("") == 0


def test_unicode_words_are_kept_whole() -> None:
    counter = WordTokenCounter()
    assert counter.tokenize("día número 42") == ["día", "número", "42"]
