"""Exercise the running API and real speech providers using synthetic data."""

import asyncio
import io
import json
import uuid

import httpx
import websockets
from docx import Document

from app.providers.tts import get_tts_provider
from app.services.audio import wav_bytes_to_pcm16


async def main() -> None:
    email = f"smoke-{uuid.uuid4().hex[:10]}@example.com"
    async with httpx.AsyncClient(base_url="http://localhost:8000/api", timeout=60) as client:
        result = await client.post(
            "/auth/register",
            json={
                "full_name": "Synthetic Practice User",
                "email": email,
                "password": "Smoke-test-password-123",
            },
        )
        result.raise_for_status()
        # Local container HTTP does not send Secure cookies automatically.
        cookie = f"access_token={client.cookies['access_token']}"
        client.headers["Cookie"] = cookie
        doc = Document()
        doc.add_paragraph(
            "Synthetic Practice User. Python backend engineer with five years "
            "building PostgreSQL services, Redis caches and distributed APIs. "
            "Designed reliable order processing with idempotency keys and queues."
        )
        output = io.BytesIO()
        doc.save(output)
        result = await client.post(
            "/resumes",
            files={
                "file": (
                    "synthetic-resume.docx",
                    output.getvalue(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        result.raise_for_status()
        result = await client.post(
            "/mock-interviews",
            json={
                "resume_id": result.json()["id"],
                "duration_minutes": 15,
                "video_enabled": False,
                "topics": ["system_design", "programming"],
                "job_description": "Python backend engineer building reliable distributed order "
                "processing APIs with PostgreSQL, Redis, queues and monitoring.",
            },
        )
        result.raise_for_status()
        interview_id = result.json()["id"]
        print(f"Account: {email}; interview: {interview_id}", flush=True)
        path = f"/mock-interviews/{interview_id}"
        for _ in range(90):
            result = await client.get(path)
            result.raise_for_status()
            state = result.json()["state"]
            if state == "ready":
                break
            if state == "failed":
                raise RuntimeError(result.json())
            await asyncio.sleep(2)
        else:
            raise TimeoutError("Plan did not become ready")
        result = await client.post(path + "/consent")
        result.raise_for_status()
        answers = [
            "I designed an order processing API in Python. We used a PostgreSQL transaction "
            "to store each order with a unique idempotency key. A durable queue handled "
            "fulfillment asynchronously. We monitored queue age and tested retry failures.",
            "I would first clarify throughput and consistency requirements. I would keep "
            "the database as the source of truth and cache reads in Redis with short expiry. "
            "I would measure latency before adding complexity or splitting services.",
            "For Python I use type hints and small functions with explicit error handling. "
            "I test duplicate requests, database failures, and concurrency. For blocking "
            "work I use a worker queue instead of blocking the async event loop.",
        ]
        tts = get_tts_provider()
        audio = [wav_bytes_to_pcm16(await tts.synthesize(answer)) for answer in answers]
        async with websockets.connect(
            f"ws://localhost:8000/ws/mock-interviews/{interview_id}",
            additional_headers={"Cookie": cookie},
            max_size=10_000_000,
        ) as ws:
            await ws.send(json.dumps({"type": "session.start", "sample_rate": 16000}))
            sent = transcripts = audio_packets = 0
            while True:
                message = await asyncio.wait_for(ws.recv(), timeout=90)
                if isinstance(message, bytes):
                    audio_packets += 1
                    continue
                event = json.loads(message)
                if event["type"] == "error":
                    raise RuntimeError(event)
                if event["type"] == "transcript.final":
                    transcripts += 1
                    print("Transcribed:", event["text"], flush=True)
                if event["type"] == "agent.speaking_end":
                    if sent == len(audio):
                        await ws.send(json.dumps({"type": "session.end"}))
                    else:
                        pcm = audio[sent] + bytes(64000)
                        for offset in range(0, len(pcm), 8000):
                            await ws.send(pcm[offset : offset + 8000])
                        sent += 1
                if event["type"] == "session.complete":
                    break
            assert transcripts >= 3 and audio_packets >= 4
        for _ in range(90):
            result = await client.get(path + "/report")
            result.raise_for_status()
            report = result.json()
            if report["score_status"] in ("complete", "needs_review", "failed"):
                print(
                    json.dumps(
                        {
                            "score_status": report["score_status"],
                            "overall_score": report["overall_score"],
                            "failure_reason": report.get("failure_reason"),
                            "transcript_turns": len(report["transcript"]),
                        }
                    ),
                    flush=True,
                )
                assert report["score_status"] != "failed", "Live scoring provider failed"
                return
            await asyncio.sleep(2)
        raise TimeoutError("Report did not finish")


if __name__ == "__main__":
    asyncio.run(main())
