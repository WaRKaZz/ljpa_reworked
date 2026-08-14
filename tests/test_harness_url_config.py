from unittest.mock import patch


def test_main_uses_harness_api_url_from_config():
    from ljpa_reworked import main

    with patch("ljpa_reworked.main.run_linkedin_harness") as run_harness:
        with patch("ljpa_reworked.main.JobSpyIntegrationService") as jobspy:
            with patch("ljpa_reworked.main.SessionLocal") as session_local:
                session_local.return_value.__enter__.return_value = object()
                with patch("ljpa_reworked.main.process_unevaluated_vacancies"):
                    main.HARNESS_API_URL = "http://127.0.0.1:8080/run-harness"
                    main.main()

    run_harness.assert_called_once_with(api_url="http://127.0.0.1:8080/run-harness")
    jobspy.return_value.run.assert_called_once()
