from unittest.mock import MagicMock, patch

from ljpa_reworked import main


def test_main_collect_chatgpt_mode():
    with (
        patch("ljpa_reworked.main.init_db") as init_db,
        patch("ljpa_reworked.main.SessionLocal") as session_local,
        patch("ljpa_reworked.main.ChatGPTGDriveService") as mock_service,
        patch("ljpa_reworked.main.evaluate_unrated_vacancies") as eval_vacancies,
    ):
        mock_db = MagicMock()
        session_local.return_value.__enter__.return_value = mock_db
        mock_service.return_value.run.return_value = (3, 1)

        ret = main.main(mode="collect-chatgpt", dry_run=False)
        assert ret == 0

        init_db.assert_called_once()
        mock_service.assert_called_once_with(dry_run=False)
        mock_service.return_value.run.assert_called_once_with(mock_db)
        eval_vacancies.assert_called_once_with(mock_db)


def test_main_collect_chatgpt_dry_run_skips_evaluation():
    with (
        patch("ljpa_reworked.main.init_db") as init_db,
        patch("ljpa_reworked.main.SessionLocal") as session_local,
        patch("ljpa_reworked.main.ChatGPTGDriveService") as mock_service,
        patch("ljpa_reworked.main.evaluate_unrated_vacancies") as eval_vacancies,
    ):
        mock_db = MagicMock()
        session_local.return_value.__enter__.return_value = mock_db
        mock_service.return_value.run.return_value = (2, 0)

        ret = main.main(mode="collect-chatgpt", dry_run=True)
        assert ret == 0

        init_db.assert_called_once()
        mock_service.assert_called_once_with(dry_run=True)
        eval_vacancies.assert_not_called()


def test_main_collect_harness_mode():
    with (
        patch("ljpa_reworked.main.init_db") as init_db,
        patch("ljpa_reworked.main.SessionLocal") as session_local,
        patch("ljpa_reworked.main.run_linkedin_harness") as run_harness,
        patch("ljpa_reworked.main.evaluate_unrated_vacancies") as eval_vacancies,
    ):
        mock_db = MagicMock()
        session_local.return_value.__enter__.return_value = mock_db

        ret = main.main(mode="collect-harness")
        assert ret == 0

        init_db.assert_called_once()
        run_harness.assert_called_once()
        eval_vacancies.assert_called_once_with(mock_db)


def test_main_collect_jobspy_mode():
    with (
        patch("ljpa_reworked.main.init_db") as init_db,
        patch("ljpa_reworked.main.SessionLocal") as session_local,
        patch("ljpa_reworked.main.JobSpyIntegrationService") as jobspy,
        patch("ljpa_reworked.main.evaluate_unrated_vacancies") as eval_vacancies,
    ):
        mock_db = MagicMock()
        session_local.return_value.__enter__.return_value = mock_db

        ret = main.main(mode="collect-jobspy")
        assert ret == 0

        init_db.assert_called_once()
        jobspy.return_value.run.assert_called_once()
        eval_vacancies.assert_called_once_with(mock_db)


def test_main_email_submit_mode():
    with (
        patch("ljpa_reworked.main.init_db") as init_db,
        patch("ljpa_reworked.main.SessionLocal") as session_local,
        patch("ljpa_reworked.main.process_unevaluated_vacancies") as process_vacancies,
        patch(
            "ljpa_reworked.main.submit_top_email_vacancies", return_value=3
        ) as submit_email,
    ):
        mock_db = MagicMock()
        session_local.return_value.__enter__.return_value = mock_db

        ret = main.main(mode="email-submit")
        assert ret == 0

        init_db.assert_called_once()
        process_vacancies.assert_called_once_with(mock_db)
        submit_email.assert_called_once_with(mock_db, limit=None)


def test_main_url_submit_mode():
    with (
        patch("ljpa_reworked.main.init_db") as init_db,
        patch("ljpa_reworked.main.SessionLocal") as session_local,
        patch("ljpa_reworked.main.process_unevaluated_vacancies") as process_vacancies,
        patch("ljpa_reworked.main.submit_top_vacancies", return_value=2) as submit_top,
    ):
        mock_db = MagicMock()
        session_local.return_value.__enter__.return_value = mock_db

        ret = main.main(mode="url-submit")
        assert ret == 0

        init_db.assert_called_once()
        process_vacancies.assert_called_once_with(mock_db)
        submit_top.assert_called_once_with(mock_db, limit=None)
