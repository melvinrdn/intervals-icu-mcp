import json
from unittest.mock import AsyncMock, MagicMock

from httpx import Response

from intervals_icu_mcp.tools.hevy import (
    get_exercise_templates,
    get_recent_workouts,
    get_routines,
    get_workout_details,
)

SAMPLE_WORKOUT = {
    "id": "w1",
    "title": "Séance A",
    "start_time": "2026-09-08T10:26:12+00:00",
    "end_time": "2026-09-08T11:32:15+00:00",
    "exercises": [
        {
            "index": 0,
            "title": "Romanian Deadlift (Barbell)",
            "exercise_template_id": "2B4B7310",
            "superset_id": None,
            "sets": [
                {
                    "index": 0,
                    "type": "warmup",
                    "weight_kg": 60,
                    "reps": 4,
                    "distance_meters": None,
                    "duration_seconds": None,
                    "rpe": None,
                },
                {
                    "index": 1,
                    "type": "normal",
                    "weight_kg": 100,
                    "reps": 8,
                    "distance_meters": None,
                    "duration_seconds": None,
                    "rpe": 7,
                },
            ],
        }
    ],
}


class TestGetRecentWorkouts:
    async def test_success_summarizes_without_set_detail(self, mock_hevy_config, hevy_respx_mock):
        mock_ctx = MagicMock()
        mock_ctx.get_state = AsyncMock(return_value=mock_hevy_config)

        hevy_respx_mock.get("/workouts", params={"page": 1, "pageSize": 10}).mock(
            return_value=Response(
                200, json={"page": 1, "page_count": 2, "workouts": [SAMPLE_WORKOUT]}
            )
        )

        result = await get_recent_workouts(ctx=mock_ctx)
        response = json.loads(result)

        workout = response["data"]["workouts"][0]
        assert workout["id"] == "w1"
        assert workout["exercise_count"] == 1
        assert workout["total_sets"] == 2
        assert "sets" not in workout
        assert response["metadata"]["page_count"] == 2

    async def test_missing_api_key(self, hevy_respx_mock):
        from intervals_icu_mcp.auth import ICUConfig

        mock_ctx = MagicMock()
        mock_ctx.get_state = AsyncMock(return_value=ICUConfig())

        result = await get_recent_workouts(ctx=mock_ctx)
        response = json.loads(result)

        assert response["error"]["type"] == "validation_error"

    async def test_page_size_validation(self, mock_hevy_config):
        mock_ctx = MagicMock()
        mock_ctx.get_state = AsyncMock(return_value=mock_hevy_config)

        result = await get_recent_workouts(page_size=11, ctx=mock_ctx)
        response = json.loads(result)

        assert response["error"]["type"] == "validation_error"

    async def test_api_error(self, mock_hevy_config, hevy_respx_mock):
        mock_ctx = MagicMock()
        mock_ctx.get_state = AsyncMock(return_value=mock_hevy_config)

        hevy_respx_mock.get("/workouts", params={"page": 1, "pageSize": 10}).mock(
            return_value=Response(401, json={"error": "Invalid API key"})
        )

        result = await get_recent_workouts(ctx=mock_ctx)
        response = json.loads(result)

        assert response["error"]["type"] == "api_error"


class TestGetWorkoutDetails:
    async def test_success_includes_full_set_detail(self, mock_hevy_config, hevy_respx_mock):
        mock_ctx = MagicMock()
        mock_ctx.get_state = AsyncMock(return_value=mock_hevy_config)

        hevy_respx_mock.get("/workouts/w1").mock(return_value=Response(200, json=SAMPLE_WORKOUT))

        result = await get_workout_details(workout_id="w1", ctx=mock_ctx)
        response = json.loads(result)

        exercise = response["data"]["exercises"][0]
        assert exercise["title"] == "Romanian Deadlift (Barbell)"
        assert len(exercise["sets"]) == 2
        assert exercise["sets"][1]["weight_kg"] == 100
        assert exercise["sets"][1]["rpe"] == 7
        assert "rpe" not in exercise["sets"][0]

    async def test_api_error(self, mock_hevy_config, hevy_respx_mock):
        mock_ctx = MagicMock()
        mock_ctx.get_state = AsyncMock(return_value=mock_hevy_config)

        hevy_respx_mock.get("/workouts/missing").mock(return_value=Response(404))

        result = await get_workout_details(workout_id="missing", ctx=mock_ctx)
        response = json.loads(result)

        assert response["error"]["type"] == "api_error"


class TestGetRoutines:
    async def test_success(self, mock_hevy_config, hevy_respx_mock):
        mock_ctx = MagicMock()
        mock_ctx.get_state = AsyncMock(return_value=mock_hevy_config)

        routine = {
            "id": "r1",
            "title": "Séance B",
            "folder_id": None,
            "exercises": [
                {"title": "Squat (Barbell)", "exercise_template_id": "D04AC939", "sets": [{}, {}]}
            ],
        }
        hevy_respx_mock.get("/routines", params={"page": 1, "pageSize": 10}).mock(
            return_value=Response(200, json={"page": 1, "page_count": 1, "routines": [routine]})
        )

        result = await get_routines(ctx=mock_ctx)
        response = json.loads(result)

        exercise = response["data"]["routines"][0]["exercises"][0]
        assert exercise["set_count"] == 2
        assert "sets" not in exercise

    async def test_page_size_validation(self, mock_hevy_config):
        mock_ctx = MagicMock()
        mock_ctx.get_state = AsyncMock(return_value=mock_hevy_config)

        result = await get_routines(page_size=0, ctx=mock_ctx)
        response = json.loads(result)

        assert response["error"]["type"] == "validation_error"


class TestGetExerciseTemplates:
    async def test_success(self, mock_hevy_config, hevy_respx_mock):
        mock_ctx = MagicMock()
        mock_ctx.get_state = AsyncMock(return_value=mock_hevy_config)

        hevy_respx_mock.get("/exercise_templates", params={"page": 1, "pageSize": 20}).mock(
            return_value=Response(
                200,
                json={
                    "page": 1,
                    "page_count": 23,
                    "exercise_templates": [
                        {
                            "id": "3BC06AD3",
                            "title": "21s Bicep Curl",
                            "primary_muscle_group": "biceps",
                            "secondary_muscle_groups": [],
                            "equipment": "barbell",
                        }
                    ],
                },
            )
        )

        result = await get_exercise_templates(ctx=mock_ctx)
        response = json.loads(result)

        template = response["data"]["exercise_templates"][0]
        assert template["id"] == "3BC06AD3"
        assert template["primary_muscle_group"] == "biceps"

    async def test_page_size_validation(self, mock_hevy_config):
        mock_ctx = MagicMock()
        mock_ctx.get_state = AsyncMock(return_value=mock_hevy_config)

        result = await get_exercise_templates(page_size=0, ctx=mock_ctx)
        response = json.loads(result)

        assert response["error"]["type"] == "validation_error"
