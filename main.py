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

def scrape_applicant_contacts():
    """Scrape applicant contact details from LinkedIn job posting"""
    if not os.path.exists("auth.json"):
        print("❌ auth.json not found. Please run save_linkedin_session() first.")
        return
    
    applicants = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        
        # Load saved authentication session
        context = browser.new_context(storage_state="auth.json")
        page = context.new_page()
        
        print(f"Navigating to job posting: {JOB_URL}")
        page.goto(JOB_URL)
        
        # Wait for the page to load - wait for applicant list to appear
        print("Waiting for applicant list to load...")
        try:
            # Wait for the applicant list component to be visible
            page.wait_for_selector('[componentkey="JOB_POSTING_ApplicantListRootContent"]', timeout=30000)
        except Exception as e:
            print(f"⚠️  Warning: Could not find applicant list component. Continuing anyway...")
        
        # Give additional time for dynamic content to load
        page.wait_for_timeout(5000)
        
        # Process applicants one by one, loading more as needed
        print("Starting to extract applicant contacts one by one...\n")
        
        processed_count = 0
        max_iterations = 500  # Safety limit
        
        while processed_count < max_iterations:
            # Get current list of applicant names
            name_elements = page.query_selector_all('p.f11b6631.a56c4ee5')
            
            # Filter out non-name elements and get unique names we haven't processed
            valid_names = []
            seen_names = {app['name'].lower() for app in applicants}
            
            for name_elem in name_elements:
                try:
                    name = name_elem.inner_text().strip()
                    if (name and len(name) > 2 and 
                        name.lower() not in ['applicants', 'meet at least', 'meets most qualifications'] and
                        'qualifications' not in name.lower() and 
                        'edit' not in name.lower() and
                        name.lower() not in seen_names):
                        valid_names.append((name_elem, name))
                except:
                    continue
            
            if not valid_names:
                # No more unprocessed applicants, try to load more
                print("\nNo more unprocessed applicants. Checking for 'Load more' button...")
                load_more_clicked = False
                try:
                    load_more_elements = page.query_selector_all('button, span')
                    for elem in load_more_elements:
                        try:
                            text = (elem.inner_text() or '').strip().lower()
                            if 'load more' in text:
                                elem.scroll_into_view_if_needed()
                                page.wait_for_timeout(500)
                                elem.click()
                                page.wait_for_timeout(3000)  # Wait for new content
                                print("  ✓ Clicked 'Load more' button, waiting for new applicants...")
                                load_more_clicked = True
                                break
                        except:
                            continue
                except:
                    pass
                
                if not load_more_clicked:
                    print("  No 'Load more' button found. All applicants processed!")
                    break
            else:
                # Process the first unprocessed applicant
                name_elem, name = valid_names[0]
                processed_count += 1
        
                print(f"\nProcessing {processed_count}: {name} (Found {len(applicants)} so far)")
                
                # Scroll name element into view
                try:
                    name_elem.scroll_into_view_if_needed()
                    page.wait_for_timeout(500)
                except:
                    print(f"  ⚠️  Could not scroll to element, skipping...")
                    continue
                
                # Step 1: Click the applicant card to open the detail panel
                card_clicked = False
                try:
                    # Find the parent button/card that contains the name
                    parent_container = name_elem
                    for _ in range(10):
                        try:
                            role = parent_container.evaluate("el => el.getAttribute('role')")
                            if role == 'button':
                                parent_container.scroll_into_view_if_needed()
                                page.wait_for_timeout(300)
                                parent_container.click()
                                page.wait_for_timeout(2000)  # Wait for detail panel to open
                                card_clicked = True
                                print(f"  ✓ Clicked applicant card to open detail view")
                                break
                        except:
                            pass
                        
                        # Get parent
                        try:
                            parent_handle = parent_container.evaluate_handle("el => el.parentElement")
                            if parent_handle:
                                parent_container = parent_handle.as_element()
                            else:
                                break
                        except:
                            break
                except Exception as e:
                    print(f"  ⚠️  Error clicking card: {e}")
                
                if not card_clicked:
                    print(f"  ⚠️  Could not click applicant card for {name}")
                    continue
                
                # Step 2: Find and click the Contact button in the detail panel
                contact_clicked = False
                try:
                    # Wait for detail panel to fully load
                    page.wait_for_timeout(1500)
                    
                    # Find Contact button using data-view-name="hiring-applicant-contact"
                    # Wait for it to appear
                    try:
                        page.wait_for_selector('button[data-view-name="hiring-applicant-contact"]', timeout=5000)
                    except:
                        pass
                    
                    contact_btn = page.query_selector('button[data-view-name="hiring-applicant-contact"]')
                    if contact_btn:
                        contact_btn.scroll_into_view_if_needed()
                        page.wait_for_timeout(300)
                        contact_btn.click()
                        page.wait_for_timeout(2500)  # Wait for popover to appear
                        contact_clicked = True
                        print(f"  ✓ Clicked Contact button in detail panel")
                    else:
                        print(f"  ⚠️  Contact button not found in detail panel")
                except Exception as e:
                    print(f"  ⚠️  Error clicking Contact button: {e}")
                
                if not contact_clicked:
                    print(f"  ⚠️  Could not find Contact button in detail panel for {name}")
                    # Close detail panel and continue
                    try:
                        page.keyboard.press('Escape')
                        page.wait_for_timeout(500)
                    except:
                        pass
                    continue
                
                # Step 3: Extract email and phone from the popover menu
                contact_data = page.evaluate("""
                    () => {
                        let email = null;
                        let phone = null;
                        
                        // Look for the popover menu (has popover="manual")
                        const popover = document.querySelector('[popover="manual"]');
                        if (!popover) return { email: null, phone: null };
                        
                        // Find email in mailto link with data-view-name="hiring-applicant-contact-email"
                        const emailLink = popover.querySelector('a[data-view-name="hiring-applicant-contact-email"]');
                        if (emailLink) {
                            const href = emailLink.getAttribute('href');
                            if (href && href.startsWith('mailto:')) {
                                email = href.replace('mailto:', '').trim();
                            }
                        }
                        
                        // Find phone in div with data-view-name="hiring-applicant-contact-phone"
                        const phoneDiv = popover.querySelector('[data-view-name="hiring-applicant-contact-phone"]');
                        if (phoneDiv) {
                            // The phone number is in a <p> tag with classes f11b6631 _7d5e841d inside this div
                            const phonePara = phoneDiv.querySelector('p.f11b6631._7d5e841d');
                            if (phonePara) {
                                phone = phonePara.textContent.trim();
                            }
                        }
                        
                        return { email: email, phone: phone };
                    }
                """)
                
                email = contact_data.get('email') if contact_data else None
                phone = contact_data.get('phone') if contact_data else None
                
                # Close the popover and detail panel
                try:
                    page.keyboard.press('Escape')  # Close popover
                    page.wait_for_timeout(500)
                    page.keyboard.press('Escape')  # Close detail panel
                    page.wait_for_timeout(500)
                except:
                    pass
                
                if email or phone:
                    applicants.append({
                        'name': name,
                        'email': email or 'Not provided',
                        'phone': phone or 'Not provided'
                    })
                    print(f"  ✓ Found: Email={email or 'N/A'}, Phone={phone or 'N/A'}")
                else:
                    print(f"  ⚠️  No contact info found in popover for {name}")
        
        print(f"\n✅ Finished processing! Collected {len(applicants)} applicants.")
        
        # Keep browser open a bit longer to see results
        print("\n✅ Extraction complete! Keeping browser open for 10 seconds...")
        print("   (You can manually check the page if needed)")
        page.wait_for_timeout(10000)
        
        browser.close()
    
    return applicants

def save_applicants_to_file(applicants, filename="applicant_contacts.txt"):
    """Save applicant contacts to a text file"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("LinkedIn Job Applicants - Contact Details\n")
        f.write("=" * 50 + "\n\n")
        
        for i, applicant in enumerate(applicants, 1):
            f.write(f"{i}. {applicant['name']}\n")
            f.write(f"   Email: {applicant.get('email', 'Not provided')}\n")
            f.write(f"   Phone: {applicant.get('phone', 'Not provided')}\n")
            f.write("\n")
        
        f.write(f"\nTotal applicants: {len(applicants)}\n")
    
    print(f"\n✅ Saved {len(applicants)} applicants to {filename}")

def main():
    print("Starting LinkedIn applicant contact scraper...\n")
    
    applicants = scrape_applicant_contacts()
    
    if applicants:
        save_applicants_to_file(applicants)
        print(f"\n✅ Successfully scraped {len(applicants)} applicants!")
    else:
        print("\n⚠️  No applicants found. Please check:")
        print("   1. You are logged in correctly")
        print("   2. The job URL is correct")
        print("   3. There are applicants visible on the page")

if __name__ == "__main__":
    # save_linkedin_session()  # Run this first to save login session
    main()