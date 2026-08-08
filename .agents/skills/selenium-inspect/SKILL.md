---
name: selenium-inspect
description: Patterns and techniques for finding and updating LinkedIn selectors when the UI changes.
---

# Selenium Inspect Skill

This skill provides techniques for maintaining robustness in Selenium web scraping, particularly for dealing with dynamic platforms like LinkedIn.

## When to use

Use this skill when the scraping pipeline fails due to `NoSuchElementException` or when LinkedIn updates its DOM structure.

## Instructions

1. **Analyze the Failure**: Review the error logs to identify which selector failed (e.g., job title, company name, description).
2. **Launch Interactive Session**: You may want to launch a local browser session manually or use a debugging script to pause execution at the failure point.
3. **Inspect the DOM**:
   - Prefer finding elements by text content or ARIA labels if possible, as they are less likely to change than class names.
   - Example: Use `//button[contains(text(), 'Apply')]` instead of `//button[@class='btn-primary-123']`.
   - Look for `data-*` attributes (e.g., `data-test-id`, `data-control-name`). These are often more stable.
4. **Test the New Selector**: Use the browser's developer tools console to test the XPath or CSS selector (e.g., `$x('//your/xpath')` or `$$('your.css.selector')`) before updating the Python code.
5. **Update Code**: Replace the broken selector in the codebase. Ensure you are using appropriate `WebDriverWait` conditions for the new element.
