from unittest.mock import patch


def test_main_email_process_skips_discovery_and_processes_unevaluated_vacancies():
    from ljpa_reworked import main

    with patch("ljpa_reworked.main.run_linkedin_harness") as harness:
        with patch("ljpa_reworked.main.JobSpyIntegrationService") as jobspy:
            with patch("ljpa_reworked.main.SessionLocal") as session_local:
                db = session_local.return_value.__enter__.return_value
                with patch(
                    "ljpa_reworked.main.process_unevaluated_vacancies"
                ) as process:
                    with patch("ljpa_reworked.main.submit_top_email_vacancies"):
                        main.main(mode="email_process")

    harness.assert_not_called()
    jobspy.return_value.run.assert_not_called()
    process.assert_called_once_with(db)


def test_main_initializes_schema_before_opening_database_session():
    from ljpa_reworked import main

    with patch("ljpa_reworked.main.init_db") as init_db:
        with patch("ljpa_reworked.main.SessionLocal") as session_local:
            with patch("ljpa_reworked.main.process_unevaluated_vacancies"):
                with patch("ljpa_reworked.main.submit_top_email_vacancies"):
                    main.main(mode="email_process")

    init_db.assert_called_once_with()
    session_local.assert_called_once_with()
