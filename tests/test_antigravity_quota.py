from unittest.mock import MagicMock


def test_usage_http_returns_gemini_five_hour_remaining_fraction(monkeypatch):
    from ljpa_reworked.services import harness_runner

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"remaining_fraction": 0.08}'

    monkeypatch.setattr(
        harness_runner.urllib.request, "urlopen", lambda request, timeout: Response()
    )

    assert (
        harness_runner.get_gemini_quota_remaining("http://harness:8080/run-harness")
        == 0.08
    )


def test_submission_stops_before_harness_when_gemini_five_hour_remaining_is_at_or_below_seven_percent(
    monkeypatch,
):
    from ljpa_reworked import main

    monkeypatch.setattr(main, "get_gemini_quota_remaining", lambda api_url: 0.07)
    monkeypatch.setattr(main, "build_ranked_submission_queue", lambda db: [object()])
    harness = MagicMock()
    monkeypatch.setattr(main, "harness_submit", harness)

    assert main.submit_top_vacancies(MagicMock()) == 0
    harness.assert_not_called()


def test_submission_continues_when_gemini_five_hour_remaining_is_above_seven_percent(
    monkeypatch,
):
    from ljpa_reworked import main

    vacancy = MagicMock(id=1, submit_url="https://example.com/apply")
    ranked = MagicMock(vacancy=vacancy)
    resume = MagicMock(path="resume.pdf")
    monkeypatch.setattr(main, "get_gemini_quota_remaining", lambda api_url: 0.071)
    monkeypatch.setattr(main, "build_ranked_submission_queue", lambda db: [ranked])
    monkeypatch.setattr(main, "get_resume_by_vacancy", lambda db, vacancy_id: resume)
    monkeypatch.setattr(main, "harness_submit", lambda **kwargs: 0)
    monkeypatch.setattr(
        main, "confirm_url_application_submitted", lambda **kwargs: None
    )

    assert main.submit_top_vacancies(MagicMock()) == 0
