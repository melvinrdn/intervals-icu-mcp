"""Hevy strength-training tools (fork-specific — not part of upstream intervals-icu-mcp).

Hevy is a separate service from Intervals.icu with its own API key
(``HEVY_API_KEY``). These tools are read-only and namespaced ``hevy_*`` to
keep them clearly distinct from the ``icu_*`` Intervals.icu tool surface.
"""

from typing import Annotated, Any

from fastmcp import Context

from ..auth import ICUConfig
from ..hevy_client import HevyAPIError, HevyClient
from ..response_builder import ResponseBuilder


def _missing_key_response() -> str:
    return ResponseBuilder.build_error_response(
        "HEVY_API_KEY is not configured. Add it to .env (get one from the Hevy app: "
        "Settings > API).",
        error_type="validation_error",
    )


def _set_to_dict(s: dict[str, Any]) -> dict[str, Any]:
    """Slim a Hevy set entry down to non-null fields."""
    out: dict[str, Any] = {"type": s.get("type")}
    for key in ("weight_kg", "reps", "distance_meters", "duration_seconds", "rpe"):
        if s.get(key) is not None:
            out[key] = s[key]
    return out


def _exercise_to_dict(e: dict[str, Any], *, include_sets: bool) -> dict[str, Any]:
    """Slim a Hevy exercise entry — full set detail or just a set count."""
    out: dict[str, Any] = {
        "title": e.get("title"),
        "exercise_template_id": e.get("exercise_template_id"),
    }
    if e.get("superset_id") is not None:
        out["superset_id"] = e["superset_id"]
    sets = e.get("sets", [])
    if include_sets:
        out["sets"] = [_set_to_dict(s) for s in sets]
    else:
        out["set_count"] = len(sets)
    return out


def _workout_summary(w: dict[str, Any]) -> dict[str, Any]:
    """LIGHT summary of one workout — no per-set detail."""
    exercises = w.get("exercises", [])
    return {
        "id": w.get("id"),
        "title": w.get("title"),
        "start_time": w.get("start_time"),
        "end_time": w.get("end_time"),
        "exercise_count": len(exercises),
        "total_sets": sum(len(e.get("sets", [])) for e in exercises),
    }


def _routine_summary(r: dict[str, Any]) -> dict[str, Any]:
    """LIGHT summary of one routine template."""
    return {
        "id": r.get("id"),
        "title": r.get("title"),
        "folder_id": r.get("folder_id"),
        "exercises": [_exercise_to_dict(e, include_sets=False) for e in r.get("exercises", [])],
    }


async def get_recent_workouts(
    page: Annotated[int, "Page number, 1-indexed"] = 1,
    page_size: Annotated[int, "Workouts per page, 1-10 (Hevy API max is 10)"] = 10,
    ctx: Context | None = None,
) -> str:
    """List LOGGED Hevy workouts (strength training), newest first — LIGHT summary only.

    Use for "what have I lifted recently?", "show my last gym sessions". Each
    result has exercise/set *counts* only, not the weights and reps — for the
    full per-set breakdown of one specific workout use hevy_get_workout_details.

    Args:
        page: Page number, 1-indexed
        page_size: Workouts per page, 1-10
        ctx: Injected MCP context

    Returns:
        JSON string with the data
    """
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    if not config.hevy_api_key:
        return _missing_key_response()

    if not (1 <= page_size <= 10):
        return ResponseBuilder.build_error_response(
            "page_size must be between 1 and 10 (Hevy API limit)",
            error_type="validation_error",
        )

    try:
        async with HevyClient(config) as client:
            result = await client.get_workouts(page=page, page_size=page_size)
            workouts = [_workout_summary(w) for w in result.get("workouts", [])]

            return ResponseBuilder.build_response(
                data={"workouts": workouts},
                metadata={"page": result.get("page"), "page_count": result.get("page_count")},
                query_type="hevy_recent_workouts",
            )
    except HevyAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def get_workout_details(
    workout_id: Annotated[str, "The Hevy workout ID (use hevy_get_recent_workouts to find one)"],
    ctx: Context | None = None,
) -> str:
    """Fetch the FULL per-set breakdown of ONE logged Hevy workout — weights, reps, RPE.

    Use for "what did I lift in my last session", "fill in the notes for my
    gym session" (pair with icu_update_activity to write it into Intervals.icu).
    For a list of many workouts with just counts, use hevy_get_recent_workouts.

    Args:
        workout_id: The Hevy workout ID
        ctx: Injected MCP context

    Returns:
        JSON string with the data
    """
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    if not config.hevy_api_key:
        return _missing_key_response()

    try:
        async with HevyClient(config) as client:
            w = await client.get_workout(workout_id)

            data = {
                "id": w.get("id"),
                "title": w.get("title"),
                "start_time": w.get("start_time"),
                "end_time": w.get("end_time"),
                "exercises": [
                    _exercise_to_dict(e, include_sets=True) for e in w.get("exercises", [])
                ],
            }

            return ResponseBuilder.build_response(data=data, query_type="hevy_workout_details")
    except HevyAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def get_routines(
    page: Annotated[int, "Page number, 1-indexed"] = 1,
    page_size: Annotated[int, "Routines per page, 1-10 (Hevy API max is 10)"] = 10,
    ctx: Context | None = None,
) -> str:
    """List saved Hevy routine TEMPLATES (e.g. "Séance A/B") — exercise names and set counts, not a log of what was performed.

    Use for "what's in my Séance A routine", "show my saved workout
    templates". For actual performed workouts use hevy_get_recent_workouts.

    Args:
        page: Page number, 1-indexed
        page_size: Routines per page, 1-10
        ctx: Injected MCP context

    Returns:
        JSON string with the data
    """
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    if not config.hevy_api_key:
        return _missing_key_response()

    if not (1 <= page_size <= 10):
        return ResponseBuilder.build_error_response(
            "page_size must be between 1 and 10 (Hevy API limit)",
            error_type="validation_error",
        )

    try:
        async with HevyClient(config) as client:
            result = await client.get_routines(page=page, page_size=page_size)
            routines = [_routine_summary(r) for r in result.get("routines", [])]

            return ResponseBuilder.build_response(
                data={"routines": routines},
                metadata={"page": result.get("page"), "page_count": result.get("page_count")},
                query_type="hevy_routines",
            )
    except HevyAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )


async def get_exercise_templates(
    page: Annotated[int, "Page number, 1-indexed"] = 1,
    page_size: Annotated[int, "Exercises per page"] = 20,
    ctx: Context | None = None,
) -> str:
    """Browse Hevy's exercise CATALOG (definitions: name, muscle group, equipment) — not anything performed or planned.

    Use to resolve an exercise_template_id seen in a workout/routine, or to
    look up what muscle group / equipment an exercise uses. Not for tracking
    progress on an exercise — that requires walking hevy_get_recent_workouts.

    Args:
        page: Page number, 1-indexed
        page_size: Exercises per page
        ctx: Injected MCP context

    Returns:
        JSON string with the data
    """
    assert ctx is not None
    config: ICUConfig = await ctx.get_state("config")

    if not config.hevy_api_key:
        return _missing_key_response()

    if page_size < 1:
        return ResponseBuilder.build_error_response(
            "page_size must be at least 1", error_type="validation_error"
        )

    try:
        async with HevyClient(config) as client:
            result = await client.get_exercise_templates(page=page, page_size=page_size)
            templates = [
                {
                    "id": t.get("id"),
                    "title": t.get("title"),
                    "primary_muscle_group": t.get("primary_muscle_group"),
                    "secondary_muscle_groups": t.get("secondary_muscle_groups"),
                    "equipment": t.get("equipment"),
                }
                for t in result.get("exercise_templates", [])
            ]

            return ResponseBuilder.build_response(
                data={"exercise_templates": templates},
                metadata={"page": result.get("page"), "page_count": result.get("page_count")},
                query_type="hevy_exercise_templates",
            )
    except HevyAPIError as e:
        return ResponseBuilder.build_error_response(e.message, error_type="api_error")
    except Exception as e:
        return ResponseBuilder.build_error_response(
            f"Unexpected error: {str(e)}", error_type="internal_error"
        )
