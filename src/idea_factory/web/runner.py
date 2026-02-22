"""Web-adapted loop runner — emits events via queue instead of Rich display."""

from __future__ import annotations

import logging
import queue
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum

from idea_factory.agents.builder import BuilderAgent
from idea_factory.agents.challenger import ChallengerAgent
from idea_factory.agents.claude_check import ClaudeCheckAgent
from idea_factory.agents.consumer import ConsumerAgent
from idea_factory.agents.creator import CreatorAgent
from idea_factory.agents.distributor import DistributorAgent
from idea_factory.agents.judge import JudgeAgent
from idea_factory.config import Settings
from idea_factory.db import repository as repo
from idea_factory.db.connection import get_db
from idea_factory.llm.factory import get_provider
from idea_factory.preferences import (
    build_taste_prefix,
    load_preferences,
    save_preferences,
    update_preferences,
)
from idea_factory.prompts import challenger_reflection_prompt, judge_reflection_prompt
from idea_factory.reflexion import run_with_reflexion

logger = logging.getLogger("idea_factory.web.runner")


class EventType(str, Enum):
    LOOP_STARTED = "loop_started"
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    IDEA_CREATED = "idea_created"
    IDEA_KILLED = "idea_killed"
    IDEA_SURVIVED = "idea_survived"
    FEEDBACK_NEEDED = "feedback_needed"
    RUN_COMPLETED = "run_completed"
    RUN_ERROR = "run_error"
    LOG = "log"


@dataclass
class RunState:
    """Holds all state for a single web-initiated run."""

    run_id: str
    region: str
    domains: list[str]
    constraints: str
    claude_check: bool
    status: str = "pending"
    loop_num: int = 0
    total_ideas: int = 0
    total_winners: int = 0
    events: queue.Queue = field(default_factory=queue.Queue)
    _stop: threading.Event = field(default_factory=threading.Event)
    _feedback_event: threading.Event = field(default_factory=threading.Event)
    _feedback_data: dict | None = None

    def emit(self, event_type: EventType, data: dict | None = None) -> None:
        self.events.put({"event": event_type.value, "data": data or {}})

    def submit_feedback(self, feedback: dict) -> None:
        self._feedback_data = feedback
        self._feedback_event.set()

    def wait_for_feedback(self, timeout: float = 600) -> dict | None:
        self._feedback_event.wait(timeout=timeout)
        self._feedback_event.clear()
        data = self._feedback_data
        self._feedback_data = None
        return data

    def should_stop(self) -> bool:
        return self._stop.is_set()

    def request_stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        """Execute the idea generation loop (call from a background thread)."""
        self.status = "running"
        self.emit(EventType.LOG, {"message": "Run starting..."})

        from idea_factory.web.deps import get_settings

        settings = get_settings()
        conn = get_db(settings.db_path)

        try:
            self._run_loop(settings, conn)
        except Exception as exc:
            logger.exception("Run error")
            self.status = "error"
            self.emit(EventType.RUN_ERROR, {"error": str(exc)})
        finally:
            conn.close()

    def _track_usage(self, conn, agent, idea_id, settings):
        usage = agent.last_usage
        if usage:
            repo.save_token_usage(
                conn,
                idea_id=idea_id,
                agent_name=agent.name,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                provider=settings.llm_provider,
                model=settings.model,
            )

    def _run_loop(self, settings: Settings, conn) -> None:
        top_k = settings.top_k
        max_winners = settings.max_winners

        provider = get_provider(settings)

        creator = CreatorAgent(provider)
        challenger = ChallengerAgent(provider)
        builder = BuilderAgent(provider)
        distributor = DistributorAgent(provider)
        consumer = ConsumerAgent(provider)
        judge = JudgeAgent(provider)
        claude_check_agent = ClaudeCheckAgent(provider) if self.claude_check else None

        prefs = load_preferences(conn)
        session_id = repo.save_session(conn, self.region, self.domains, self.constraints)
        recent_rejections: list[str] = []

        while not self.should_stop():
            self.loop_num += 1
            self.emit(EventType.LOOP_STARTED, {"loop_num": self.loop_num})

            # ----- CREATOR -----
            taste_prefix = build_taste_prefix(prefs)
            self.emit(EventType.AGENT_STARTED, {"agent": "creator"})
            creator_out = creator.run(
                {
                    "region": self.region,
                    "domains": self.domains,
                    "constraints": self.constraints,
                    "taste_prefix": taste_prefix,
                    "recent_rejections": recent_rejections,
                }
            )
            ideas = creator_out.ideas  # type: ignore[attr-defined]
            self._track_usage(conn, creator, None, settings)
            self.emit(
                EventType.AGENT_COMPLETED,
                {"agent": "creator", "count": len(ideas)},
            )

            idea_records: list[dict] = []
            for idea in ideas:
                idea_dict = idea.model_dump()
                idea_id = repo.save_idea(conn, idea_dict)
                idea_dict["id"] = idea_id
                idea_records.append(idea_dict)
                self.total_ideas += 1
                self.emit(
                    EventType.IDEA_CREATED,
                    {
                        "id": idea_id,
                        "name": idea_dict["name"],
                        "one_liner": idea_dict.get("one_liner", ""),
                    },
                )

            if self.should_stop():
                break

            # ----- CHALLENGER -----
            survivors: list[tuple[dict, dict]] = []
            for idea_dict in idea_records:
                self.emit(
                    EventType.AGENT_STARTED,
                    {
                        "agent": "challenger",
                        "idea": idea_dict["name"],
                    },
                )
                ch_out = run_with_reflexion(
                    agent=challenger,
                    context={"idea": idea_dict},
                    reflection_prompt_fn=lambda ctx, out: challenger_reflection_prompt(
                        idea=ctx["idea"],
                        challenger_output=out,
                    ),
                    max_rounds=settings.reflexion_max_rounds,
                )
                ch_dict = ch_out.model_dump()
                repo.save_agent_output(conn, idea_dict["id"], "challenger", ch_dict)
                self._track_usage(conn, challenger, idea_dict["id"], settings)

                if ch_dict["verdict"] == "SURVIVE":
                    survivors.append((idea_dict, ch_dict))
                    self.emit(
                        EventType.IDEA_SURVIVED,
                        {
                            "id": idea_dict["id"],
                            "name": idea_dict["name"],
                        },
                    )
                    self.emit(
                        EventType.AGENT_COMPLETED,
                        {
                            "agent": "challenger",
                            "idea": idea_dict["name"],
                            "verdict": "SURVIVE",
                        },
                    )
                else:
                    repo.update_idea_status(conn, idea_dict["id"], "killed")
                    recent_rejections.append(idea_dict["name"])
                    self.emit(
                        EventType.IDEA_KILLED,
                        {
                            "id": idea_dict["id"],
                            "name": idea_dict["name"],
                        },
                    )
                    self.emit(
                        EventType.AGENT_COMPLETED,
                        {
                            "agent": "challenger",
                            "idea": idea_dict["name"],
                            "verdict": "KILL",
                        },
                    )

                if self.should_stop():
                    break

            if self.should_stop():
                break

            if not survivors:
                self.emit(
                    EventType.LOG,
                    {
                        "message": "No survivors this round. Generating new batch...",
                    },
                )
                continue

            top_survivors = survivors[:top_k]

            # ----- FULL PIPELINE -----
            finalists: list[tuple[dict, dict]] = []
            for idea_dict, ch_dict in top_survivors:
                if self.should_stop():
                    break

                # Builder
                self.emit(
                    EventType.AGENT_STARTED,
                    {
                        "agent": "builder",
                        "idea": idea_dict["name"],
                    },
                )
                b_out = builder.run({"idea": idea_dict})
                b_dict = b_out.model_dump()
                repo.save_agent_output(conn, idea_dict["id"], "builder", b_dict)
                self._track_usage(conn, builder, idea_dict["id"], settings)
                self.emit(
                    EventType.AGENT_COMPLETED,
                    {
                        "agent": "builder",
                        "idea": idea_dict["name"],
                        "buildable": b_dict.get("buildable", True),
                    },
                )

                if not b_dict.get("buildable", True):
                    repo.update_idea_status(conn, idea_dict["id"], "unbuildable")
                    continue

                # Distributor
                self.emit(
                    EventType.AGENT_STARTED,
                    {
                        "agent": "distributor",
                        "idea": idea_dict["name"],
                    },
                )
                d_out = distributor.run(
                    {
                        "idea": idea_dict,
                        "build_output": b_dict,
                    }
                )
                d_dict = d_out.model_dump()
                repo.save_agent_output(conn, idea_dict["id"], "distributor", d_dict)
                self._track_usage(conn, distributor, idea_dict["id"], settings)
                self.emit(
                    EventType.AGENT_COMPLETED,
                    {
                        "agent": "distributor",
                        "idea": idea_dict["name"],
                    },
                )

                # Consumer
                self.emit(
                    EventType.AGENT_STARTED,
                    {
                        "agent": "consumer",
                        "idea": idea_dict["name"],
                    },
                )
                c_out = consumer.run(
                    {
                        "idea": idea_dict,
                        "build_output": b_dict,
                        "dist_output": d_dict,
                    }
                )
                c_dict = c_out.model_dump()
                repo.save_agent_output(conn, idea_dict["id"], "consumer", c_dict)
                self._track_usage(conn, consumer, idea_dict["id"], settings)
                self.emit(
                    EventType.AGENT_COMPLETED,
                    {
                        "agent": "consumer",
                        "idea": idea_dict["name"],
                    },
                )

                # Judge
                self.emit(
                    EventType.AGENT_STARTED,
                    {
                        "agent": "judge",
                        "idea": idea_dict["name"],
                    },
                )
                j_out = run_with_reflexion(
                    agent=judge,
                    context={
                        "idea": idea_dict,
                        "challenger_out": ch_dict,
                        "builder_out": b_dict,
                        "dist_out": d_dict,
                        "consumer_out": c_dict,
                    },
                    reflection_prompt_fn=lambda ctx, out: judge_reflection_prompt(
                        idea=ctx["idea"],
                        judge_output=out,
                    ),
                    max_rounds=settings.reflexion_max_rounds,
                )
                j_dict = j_out.model_dump()
                repo.save_agent_output(conn, idea_dict["id"], "judge", j_dict)
                self._track_usage(conn, judge, idea_dict["id"], settings)

                verdict = j_dict.get("verdict", "PASS").lower()
                repo.update_idea_status(
                    conn, idea_dict["id"], verdict, j_dict.get("composite_score")
                )
                self.emit(
                    EventType.AGENT_COMPLETED,
                    {
                        "agent": "judge",
                        "idea": idea_dict["name"],
                        "verdict": j_dict.get("verdict", "PASS"),
                        "composite_score": j_dict.get("composite_score", 0),
                        "idea_id": idea_dict["id"],
                    },
                )

                finalists.append((idea_dict, j_dict))

                # Claude Check (optional)
                if claude_check_agent:
                    self.emit(
                        EventType.AGENT_STARTED,
                        {
                            "agent": "claude_check",
                            "idea": idea_dict["name"],
                        },
                    )
                    cc_out = claude_check_agent.run(
                        {
                            "idea": idea_dict,
                            "judge_output": j_dict,
                            "builder_output": b_dict,
                        }
                    )
                    cc_dict = cc_out.model_dump()
                    repo.save_agent_output(conn, idea_dict["id"], "claude_check", cc_dict)
                    self._track_usage(conn, claude_check_agent, idea_dict["id"], settings)
                    self.emit(
                        EventType.AGENT_COMPLETED,
                        {
                            "agent": "claude_check",
                            "idea": idea_dict["name"],
                            "verdict": cc_dict.get("verdict", ""),
                        },
                    )

            if self.should_stop():
                break

            # ----- FEEDBACK -----
            if not finalists:
                self.emit(
                    EventType.LOG,
                    {
                        "message": "No finalists this round.",
                    },
                )
                repo.update_session_progress(conn, session_id, self.loop_num, self.total_winners)
                continue

            for idea_dict, j_dict in finalists:
                if self.should_stop():
                    break

                self.emit(
                    EventType.FEEDBACK_NEEDED,
                    {
                        "idea_id": idea_dict["id"],
                        "name": idea_dict["name"],
                        "one_liner": idea_dict.get("one_liner", ""),
                        "verdict": j_dict.get("verdict", "PASS"),
                        "composite_score": j_dict.get("composite_score", 0),
                    },
                )

                fb = self.wait_for_feedback()
                if fb is None or self.should_stop():
                    break

                repo.save_feedback(conn, idea_dict["id"], fb)
                prefs = update_preferences(prefs, fb, idea_dict, j_dict)
                save_preferences(conn, prefs)

                if fb["decision"] == "love" and j_dict.get("verdict") == "WINNER":
                    self.total_winners += 1

            repo.update_session_progress(conn, session_id, self.loop_num, self.total_winners)

            if self.total_winners >= max_winners:
                self.emit(
                    EventType.LOG,
                    {
                        "message": f"Reached {max_winners} winners! Wrapping up.",
                    },
                )
                break

        self.status = "completed"
        self.emit(
            EventType.RUN_COMPLETED,
            {
                "loop_num": self.loop_num,
                "total_ideas": self.total_ideas,
                "total_winners": self.total_winners,
            },
        )


# ---------------------------------------------------------------------------
# In-memory run registry (single-user tool)
# ---------------------------------------------------------------------------

_runs: dict[str, RunState] = {}
_lock = threading.Lock()


def create_run(
    region: str,
    domains: list[str],
    constraints: str,
    claude_check: bool = False,
) -> RunState:
    """Create a new RunState and register it."""
    run_id = uuid.uuid4().hex[:12]
    state = RunState(
        run_id=run_id,
        region=region,
        domains=domains,
        constraints=constraints,
        claude_check=claude_check,
    )
    with _lock:
        _runs[run_id] = state
    return state


def get_run_state(run_id: str) -> RunState | None:
    with _lock:
        return _runs.get(run_id)


def stop_run(run_id: str) -> None:
    state = get_run_state(run_id)
    if state:
        state.request_stop()
