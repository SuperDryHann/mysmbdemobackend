from playwright.sync_api import sync_playwright

def run(playwright):
    # Launch Chromium browser
    browser = playwright.chromium.launch(headless=False)  # Set headless=True for headless mode
    page = browser.new_page()
    
    # Navigate to the target page
    page.goto('https://www.microsoft.com/en-au/microsoft-365/copilot')

    # Wait for the page to load completely
    page.wait_for_load_state('networkidle')

    # Get all the anchor tags (<a>) on the page
    links = page.locator('a')
    
    # Loop through all the anchor tags and print their URLs
    for i in range(links.count()):
        link_url = links.nth(i).get_attribute('href')
        if link_url:
            print(f"Link {i + 1}: {link_url}")

    # Close the browser
    browser.close()

# Ensure that Playwright is used within the `with` statement
with sync_playwright() as playwright:
    run(playwright)
