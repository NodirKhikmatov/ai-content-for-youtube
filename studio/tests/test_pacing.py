from studio.pacing import WORDS_PER_MINUTE, seconds_for_words, word_count, words_for_seconds


def test_seconds_for_words_at_exactly_one_minute():
    assert seconds_for_words(WORDS_PER_MINUTE) == 60


def test_words_for_seconds_round_trips_seconds_for_words():
    assert words_for_seconds(seconds_for_words(300)) == 300


def test_word_count_splits_on_whitespace():
    assert word_count("The quick brown fox") == 4
    assert word_count("") == 0
