import backend.services.mastery_policy as policy_module
from backend.services.mastery_policy import MasteryPolicy


def event(
    outcome,
    stage,
    *,
    applied=1,
    assistance="untracked",
):
    return {
        "outcome": outcome,
        "stage_before": stage,
        "applied": applied,
        "assistance_level": assistance,
    }


def evaluate(monkeypatch, existing, **overrides):
    monkeypatch.setattr(
        policy_module.EvidenceEvent,
        "list_for_concept",
        lambda *args, **kwargs: existing,
    )
    params = {
        "area": "ads",
        "concept": "ads.variables",
        "stage_before": "fixar",
        "semantic_evidence": {
            "outcome": "demonstrated",
            "confidence": 0.95,
        },
        "mastery_score": 0.8,
        "current_applied": True,
        "student_id": "student_default",
        "assistance_level": "independent",
    }
    params.update(overrides)
    return MasteryPolicy.evaluate(**params)


def test_completion_requires_portfolio_not_only_score(monkeypatch):
    decision = evaluate(
        monkeypatch,
        [event("demonstrated", "fixar")],
        mastery_score=0.95,
    )

    assert decision["can_complete"] is False
    assert MasteryPolicy.BLOCK_EVIDENCE_COUNT in decision["blockers"]
    assert MasteryPolicy.BLOCK_STAGE_DIVERSITY in decision["blockers"]


def test_varied_evidence_portfolio_can_complete(monkeypatch):
    decision = evaluate(
        monkeypatch,
        [
            event("demonstrated", "compreender"),
            event("partial", "testar"),
        ],
    )

    assert decision["can_complete"] is True
    assert decision["score"] == 0.8
    assert decision["applied_evidence_count"] == 3
    assert decision["demonstrated_count"] == 2
    assert decision["demonstrated_stage_count"] == 2
    assert decision["blockers"] == []


def test_current_evidence_must_be_applied_and_demonstrated(monkeypatch):
    decision = evaluate(
        monkeypatch,
        [
            event("demonstrated", "compreender"),
            event("demonstrated", "fixar"),
            event("partial", "testar"),
        ],
        current_applied=False,
    )

    assert decision["can_complete"] is False
    assert MasteryPolicy.BLOCK_CURRENT_NOT_APPLIED in decision["blockers"]

    partial = evaluate(
        monkeypatch,
        [
            event("demonstrated", "compreender"),
            event("demonstrated", "fixar"),
        ],
        semantic_evidence={"outcome": "partial", "confidence": 0.95},
    )

    assert partial["can_complete"] is False
    assert MasteryPolicy.BLOCK_LATEST_OUTCOME in partial["blockers"]


def test_tracked_assistance_requires_low_assistance_demonstration(monkeypatch):
    blocked = evaluate(
        monkeypatch,
        [
            event("demonstrated", "compreender", assistance="direct"),
            event("partial", "testar", assistance="guided"),
        ],
        assistance_level="direct",
    )

    assert blocked["can_complete"] is False
    assert MasteryPolicy.BLOCK_ASSISTANCE in blocked["blockers"]

    allowed = evaluate(
        monkeypatch,
        [
            event("demonstrated", "compreender", assistance="direct"),
            event("partial", "testar", assistance="guided"),
        ],
        assistance_level="light",
    )

    assert allowed["can_complete"] is True
    assert allowed["low_assistance_demonstrated_count"] == 1


def test_current_assistance_must_be_low_and_recommends_independent_recheck(monkeypatch):
    decision = evaluate(
        monkeypatch,
        [
            event("demonstrated", "compreender", assistance="guided"),
            event("partial", "testar", assistance="direct"),
        ],
        assistance_level="untracked",
    )

    assert decision["can_complete"] is False
    assert MasteryPolicy.BLOCK_ASSISTANCE in decision["blockers"]
    assert MasteryPolicy.BLOCK_CURRENT_ASSISTANCE in decision["blockers"]
    assert decision["recommended_stage"] == "testar"


def test_retention_demonstration_is_visible_in_decision(monkeypatch):
    decision = evaluate(
        monkeypatch,
        [
            event("demonstrated", "compreender"),
            event("demonstrated", "reencontrar"),
        ],
    )

    assert decision["retention_demonstrated_count"] == 1


def test_missing_stage_diversity_recommends_testing(monkeypatch):
    decision = evaluate(
        monkeypatch,
        [
            event("demonstrated", "fixar"),
            event("demonstrated", "fixar"),
        ],
        mastery_score=0.9,
    )

    assert decision["can_complete"] is False
    assert MasteryPolicy.BLOCK_STAGE_DIVERSITY in decision["blockers"]
    assert decision["recommended_stage"] == "testar"


def controlled_event(outcome, stage, prompt, *, assistance="independent"):
    return {
        "outcome": outcome,
        "stage_before": stage,
        "applied": 1,
        "assistance_level": assistance,
        "concept_id": "ads.algorithms.goal_result",
        "tutor_message": prompt,
    }


def test_controlled_mastery_blocks_repeated_same_activity_context(monkeypatch):
    from backend.services.goal_result_tasks import GoalResultTasks

    backpack = GoalResultTasks.prompt_for_mastery(0.75)
    existing = [
        controlled_event("demonstrated", "compreender", backpack),
        controlled_event("demonstrated", "testar", backpack),
    ]
    decision = evaluate(
        monkeypatch,
        existing,
        concept="ads.algorithms.goal_result",
        stage_before="fixar",
        mastery_score=0.8,
        current_context_id="goal_backpack_organized",
    )

    assert decision["can_complete"] is False
    assert decision["demonstrated_context_count"] == 1
    assert MasteryPolicy.BLOCK_CONTEXT_DIVERSITY in decision["blockers"]


def test_controlled_mastery_accepts_two_real_task_contexts(monkeypatch):
    from backend.services.goal_result_tasks import GoalResultTasks

    document = GoalResultTasks.prompt_for_mastery(0.25)
    dishes = GoalResultTasks.prompt_for_mastery(0.45)
    existing = [
        controlled_event("demonstrated", "compreender", document),
        controlled_event("demonstrated", "testar", dishes),
    ]
    decision = evaluate(
        monkeypatch,
        existing,
        concept="ads.algorithms.goal_result",
        stage_before="fixar",
        mastery_score=0.8,
        current_context_id="goal_backpack_organized",
    )

    assert decision["can_complete"] is True
    assert decision["demonstrated_context_count"] == 3
    assert MasteryPolicy.BLOCK_CONTEXT_DIVERSITY not in decision["blockers"]
