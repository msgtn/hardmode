import pytest
import moderation

QUESTION = "What is the most embarrassing thing you've done?"


@pytest.fixture(scope="session", autouse=True)
def load_models():
    moderation.preload()


def test_clean_answer():
    r = moderation.moderate(QUESTION, "I tripped on stage in front of my whole school.")
    assert r.approved


def test_empty():
    r = moderation.moderate(QUESTION, "")
    assert not r.approved
    assert "empty" in r.reason.lower()


def test_too_long():
    r = moderation.moderate(QUESTION, "a" * 501)
    assert not r.approved
    assert "too long" in r.reason.lower()


def test_url():
    r = moderation.moderate(QUESTION, "Check out https://example.com for more.")
    assert not r.approved
    assert "link" in r.reason.lower()


def test_profanity():
    r = moderation.moderate(QUESTION, "I got fucking wasted at my boss's party.")
    assert not r.approved
    assert "profanity" in r.reason.lower()


def test_threat():
    r = moderation.moderate(QUESTION, "I will hurt you if you tell anyone.")
    assert not r.approved
    assert "threat" in r.reason.lower()


def test_irrelevant():
    r = moderation.moderate(QUESTION, "The mitochondria is the powerhouse of the cell.")
    assert not r.approved
    assert "relevant" in r.reason.lower()
