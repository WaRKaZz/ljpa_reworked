import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ljpa_reworked.models.database_models import LinkedinPost
from ljpa_reworked.operations.linkedin_post_ops import save_linkedin_post
from ljpa_reworked.services.harness_posts_scraper import (
    extract_posts_from_feed,
    run_posts_scraper,
)


@pytest.mark.asyncio
async def test_extract_posts_from_feed_returns_structured_dicts():
    # Setup mock page and elements
    mock_page = MagicMock()

    mock_elem1 = MagicMock()
    mock_elem1.inner_text = AsyncMock(return_value="Hiring Senior Python Developer at TechCorp! Contact recruiter@techcorp.com")
    mock_link1 = MagicMock()
    mock_link1.get_attribute = AsyncMock(return_value="https://www.linkedin.com/feed/update/urn:li:activity:123456789/")
    mock_link_loc1 = MagicMock()
    mock_link_loc1.first = mock_link1
    mock_link_loc1.count = AsyncMock(return_value=1)
    mock_elem1.locator = MagicMock(return_value=mock_link_loc1)

    mock_elem2 = MagicMock()
    mock_elem2.inner_text = AsyncMock(return_value="We are looking for a Data Engineer in Berlin.")
    mock_link2 = MagicMock()
    mock_link2.get_attribute = AsyncMock(return_value="https://www.linkedin.com/feed/update/urn:li:activity:987654321/")
    mock_link_loc2 = MagicMock()
    mock_link_loc2.first = mock_link2
    mock_link_loc2.count = AsyncMock(return_value=1)
    mock_elem2.locator = MagicMock(return_value=mock_link_loc2)

    mock_posts_locator = MagicMock()
    mock_posts_locator.count = AsyncMock(return_value=2)
    mock_posts_locator.nth.side_effect = [mock_elem1, mock_elem2]

    mock_page.locator.return_value = mock_posts_locator


    posts = await extract_posts_from_feed(mock_page, max_posts=10)

    assert len(posts) == 2
    assert posts[0]["text"] == "Hiring Senior Python Developer at TechCorp! Contact recruiter@techcorp.com"
    assert posts[0]["url"] == "https://www.linkedin.com/feed/update/urn:li:activity:123456789/"
    assert posts[1]["text"] == "We are looking for a Data Engineer in Berlin."
    assert posts[1]["url"] == "https://www.linkedin.com/feed/update/urn:li:activity:987654321/"


@pytest.mark.asyncio
async def test_run_posts_scraper_connects_and_saves():
    mock_post_record = LinkedinPost(id=1, text="Test Job Post", url="https://linkedin.com/feed/update/1")

    with patch(
        "ljpa_reworked.services.harness_posts_scraper.extract_posts_from_feed",
        new_callable=AsyncMock,
    ) as mock_extract, patch(
        "ljpa_reworked.services.harness_posts_scraper.save_linkedin_post"
    ) as mock_save, patch(
        "ljpa_reworked.services.harness_posts_scraper.async_playwright"
    ) as mock_playwright:
        mock_extract.return_value = [
            {"text": "Test Job Post", "url": "https://linkedin.com/feed/update/1"}
        ]
        mock_save.return_value = mock_post_record

        mock_p_ctx = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_playwright.return_value.__aenter__.return_value = mock_p_ctx
        mock_p_ctx.chromium.connect_over_cdp.return_value = mock_browser
        mock_browser.contexts = [mock_context]
        mock_context.pages = [mock_page]

        result = await run_posts_scraper(cdp_url="http://cloak-browser:9222", max_posts=5)

        mock_p_ctx.chromium.connect_over_cdp.assert_called_once_with("http://cloak-browser:9222")
        mock_page.goto.assert_called_once_with("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        mock_save.assert_called_once_with(text="Test Job Post", url="https://linkedin.com/feed/update/1")
        assert len(result) == 1
        assert result[0] == mock_post_record


def test_save_linkedin_post_operations():
    mock_db = MagicMock()
    mock_post = MagicMock()

    with patch("ljpa_reworked.operations.linkedin_post_ops.create_linkedin_post", return_value=mock_post) as mock_create:
        res = save_linkedin_post("Sample text", url="http://test.com", db=mock_db)
        mock_create.assert_called_once_with(db=mock_db, text="Sample text", url="http://test.com", screenshot_path=None)
        assert res == mock_post
