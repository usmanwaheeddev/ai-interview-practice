import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.base import Base
from app.db.models import (
    MockInterview,
    MockInterviewState,
    MockInterviewTurn,
    Resume,
)
from app.providers.llm.fake import FakeLLMProvider
from app.services.interview.plan import generate_interview_plan, generate_language_interview_plan


async def registered(client, email="practice@example.com"):
    r = await client.post(
        "/api/auth/register",
        json=dict(email=email, full_name="Practice User", password="password123"),
    )
    assert r.status_code == 201, r.text
    assert "role" not in r.json()
    return uuid.UUID(r.json()["id"])


async def resume_for(db, user_id):
    resume = Resume(
        user_id=user_id,
        storage_key=f"tests/{uuid.uuid4()}",
        filename="practice.pdf",
        mime_type="application/pdf",
        raw_text="Skills: Python. Experience: Built a payment service.",
        parsed={"experience": ["Built a payment service"]},
        parse_status="complete",
    )
    db.add(resume)
    await db.commit()
    return resume


def body(resume_id, duration=15):
    return dict(
        resume_id=str(resume_id),
        job_description="Backend role building reliable Python APIs and distributed services.",
        topics=["system_design", "programming"],
        duration_minutes=duration,
        video_enabled=False,
    )


def factory(db):
    @asynccontextmanager
    async def create():
        yield db

    return create


async def test_full_mock_lifecycle(client, db_session, fake_queue, monkeypatch):
    from app.workers import interview_jobs, scoring_jobs

    uid = await registered(client)
    resume = await resume_for(db_session, uid)
    r = await client.post("/api/mock-interviews", json=body(resume.id, 30))
    assert r.status_code == 201, r.text
    iid = r.json()["id"]
    assert r.json()["state"] == "preparing"
    assert fake_queue.enqueued[-1] == ("generate_mock_plan", (iid,))
    monkeypatch.setattr(interview_jobs, "async_session_factory", factory(db_session))
    await interview_jobs.generate_mock_plan({}, iid)
    ready = (await client.get(f"/api/mock-interviews/{iid}")).json()
    assert ready["state"] == "ready"
    assert ready["remaining_s"] == 1800
    assert (await client.post(f"/api/mock-interviews/{iid}/consent")).status_code == 200
    interview = await db_session.get(MockInterview, uuid.UUID(iid))
    interview.started_at = datetime.now(UTC)
    interview.state = MockInterviewState.SCORING
    for index, text in enumerate(
        [
            "I designed an idempotency key stored with the payment transaction.",
            "I used async Python for network IO and monitored error rates.",
        ]
    ):
        db_session.add(
            MockInterviewTurn(
                interview_id=interview.id,
                turn_index=index,
                speaker="user",
                text=text,
                started_at=datetime.now(UTC),
                ended_at=datetime.now(UTC),
            )
        )
    await db_session.commit()
    monkeypatch.setattr(scoring_jobs, "async_session_factory", factory(db_session))
    await scoring_jobs.score_mock_interview({}, iid)
    report = (await client.get(f"/api/mock-interviews/{iid}/report")).json()
    assert report["score_status"] == "complete", report
    assert Decimal(report["overall_score"]) == Decimal("3.00")
    assert len(report["dimensions"]) == 2
    assert len(report["transcript"]) == 2
    assert report["improvements"]
    assert all(d["evidence_verified"] for d in report["dimensions"])


async def test_owner_isolation(client_factory, db_session):
    first, second = await client_factory(), await client_factory()
    uid = await registered(first)
    resume = await resume_for(db_session, uid)
    iid = (await first.post("/api/mock-interviews", json=body(resume.id))).json()["id"]
    await registered(second, "other@example.com")
    assert (await second.post("/api/mock-interviews", json=body(resume.id))).status_code == 404
    for suffix in ("", "/report"):
        assert (await second.get(f"/api/mock-interviews/{iid}{suffix}")).status_code == 404
    for suffix in ("/consent", "/retry", "/rescore"):
        assert (await second.post(f"/api/mock-interviews/{iid}{suffix}")).status_code == 404
    assert (await second.get("/api/mock-interviews")).json() == []


async def test_only_new_schema_and_routes(client):
    assert set(Base.metadata.tables) == {
        "users",
        "resumes",
        "mock_interviews",
        "mock_interview_turns",
        "mock_media_assets",
        "mock_interview_scores",
    }
    assert set(Base.metadata.tables["users"].columns.keys()) == {
        "id",
        "created_at",
        "email",
        "full_name",
        "password_hash",
        "last_login_at",
    }
    for path in ("/api/jobs", "/api/applications", "/api/organizations", "/api/public/jobs"):
        assert (await client.get(path)).status_code == 404
    assert (await client.post("/api/auth/register/hr", json={})).status_code == 404


@pytest.mark.parametrize("duration", [0, 14, 31])
async def test_invalid_duration(client, db_session, duration):
    uid = await registered(client)
    resume = await resume_for(db_session, uid)
    assert (
        await client.post("/api/mock-interviews", json=body(resume.id, duration))
    ).status_code == 422


async def test_provider_failure_plan_fallback():
    class Unavailable:
        async def extract_json(self, **kwargs):
            raise RuntimeError("Rate limited")

    interview = MockInterview(
        job_description="Python backend", topics=["programming"], duration_minutes=30
    )
    resume = Resume(raw_text="Python", parsed={"experience": ["Built APIs"]})
    with pytest.raises(RuntimeError, match="did not generate a valid interview question"):
        await generate_interview_plan(interview=interview, resume=resume, llm=Unavailable())


async def test_language_interview_plan_fallback():
    class Unavailable:
        async def extract_json(self, **kwargs):
            raise RuntimeError("Rate limited")

    interview = MockInterview(language="python", level="advanced", duration_minutes=30)
    with pytest.raises(RuntimeError, match="did not generate a valid interview question"):
        await generate_language_interview_plan(interview=interview, llm=Unavailable())


async def test_language_interview_lifecycle(client, db_session, fake_queue, monkeypatch):
    from app.workers import interview_jobs

    await registered(client)
    r = await client.post(
        "/api/mock-interviews",
        json=dict(language="java", level="basic", duration_minutes=15, video_enabled=False),
    )
    assert r.status_code == 201, r.text
    assert r.json()["resume_id"] is None
    assert r.json()["language"] == "java"
    assert r.json()["spoken_language"] == "en"
    iid = r.json()["id"]
    monkeypatch.setattr(interview_jobs, "async_session_factory", factory(db_session))
    await interview_jobs.generate_mock_plan({}, iid)
    ready = (await client.get(f"/api/mock-interviews/{iid}")).json()
    assert ready["state"] == "ready"


@pytest.mark.parametrize("spoken_language", ["hi", "ur"])
async def test_spoken_language_is_not_client_settable(
    client, db_session, fake_queue, spoken_language
):
    """The conversation's spoken language is auto-detected from the
    candidate's own speech (see app/ws/interview.py), never chosen at
    creation — a client-supplied `spoken_language` is silently ignored and
    every interview starts in English."""
    await registered(client)
    r = await client.post(
        "/api/mock-interviews",
        json=dict(
            language="python",
            level="basic",
            spoken_language=spoken_language,
            duration_minutes=15,
            video_enabled=False,
        ),
    )
    assert r.status_code == 201, r.text
    assert r.json()["spoken_language"] == "en"


async def test_language_practice_rejects_missing_llm_question() -> None:
    class Unavailable:
        async def extract_json(self, **kwargs):
            raise RuntimeError("Rate limited")

    interview = MockInterview(language="python", level="basic", duration_minutes=15)
    with pytest.raises(RuntimeError, match="did not generate a valid interview question"):
        await generate_language_interview_plan(
            interview=interview, llm=Unavailable(), spoken_language="hi"
        )


async def test_both_modes_rejected(client, db_session):
    uid = await registered(client)
    resume = await resume_for(db_session, uid)
    payload = {**body(resume.id), "language": "python", "level": "basic"}
    assert (await client.post("/api/mock-interviews", json=payload)).status_code == 422


async def test_neither_mode_rejected(client):
    await registered(client)
    payload = dict(duration_minutes=15, video_enabled=False)
    assert (await client.post("/api/mock-interviews", json=payload)).status_code == 422


async def test_resume_interview_allows_missing_job_description(client, db_session):
    uid = await registered(client, "resume-only@example.com")
    resume = await resume_for(db_session, uid)
    payload = {
        "resume_id": str(resume.id),
        "topics": ["programming"],
        "duration_minutes": 15,
        "video_enabled": False,
    }
    response = await client.post("/api/mock-interviews", json=payload)
    assert response.status_code == 201, response.text


async def test_failed_scoring_is_visible_and_retryable(client, db_session, monkeypatch):
    from app.workers import scoring_jobs

    uid = await registered(client)
    resume = await resume_for(db_session, uid)
    interview = MockInterview(
        user_id=uid,
        resume_id=resume.id,
        job_description="Backend",
        topics=["programming"],
        duration_minutes=15,
        state=MockInterviewState.SCORING,
    )
    interview.interview_plan = (
        await generate_interview_plan(interview=interview, resume=resume, llm=FakeLLMProvider())
    ).model_dump(mode="json")
    db_session.add(interview)
    await db_session.commit()
    monkeypatch.setattr(scoring_jobs, "async_session_factory", factory(db_session))
    await scoring_jobs.score_mock_interview({}, str(interview.id))
    result = (await client.get(f"/api/mock-interviews/{interview.id}/report")).json()
    assert result["score_status"] == "failed"
    assert result["overall_score"] is None
    assert "No spoken answers" in result["failure_reason"]
    assert (await client.post(f"/api/mock-interviews/{interview.id}/rescore")).status_code == 202


async def test_erasure_removes_owned_interviews(client, db_session):
    uid = await registered(client)
    resume = await resume_for(db_session, uid)
    await client.post("/api/mock-interviews", json=body(resume.id))
    exported = (await client.get("/api/me/data-export")).json()
    assert len(exported["interviews"]) == 1
    assert (await client.post("/api/me/erase")).status_code == 204
    assert (await client.get("/api/auth/me")).status_code == 401
    assert list(await db_session.scalars(select(MockInterview))) == []


async def test_queue_outage_does_not_leave_infinite_preparation(
    client, db_session, fake_queue, monkeypatch
):
    async def unavailable(*args, **kwargs):
        raise ConnectionError("Queue unavailable")

    uid = await registered(client)
    resume = await resume_for(db_session, uid)
    monkeypatch.setattr(fake_queue, "enqueue_job", unavailable)
    result = await client.post("/api/mock-interviews", json=body(resume.id))
    assert result.status_code == 201
    assert result.json()["state"] == "failed"
    retry = await client.post(f"/api/mock-interviews/{result.json()['id']}/retry")
    assert retry.json()["state"] == "failed"
    assert retry.json()["failure_reason"]


@pytest.mark.parametrize("video_enabled,kind", [(False, "audio"), (True, "video")])
async def test_recordings_require_consent_and_match_mode(client, db_session, video_enabled, kind):
    uid = await registered(client)
    resume = await resume_for(db_session, uid)
    request = body(resume.id, 30)
    request["video_enabled"] = video_enabled
    iid = (await client.post("/api/mock-interviews", json=request)).json()["id"]
    path = f"/api/mock-interviews/{iid}"
    media = dict(kind=kind, chunk_index=0, content_type=f"{kind}/webm")
    assert (await client.post(path + "/media", json=media)).status_code == 409
    interview = await db_session.get(MockInterview, uuid.UUID(iid))
    interview.started_at = interview.consent_at = datetime.now(UTC)
    interview.state = MockInterviewState.IN_PROGRESS
    await db_session.commit()
    wrong_kind = "audio" if video_enabled else "video"
    invalid = dict(media, kind=wrong_kind, content_type=f"{wrong_kind}/webm")
    assert (await client.post(path + "/media", json=invalid)).status_code == 422
    assert (await client.post(path + "/media", json=media)).status_code == 200
    assert (await client.get(path + "/report")).json()["recordings"] == []
    assert (
        await client.post(path + "/media/complete", json={"chunk_indices": [0]})
    ).status_code == 204
    recordings = (await client.get(path + "/report")).json()["recordings"]
    assert len(recordings) == 1
    assert recordings[0]["kind"] == kind
