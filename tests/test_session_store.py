import fakeredis

from src.services.session_store import InMemorySessionStore
from src.services.session_store_redis import RedisSessionStore


def test_in_memory_session_store_trims_to_max_history() -> None:
    store = InMemorySessionStore(max_history=4)
    session_id = store.get_or_create(None)

    store.add_turn(session_id, "u1", "a1")
    store.add_turn(session_id, "u2", "a2")
    store.add_turn(session_id, "u3", "a3")

    assert store.get_history(session_id) == [
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
        {"role": "user", "content": "u3"},
        {"role": "assistant", "content": "a3"},
    ]


def test_in_memory_session_store_persists_language_preference() -> None:
    store = InMemorySessionStore(max_history=4)
    session_id = store.get_or_create(None)

    store.set_preferred_language(session_id, "ja")

    assert store.get_preferred_language(session_id) == "ja"

    store.clear(session_id)
    assert store.get_preferred_language(session_id) is None


def test_redis_session_store_persists_and_clears() -> None:
    client = fakeredis.FakeRedis(decode_responses=True)
    store = RedisSessionStore(
        redis_url="redis://unused",
        max_history=4,
        ttl_seconds=60,
        client=client,
    )
    session_id = store.get_or_create(None)

    store.add_turn(session_id, "hello", "world")
    store.set_preferred_language(session_id, "en")
    assert store.get_history(session_id) == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]
    assert store.get_preferred_language(session_id) == "en"
    assert client.ttl(f"nenebot:session:{session_id}") > 0

    store.clear(session_id)
    assert store.get_history(session_id) == []
    assert store.get_preferred_language(session_id) is None
