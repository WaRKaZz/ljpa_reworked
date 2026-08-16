from unittest.mock import MagicMock, patch

from ljpa_reworked import main


def test_main_collect_mode_runs_discovery_and_evaluates_without_resume_gen_or_submit():
    with (
        patch("ljpa_reworked.main.init_db") as init_db,
        patch("ljpa_reworked.main.SessionLocal") as session_local,
        patch("ljpa_reworked.main.run_linkedin_harness") as run_harness,
        patch("ljpa_reworked.main.JobSpyIntegrationService") as jobspy,
        patch("ljpa_reworked.main.evaluate_unrated_vacancies") as eval_vacancies,
        patch("ljpa_reworked.main.generate_missing_resumes") as gen_resumes,
        patch("ljpa_reworked.main.submit_top_email_vacancies") as submit_email,
        patch("ljpa_reworked.main.submit_top_vacancies") as submit_top,
    ):
        mock_db = MagicMock()
        session_local.return_value.__enter__.return_value = mock_db

        ret = main.main(mode="collect")
        assert ret == 0

        init_db.assert_called_once()
        run_harness.assert_called_once()
        jobspy.return_value.run.assert_called_once()
        eval_vacancies.assert_called_once_with(mock_db)
        gen_resumes.assert_not_called()
        submit_email.assert_not_called()
        submit_top.assert_not_called()


def test_main_email_process_mode_evaluates_generates_resumes_and_submits_all_emails():
    with (
        patch("ljpa_reworked.main.init_db") as init_db,
        patch("ljpa_reworked.main.SessionLocal") as session_local,
        patch("ljpa_reworked.main.run_linkedin_harness") as run_harness,
        patch("ljpa_reworked.main.JobSpyIntegrationService") as jobspy,
        patch("ljpa_reworked.main.process_unevaluated_vacancies") as process_vacancies,
        patch(
            "ljpa_reworked.main.submit_top_email_vacancies", return_value=3
        ) as submit_email,
        patch("ljpa_reworked.main.submit_top_vacancies") as submit_top,
    ):
        mock_db = MagicMock()
        session_local.return_value.__enter__.return_value = mock_db

        ret = main.main(mode="email_process")
        assert ret == 0

        init_db.assert_called_once()
        run_harness.assert_not_called()
        jobspy.assert_not_called()
        process_vacancies.assert_called_once_with(mock_db)
        submit_email.assert_called_once_with(mock_db, limit=None)
        submit_top.assert_not_called()


def test_main_url_process_mode_evaluates_generates_resumes_and_submits_urls():
    with (
        patch("ljpa_reworked.main.init_db") as init_db,
        patch("ljpa_reworked.main.SessionLocal") as session_local,
        patch("ljpa_reworked.main.run_linkedin_harness") as run_harness,
        patch("ljpa_reworked.main.JobSpyIntegrationService") as jobspy,
        patch("ljpa_reworked.main.process_unevaluated_vacancies") as process_vacancies,
        patch("ljpa_reworked.main.submit_top_email_vacancies") as submit_email,
        patch("ljpa_reworked.main.submit_top_vacancies", return_value=2) as submit_top,
    ):
        mock_db = MagicMock()
        session_local.return_value.__enter__.return_value = mock_db

        ret = main.main(mode="url_process")
        assert ret == 0

        init_db.assert_called_once()
        run_harness.assert_not_called()
        jobspy.assert_not_called()
        process_vacancies.assert_called_once_with(mock_db)
        submit_email.assert_not_called()
        submit_top.assert_called_once_with(mock_db, limit=None)
