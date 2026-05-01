"""Deterministic quality checks for Nene datasets, retrieval, and live replies."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from statistics import mean
from typing import Any, cast

from src.evaluation.nene_benchmark_cases import BENCHMARK_CASES
from src.infrastructure.llm_base import BaseLLMClient
from src.services.chat_orchestrator import generate_chat_turn
from src.services.nene_tagging import (
    infer_tags,
    is_intimate_noise,
    is_low_signal_response,
)
from src.services.rag_pipeline import RAGPipeline
from src.services.session_store import InMemorySessionStore

EXPLICIT_RE = re.compile(r"肉棒|自慰|高潮|小●穴|射精|做爱|性爱|湿了|乳头|下着|セックス|初体験")
MOAN_RE = re.compile(r"(?:[哈啊嗯呜噗呼呀唔]{2,}[，、…！]*){3,}")
PLACEHOLDER_RE = re.compile(r"白蛇占|译注")
AI_LEAK_RE = re.compile(r"作为AI|语言模型|我是AI|作为助手")
LISTY_RE = re.compile(r"\n\s*[-1-9]")
INTIMATE_SOUND_RE = re.compile(r"啾|啾噜|啾啾|嘶噜|吸溜|呼噜|咕啾|噗啾")


def score_retrieval_hit(case: dict[str, object], top1: dict[str, Any]) -> tuple[int, list[str]]:
    penalties: list[str] = []
    score = 100
    query = str(case.get("query", ""))
    query_tags = set(infer_tags(query))
    top1_query = str(top1.get("query_text", ""))
    top1_response = str(top1.get("bot_response", ""))
    haystack = f"{top1_query}\n{top1_response}"
    hit_tags = set(top1.get("query_tags", [])) | set(top1.get("response_tags", []))

    required_tokens = [str(item) for item in cast("list[object]", case.get("must_include_any", []))]
    preferred_tokens = [
        str(item) for item in cast("list[object]", case.get("prefer_include_any", []))
    ]
    if required_tokens and not any(token in haystack for token in required_tokens):
        score -= 30
        penalties.append("missed_required_signal")
    if preferred_tokens and not any(token in haystack for token in preferred_tokens):
        score -= 10
        penalties.append("missed_preferred_signal")

    if is_low_signal_response(top1_response):
        score -= 20
        penalties.append("low_signal_response")

    if is_intimate_noise(haystack):
        score -= 60
        penalties.append("intimate_noise_hit")

    intimate_sound_hits = len(INTIMATE_SOUND_RE.findall(haystack))
    if intimate_sound_hits >= 2:
        score -= 25
        penalties.append("kissy_noise")

    if "comfort" in query_tags and not ({"comfort", "support"} & hit_tags):
        score -= 25
        penalties.append("missed_comfort_intent")

    if "witch" in query_tags and "witch" not in hit_tags:
        score -= 25
        penalties.append("missed_witch_intent")

    if ("club" in query_tags or "divination" in query_tags) and not (
        {"club", "divination"} & hit_tags
    ):
        score -= 20
        penalties.append("missed_setting_intent")

    if "gratitude" in query_tags and "gratitude" not in hit_tags:
        score -= 15
        penalties.append("missed_gratitude_intent")

    if "greeting" in query_tags and "greeting" not in hit_tags:
        score -= 15
        penalties.append("missed_greeting_intent")

    if (
        "relationship" in query_tags
        and "confession" not in query_tags
        and "intimate_noise" in hit_tags
    ):
        score -= 25
        penalties.append("wrong_relationship_tone")

    return max(score, 0), penalties


def load_jsonl_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if line:
                records.append(json.loads(line))
    return records


def extract_pair(record: dict[str, Any]) -> tuple[str, str, str]:
    system_text = ""
    user_text = ""
    assistant_text = ""
    for message in record.get("messages", []):
        role = message.get("role")
        content = str(message.get("content", "")).strip()
        if role == "system" and not system_text:
            system_text = content
        elif role == "user" and not user_text:
            user_text = content
        elif role == "assistant" and not assistant_text:
            assistant_text = content
    return system_text, user_text, assistant_text


def analyze_text_flags(text: str) -> dict[str, bool]:
    return {
        "explicit": bool(EXPLICIT_RE.search(text)),
        "moan": bool(MOAN_RE.search(text)),
        "placeholder": bool(PLACEHOLDER_RE.search(text)),
        "ai_leak": bool(AI_LEAK_RE.search(text)),
        "listy": bool(LISTY_RE.search(text)),
    }


def summarize_dataset(path: Path) -> dict[str, Any]:
    records = load_jsonl_records(path)
    system_prompts: set[str] = set()
    pair_keys: set[tuple[str, str]] = set()
    explicit_hits = 0
    moan_hits = 0
    placeholder_hits = 0
    ai_leak_hits = 0

    for record in records:
        system_text, user_text, assistant_text = extract_pair(record)
        if system_text:
            system_prompts.add(system_text)
        pair_keys.add((user_text, assistant_text))

        flags = analyze_text_flags(f"{user_text}\n{assistant_text}")
        explicit_hits += int(flags["explicit"])
        moan_hits += int(flags["moan"])
        placeholder_hits += int(flags["placeholder"])
        ai_leak_hits += int(flags["ai_leak"])

    line_count = len(records)
    duplicate_pairs = line_count - len(pair_keys)

    return {
        "path": str(path),
        "line_count": line_count,
        "unique_pair_count": len(pair_keys),
        "duplicate_pair_count": duplicate_pairs,
        "duplicate_pair_rate": round(duplicate_pairs / line_count, 4) if line_count else 0.0,
        "system_prompt_variants": len(system_prompts),
        "explicit_hits": explicit_hits,
        "moan_hits": moan_hits,
        "placeholder_hits": placeholder_hits,
        "ai_leak_hits": ai_leak_hits,
    }


def compare_dataset_summaries(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    def pct_change(new: int, old: int) -> float | None:
        if old == 0:
            return None
        return round((new - old) / old * 100, 2)

    return {
        "line_count_delta": current["line_count"] - baseline["line_count"],
        "line_count_delta_pct": pct_change(current["line_count"], baseline["line_count"]),
        "duplicate_pair_delta": current["duplicate_pair_count"] - baseline["duplicate_pair_count"],
        "explicit_hits_delta": current["explicit_hits"] - baseline["explicit_hits"],
        "moan_hits_delta": current["moan_hits"] - baseline["moan_hits"],
        "placeholder_hits_delta": current["placeholder_hits"] - baseline["placeholder_hits"],
        "ai_leak_hits_delta": current["ai_leak_hits"] - baseline["ai_leak_hits"],
    }


def evaluate_retrieval(
    rag: RAGPipeline,
    *,
    top_k: int = 3,
) -> dict[str, Any]:
    case_details: list[dict[str, Any]] = []
    top1_scores: list[float] = []
    nonempty_count = 0
    clean_count = 0
    quality_scores: list[int] = []

    for case in BENCHMARK_CASES:
        query = str(case["query"])
        results = rag.retrieve_and_filter(query, top_k=top_k)
        nonempty = bool(results)
        nonempty_count += int(nonempty)

        if results:
            top1_scores.append(float(results[0].get("similarity_score", 0.0)))

        clean = True
        for result in results:
            text = f"{result.get('query_text', '')}\n{result.get('bot_response', '')}"
            flags = analyze_text_flags(text)
            if flags["explicit"] or flags["moan"] or flags["placeholder"]:
                clean = False
                break
        clean_count += int(clean)

        top1 = results[0] if results else {}
        quality_score, penalties = score_retrieval_hit(case, top1) if results else (0, ["empty"])
        quality_scores.append(quality_score)
        case_details.append(
            {
                "id": case["id"],
                "query": query,
                "retrieved_count": len(results),
                "top1_similarity": round(float(top1.get("similarity_score", 0.0)), 4),
                "top1_query": top1.get("query_text", ""),
                "top1_response": top1.get("bot_response", ""),
                "clean": clean,
                "quality_score": quality_score,
                "penalties": penalties,
            }
        )

    case_count = len(BENCHMARK_CASES)
    return {
        "case_count": case_count,
        "nonempty_rate": round(nonempty_count / case_count, 4),
        "clean_rate": round(clean_count / case_count, 4),
        "avg_top1_similarity": round(mean(top1_scores), 4) if top1_scores else 0.0,
        "avg_quality_score": round(mean(quality_scores), 2) if quality_scores else 0.0,
        "cases": case_details,
    }


def score_reply(reply: str, case: dict[str, object]) -> dict[str, Any]:
    flags = analyze_text_flags(reply)
    score = 100
    penalties: list[str] = []

    if flags["explicit"] or flags["moan"] or flags["placeholder"]:
        score -= 60
        penalties.append("unsafe_or_broken_style")
    if flags["ai_leak"]:
        score -= 50
        penalties.append("ai_leak")
    if flags["listy"]:
        score -= 10
        penalties.append("too_mechanical")
    if len(reply.strip()) < 4:
        score -= 20
        penalties.append("too_short")
    if len(reply) > 180:
        score -= 10
        penalties.append("too_long")

    must_include_any = [
        str(item) for item in cast("list[object]", case.get("must_include_any", []))
    ]
    if must_include_any and not any(token in reply for token in must_include_any):
        score -= 15
        penalties.append("missed_required_signal")

    prefer_include_any = [
        str(item) for item in cast("list[object]", case.get("prefer_include_any", []))
    ]
    if prefer_include_any and not any(token in reply for token in prefer_include_any):
        score -= 5
        penalties.append("missed_preferred_signal")

    return {
        "score": max(score, 0),
        "penalties": penalties,
        "flags": flags,
    }


async def evaluate_live_replies(
    rag: RAGPipeline,
    llm: BaseLLMClient,
    *,
    top_k: int = 3,
) -> dict[str, Any]:
    sessions = InMemorySessionStore(max_history=6)
    case_details: list[dict[str, Any]] = []
    scores: list[int] = []

    for case in BENCHMARK_CASES:
        query = str(case["query"])
        result = await generate_chat_turn(
            query=query,
            session_id=None,
            top_k=top_k,
            rag=rag,
            llm=llm,
            sessions=sessions,
        )
        scoring = score_reply(result.reply, case)
        scores.append(int(scoring["score"]))
        case_details.append(
            {
                "id": case["id"],
                "query": query,
                "reply": result.reply,
                "score": scoring["score"],
                "penalties": scoring["penalties"],
                "reference_count": len(result.contexts),
            }
        )

    return {
        "case_count": len(BENCHMARK_CASES),
        "avg_score": round(mean(scores), 2) if scores else 0.0,
        "cases": case_details,
    }


def render_report(report: dict[str, Any]) -> str:
    lines = ["# Nene Quality Report", ""]

    current = report["current_dataset"]
    lines.extend(
        [
            "## Current Dataset",
            f"- Path: `{current['path']}`",
            f"- Samples: `{current['line_count']}`",
            f"- Unique pairs: `{current['unique_pair_count']}`",
            f"- Duplicate pairs: `{current['duplicate_pair_count']}`",
            f"- System prompt variants: `{current['system_prompt_variants']}`",
            f"- Explicit hits: `{current['explicit_hits']}`",
            f"- Moan hits: `{current['moan_hits']}`",
            f"- Placeholder hits: `{current['placeholder_hits']}`",
            f"- AI-leak hits: `{current['ai_leak_hits']}`",
            "",
        ]
    )

    baseline = report.get("baseline_dataset")
    if baseline is not None:
        delta = report["dataset_delta"]
        lines.extend(
            [
                "## Baseline Comparison",
                f"- Baseline path: `{baseline['path']}`",
                f"- Baseline samples: `{baseline['line_count']}`",
                f"- Sample delta: `{delta['line_count_delta']}`",
                f"- Explicit-hit delta: `{delta['explicit_hits_delta']}`",
                f"- Moan-hit delta: `{delta['moan_hits_delta']}`",
                f"- Placeholder-hit delta: `{delta['placeholder_hits_delta']}`",
                "",
            ]
        )

    retrieval = report["retrieval"]
    lines.extend(
        [
            "## Retrieval Benchmark",
            f"- Case count: `{retrieval['case_count']}`",
            f"- Non-empty retrieval rate: `{retrieval['nonempty_rate']}`",
            f"- Clean retrieval rate: `{retrieval['clean_rate']}`",
            f"- Average top1 similarity: `{retrieval['avg_top1_similarity']}`",
            f"- Average retrieval quality score: `{retrieval['avg_quality_score']}`",
            "",
        ]
    )

    live = report.get("live_replies")
    if live is not None:
        lines.extend(
            [
                "## Live Reply Benchmark",
                f"- Case count: `{live['case_count']}`",
                f"- Average score: `{live['avg_score']}`",
                "",
            ]
        )

    return "\n".join(lines)


def run_live_evaluation(rag: RAGPipeline, llm: BaseLLMClient, *, top_k: int = 3) -> dict[str, Any]:
    return asyncio.run(evaluate_live_replies(rag, llm, top_k=top_k))
