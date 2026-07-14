from concurrent.futures import ThreadPoolExecutor

import fakeredis
import pytest
from redis.exceptions import WatchError

from src.services.session_store import InMemorySessionStore, validate_session_id
from src.services.session_store_redis import RedisSessionStore

SESSION_ID = "123e4567-e89b-42d3-a456-426614174000"
OTHER_SESSION_ID = "123e4567-e89b-42d3-b456-426614174001"


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
    assert client.ttl(f"persona-studio:session:{session_id}") > 0

    store.clear(session_id)
    assert store.get_history(session_id) == []
    assert store.get_preferred_language(session_id) is None


def test_redis_session_store_handles_bytes_client() -> None:
    client = fakeredis.FakeRedis(decode_responses=False)
    store = RedisSessionStore(
        redis_url="redis://unused",
        max_history=4,
        ttl_seconds=60,
        client=client,
    )
    session_id = store.get_or_create(None)
    store.add_turn(session_id, "hello", "world")

    assert store.get_history(session_id) == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]


def test_redis_session_store_retries_conflicts_and_refreshes_ttl(monkeypatch) -> None:
    client = fakeredis.FakeRedis(decode_responses=True)
    store = RedisSessionStore(redis_url="redis://unused", ttl_seconds=60, client=client)
    original_pipeline = client.pipeline
    conflict_raised = False

    def pipeline_with_one_conflict(*args, **kwargs):
        nonlocal conflict_raised
        pipeline = original_pipeline(*args, **kwargs)
        original_execute = pipeline.execute

        def execute(*execute_args, **execute_kwargs):
            nonlocal conflict_raised
            if not conflict_raised:
                conflict_raised = True
                raise WatchError
            return original_execute(*execute_args, **execute_kwargs)

        pipeline.execute = execute
        return pipeline

    monkeypatch.setattr(client, "pipeline", pipeline_with_one_conflict)
    store.add_turn(SESSION_ID, "hello", "world")

    assert conflict_raised is True
    assert store.get_history(SESSION_ID)[-1]["content"] == "world"
    assert 0 < client.ttl(f"persona-studio:session:{SESSION_ID}") <= 60


def test_redis_session_store_preserves_concurrent_turns() -> None:
    client = fakeredis.FakeRedis(decode_responses=True)
    store = RedisSessionStore(
        redis_url="redis://unused",
        max_history=40,
        ttl_seconds=60,
        client=client,
    )

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(store.add_turn, OTHER_SESSION_ID, f"user-{index}", f"reply-{index}")
            for index in range(10)
        ]
        for future in futures:
            future.result()

    history = store.get_history(OTHER_SESSION_ID)
    assert len(history) == 20
    assert {item["content"] for item in history if item["role"] == "user"} == {
        f"user-{index}" for index in range(10)
    }
    assert 0 < client.ttl(f"persona-studio:session:{OTHER_SESSION_ID}") <= 60


def test_session_stores_accept_uuid_and_internal_telegram_ids() -> None:
    store = InMemorySessionStore()
    generated_id = store.get_or_create(None)

    assert validate_session_id(generated_id) == generated_id
    for session_id in (SESSION_ID, "telegram:123456", "telegram:-100123456"):
        assert store.get_or_create(session_id) == session_id
        store.add_turn(session_id, "hello", "world")
        assert len(store.get_history(session_id)) == 2


@pytest.mark.parametrize(
    "session_id",
    [
        "",
        " leading",
        "trailing ",
        "contains spaces",
        "../escape",
        "中文",
        "client-session_01",
        "123e4567-e89b-12d3-a456-426614174000",
        "telegram:user",
    ],
)
def test_session_store_rejects_unsafe_session_ids(session_id: str) -> None:
    memory_store = InMemorySessionStore()
    redis_store = RedisSessionStore(redis_url="redis://unused", client=fakeredis.FakeRedis())

    with pytest.raises(ValueError):
        memory_store.get_or_create(session_id)
    with pytest.raises(ValueError):
        redis_store.get_or_create(session_id)


@pytest.mark.parametrize("store_type", [InMemorySessionStore, RedisSessionStore])
def test_session_store_requires_capacity_for_a_complete_turn(store_type) -> None:
    with pytest.raises(ValueError, match="at least one user/assistant turn"):
        if store_type is InMemorySessionStore:
            store_type(max_history=1)
        else:
            store_type(redis_url="redis://unused", max_history=1, client=fakeredis.FakeRedis())
