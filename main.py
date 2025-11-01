import os 
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
JOB_URL = os.getenv("JOB_URL")

def save_linkedin_session():
    """Save LinkedIn login session for future use"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://www.linkedin.com/login")
        print("Please log in to LinkedIn manually in the browser window...")

        page.wait_for_timeout(200000)  # Give you 60 seconds to log in

        context.storage_state(path="auth.json")
        print("✅ Login session saved to auth.json")
        browser.close()

def main():

if __name__ == "__main__":
    # save_linkedin_session()  # Run this first to save login session
    main()