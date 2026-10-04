from __future__ import annotations

"""Module 4: RAGAS Evaluation — 4 metrics + failure analysis."""

import os, sys, json, math
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, TEST_SET_PATH


@dataclass
class EvalResult:
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float


def load_test_set(path: str = TEST_SET_PATH) -> list[dict]:
    """Load test set from JSON. (Đã implement sẵn)"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate_ragas(questions: list[str], answers: list[str],
                   contexts: list[list[str]], ground_truths: list[str]) -> dict:
    """Run RAGAS evaluation."""
    metric_names = (
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
    )
    zeros = {name: 0.0 for name in metric_names}
    zeros["per_question"] = []

    lengths = {len(questions), len(answers), len(contexts), len(ground_truths)}
    if len(lengths) != 1:
        raise ValueError("questions, answers, contexts and ground_truths must have equal length")
    if not questions:
        return zeros

    zero_per_question = [
        EvalResult(
            question=question,
            answer=answer,
            contexts=context,
            ground_truth=ground_truth,
            faithfulness=0.0,
            answer_relevancy=0.0,
            context_precision=0.0,
            context_recall=0.0,
        )
        for question, answer, context, ground_truth in zip(
            questions, answers, contexts, ground_truths
        )
    ]
    zero_results = {**zeros, "per_question": zero_per_question}
    if not OPENAI_API_KEY:
        print("  ⚠️  RAGAS evaluation skipped: OPENAI_API_KEY is not configured")
        return zero_results

    def safe_score(value) -> float:
        try:
            score = float(value)
            return 0.0 if math.isnan(score) else score
        except (TypeError, ValueError):
            return 0.0

    try:
        from datasets import Dataset
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from langchain_openai import ChatOpenAI
        from ragas import evaluate
        from ragas.run_config import RunConfig
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )

        dataset = Dataset.from_dict({
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": ground_truths,
        })
        llm_kwargs = {
            "api_key": OPENAI_API_KEY,
            "model": OPENAI_MODEL,
            "temperature": 0,
        }
        if OPENAI_BASE_URL:
            llm_kwargs["base_url"] = OPENAI_BASE_URL

        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=ChatOpenAI(**llm_kwargs),
            embeddings=HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                encode_kwargs={"normalize_embeddings": True},
            ),
            run_config=RunConfig(
                timeout=180,
                max_retries=3,
                max_wait=30,
                max_workers=max(1, int(os.getenv("RAGAS_MAX_WORKERS", "4"))),
            ),
        )
        frame = result.to_pandas()
        per_question = [
            EvalResult(
                question=str(row["question"]),
                answer=str(row["answer"]),
                contexts=list(row["contexts"]),
                ground_truth=str(row["ground_truth"]),
                faithfulness=safe_score(row.get("faithfulness")),
                answer_relevancy=safe_score(row.get("answer_relevancy")),
                context_precision=safe_score(row.get("context_precision")),
                context_recall=safe_score(row.get("context_recall")),
            )
            for _, row in frame.iterrows()
        ]
        aggregates = {
            name: (
                sum(getattr(item, name) for item in per_question) / len(per_question)
                if per_question else 0.0
            )
            for name in metric_names
        }
        return {**aggregates, "per_question": per_question}
    except Exception as error:
        print(f"  ⚠️  RAGAS evaluation failed: {error}")
        return zero_results


def failure_analysis(eval_results: list[EvalResult], bottom_n: int = 10) -> list[dict]:
    """Analyze bottom-N worst questions using Diagnostic Tree."""
    if bottom_n <= 0:
        return []
    diagnostic_tree = {
        "faithfulness": (
            "Câu trả lời có chi tiết không được hỗ trợ bởi ngữ cảnh.",
            "Siết system prompt, chỉ cho phép dùng context và đặt temperature=0.",
        ),
        "context_recall": (
            "Retriever bỏ sót đoạn chứa đủ thông tin cần thiết.",
            "Điều chỉnh chunking hoặc tăng tín hiệu từ khóa của BM25.",
        ),
        "context_precision": (
            "Các đoạn ít liên quan đang đứng quá cao trong kết quả tìm kiếm.",
            "Cải thiện cross-encoder reranking hoặc lọc theo metadata.",
        ),
        "answer_relevancy": (
            "Câu trả lời chưa đi thẳng vào trọng tâm câu hỏi.",
            "Viết lại prompt để yêu cầu trả lời trực tiếp và ngắn gọn.",
        ),
    }
    analyzed = []
    for item in eval_results:
        scores = {
            "faithfulness": item.faithfulness,
            "answer_relevancy": item.answer_relevancy,
            "context_precision": item.context_precision,
            "context_recall": item.context_recall,
        }
        worst_metric = min(scores, key=scores.get)
        diagnosis, suggested_fix = diagnostic_tree[worst_metric]
        analyzed.append({
            "question": item.question,
            "answer": item.answer,
            "contexts": item.contexts,
            "ground_truth": item.ground_truth,
            "average_score": sum(scores.values()) / len(scores),
            "worst_metric": worst_metric,
            "score": scores[worst_metric],
            "diagnosis": diagnosis,
            "suggested_fix": suggested_fix,
        })
    analyzed.sort(key=lambda item: item["average_score"])
    return analyzed[:bottom_n]


def save_report(results: dict, failures: list[dict], path: str = "reports/ragas_report.json"):
    """Save evaluation report to JSON. (Đã implement sẵn)"""
    parent_dir = os.path.dirname(path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    report = {
        "aggregate": {k: v for k, v in results.items() if k != "per_question"},
        "num_questions": len(results.get("per_question", [])),
        "failures": failures,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report saved to {path}")


if __name__ == "__main__":
    test_set = load_test_set()
    print(f"Loaded {len(test_set)} test questions")
    print("Run pipeline.py first to generate answers, then call evaluate_ragas().")
