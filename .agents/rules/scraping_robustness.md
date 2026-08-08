---
trigger: always_on
---

# Scraping Robustness Rule

When writing or modifying Selenium web scraping logic in `services/` or `operations/`, always ensure robustness:

1. **Exception Handling**: Catch and handle common Selenium exceptions like `TimeoutException`, `NoSuchElementException`, and `StaleElementReferenceException`.
2. **Explicit Waits**: Do not rely on `time.sleep()`. Always use `WebDriverWait` combined with `expected_conditions` to wait for elements to appear, become clickable, or disappear.
3. **Selector Resiliency**: Use resilient selectors (e.g., data attributes if available) instead of brittle absolute XPaths. LinkedIn frequently changes its UI, so prefer relative and semantic locators.
4. **Anti-Bot Measures**: Be aware of captchas and rate limiting. Implement random delays or backoff mechanisms if necessary.
