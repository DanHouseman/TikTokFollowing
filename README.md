# TikTok Following Scraper

This repository contains an **asynchronous Playwright** script that:

- **Logs into TikTok** (or reuses a persistent session).
- **Expands** the “Following” list in the left navigation by clicking "See more" until all followed accounts are visible.
- **Collects** the **profile URLs** for everyone you follow.
- **Scrapes each profile in parallel** (default concurrency is 5) to gather:
  - **Profile Image URL** (by grabbing the last element matching `[class*=ImgAvatar]`).
  - **Bio Information** (non-TikTok URLs and any email addresses).
  - **Linktr.ee** link, if present, and from that page: known social links (YouTube, Instagram, etc.).
- **Saves everything** to `following_data.json`.
- **Creates a local webpage** that loads `following_data.json` into a sortable, visual format (handled by `server.py` after scraping finishes).

## Features

1. **Persistent Login**
   - Stores your login session in the `./tiktok_profile` folder, so you only need to log in once (unless TikTok expires your session).

2. **Async + Parallel Scraping**
   - Utilizes Python’s `asyncio` to scrape multiple profiles concurrently, significantly speeding up the data collection process.
   - Configurable concurrency with a default of 5 parallel pages.

3. **Rich Profile Data**
   - **Profile Image URL**: Extracts the avatar image URL by targeting the last element matching `[class*=ImgAvatar]`.
   - **Bio Information**: Extracts non-TikTok URLs and email addresses from the user's bio.
   - **Linktr.ee Integration**: If a user has a `linktr.ee` link in their profile, the script navigates to it and gathers known social links (YouTube, Instagram, etc.).

4. **Local Webpage Creation**
   - After scraping, the script automatically executes `server.py`, which generates a local webpage.
   - This webpage loads `following_data.json` and presents the data in a **sortable, visual format**, allowing for easy browsing and analysis.

## Requirements

- **Python 3.7+**
- **Playwright** (and installed browser binaries)
- **Additional Dependencies** listed in `requirements.txt`

Ensure that `server.py` has its own dependencies installed if it requires any.

## Installation

1. Clone the Repository

```bash
git clone https://github.com/DanHouseman/TikTokFollowing.git
cd tiktok-following-scraper
```
2. (Optional) Create a Virtual Environment

It’s recommended to use a virtual environment to manage dependencies.

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install Dependencies
```bash
pip install -r requirements.txt
```
4. Install Playwright Browser Binaries

Playwright requires specific browser binaries to function correctly.
```bash
playwright install
```
This command downloads the necessary Chromium (or other browsers) binaries required by Playwright.

### Usage

1. Prepare Credentials

Ensure you have your TikTok username/email and password ready.

2. Run the Scraper
```bash
python script.py <username> <password> [<concurrency>]
```
-	`<username>`: Your TikTok login (email or username).
-	`<password>`: Your TikTok account password.
-	`<concurrency>` (optional): Number of profiles to scrape in parallel (default is 5).

Example:
```bash
python script.py myemail@example.com MySuperSecretPassword 5
```

3. Login Flow
- First-Time Run or Session Expired:
- A browser window will open prompting you to log in to TikTok.
- Solve any captchas or 2FA prompts manually in the browser.
- After successfully logging in, return to the terminal and press ENTER to continue.
- The script will verify the session and proceed with scraping.

5. Scraping Process
- Expands the “Following” list by clicking “See more” in the left navigation until all followed accounts are displayed.
-	Collects profile URLs for all followed accounts.
-	Scrapes them in parallel (in batches of <concurrency>), gathering:
-	Profile Image URL
-	Bio URLs (excluding any TikTok URLs)
-	Bio Emails (if listed)
-	Linktr.ee URL and associated social links.
-	Saves results in following_data.json.

7. Post-Scraping Action
	-	Once scraping is complete and following_data.json is saved, the script automatically executes server.py.
	-	server.py is responsible for:
	-	Creating a local webpage.
	-	Loading following_data.json.
	-	Presenting the data in a sortable, visual format for easy viewing and analysis.

8. Access the Local Webpage

After server.py runs, open your browser and navigate to:

http://localhost:8080

This page will display your following data in a sortable, visual format based on the pre-created .html file.

Output

following_data.json

Each entry in this JSON array includes:
```json
{
  "tiktok_profile": "https://www.tiktok.com/@someusername",
  "profile_image_url": "https://example.com/avatar.jpg",
  "bio_urls": ["https://mywebsite.com"],
  "bio_emails": ["someone@example.com"],
  "linktree_url": "https://linktr.ee/someuser",
  "social_links": [
    "https://www.youtube.com/somechannel",
    "https://www.instagram.com/someuser"
  ]
}
```
Local Webpage

After scraping, server.py runs and creates a local webpage that:
-	Loads following_data.json.
-	Displays the data in a sortable table or other visual formats.
-	Allows you to sort and filter the data based on different criteria (e.g., username, social links).

Running server.py

The server.py script is responsible for creating a local webpage that visually presents the data from following_data.json. It runs a local server on port 8080 and loads the .html file to display the data.

1. Ensure server.py Exists
	-	Verify that server.py is present in the root directory of the project.
	-	Ensure that the associated .html file (e.g., following.html) is correctly set up to load and present following_data.json.

2. Script Execution
	-	The main scraping script automatically runs server.py after completing the scraping process.
	-	If you need to run server.py manually, use:
```bash
python server.py
```
-	Access the local webpage by navigating to http://localhost:8080 in your browser.

3. Customization
   -	Modify server.py and the .html file as needed to change the presentation or add additional features.


# Notes and Tips
-	Selectors
    -	If [class*=ImgAvatar] or [data-e2e='user-bio'] do not match the elements on your TikTok profile page, inspect the page using browser developer tools and update the selectors in the script accordingly.
-	Handling Captchas
    -	Opening multiple profiles quickly may trigger TikTok’s anti-bot measures, resulting in captchas or temporary blocks.
-	Solutions:
    -	Lower the concurrency: Reduce the number of parallel pages (e.g., set concurrency to 3).
    -	Introduce random delays between scraping batches.
    -	Monitor for any captcha prompts and handle them manually.
-	Session Persistence
    -	The tiktok_profile folder stores your session data (cookies, localStorage, etc.). To force a fresh login, delete this folder and rerun the script.
-	Local Webpage
    -	Ensure that server.py and the associated .html file are correctly set up to load and display following_data.json.
    -	If server.py requires specific ports or frameworks, verify its configuration accordingly.
-	Error Handling
    -	The script includes basic error handling for navigation failures. Monitor the terminal output for any errors during scraping and adjust as necessary.

# Troubleshooting
- Issue: The script only scrapes a subset of your followings.
- Solution: 
    - Ensure that the “See more” button is correctly identified and clicked.
  - Increase await asyncio.sleep(...) durations to allow more time for items to load.
  - Verify that the selectors match your TikTok UI.
-	Issue: Elements like [class*=ImgAvatar] or [data-e2e='user-bio'] are not found.
-	Solution: 
    -	Inspect your TikTok profile page using browser developer tools.
    -	Update the selectors in the script to match the actual classes or attributes used.
-	Issue: After scraping, server.py does not execute or fails.
-	Solution: 
    -	Ensure server.py exists in the same directory.
      -	Verify that server.py has the necessary code to load and display following_data.json.
    -	Check for any errors in server.py and address them accordingly.
-	Issue: Missing Python packages or Playwright binaries.
-	Solution:
      -	Run pip install -r requirements.txt to install required packages.
      -	Run playwright install to install necessary browser binaries.


# License

This project is licensed under the MIT License. Feel free to modify and adapt it to your needs.

# Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

