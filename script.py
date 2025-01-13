import asyncio
import sys
import re
import json
import time
import getpass
import subprocess
from typing import List
from playwright.async_api import async_playwright, BrowserContext, Page

# =============== Configuration ===============
USER_DATA_DIR = "./tiktok_profile"         # For persistent session
FOLLOWING_JSON = "following_data.json"     # Output JSON
DEFAULT_CONCURRENCY = 5                    # Default number of parallel pages
URL_REGEX = re.compile(r"(https?://[^\s]+)", re.IGNORECASE)
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

SOCIAL_DOMAINS = [
    "youtube.com", "instagram.com", "facebook.com", "substack.com", "onlyfans.com", "soundcloud.com", "tumblr.com", "twitch.tv",
    "linkedin.com", "snapchat.com", "bluesky", "twitter.com", "medium.com", "mastadon.social", "telegram.com", "vimeo.com",
    "x.com", "patreon.com", "pinterest.com", "github.com", "dribble.com", "discord.com", "reddit.com", "threads.net"
]
# ============================================

async def has_sessionid_cookie(context: BrowserContext) -> bool:
    """Check if 'sessionid' or 'sessionid_ss' is present, indicating we're logged in."""
    cookies = await context.cookies()
    for c in cookies:
        if c["name"] in ("sessionid", "sessionid_ss"):
            return True
    return False

async def do_login(context: BrowserContext, username: str, password: str) -> bool:
    """
    Opens the email/username login, waits for manual captcha/2FA solve, 
    then checks for session cookie.
    """
    page = await context.new_page()
    await page.goto("https://www.tiktok.com/login/phone-or-email/email", wait_until="domcontentloaded")

    # Adjust placeholders as TikTok changes
    await page.wait_for_selector("[placeholder='Email or username']")
    await page.wait_for_selector("[placeholder='Password']")
    await page.fill("[placeholder='Email or username']", username)
    await page.fill("[placeholder='Password']", password)
    await page.click("button[type='submit']")

    print("\nIf there's a captcha or 2FA, solve it in the browser.")
    input("When you're fully logged in, press ENTER here...")
    # Give time for session to finalize
    await asyncio.sleep(5)

    logged_in = await has_sessionid_cookie(context)
    await page.close()
    return logged_in

async def ensure_logged_in(play, username: str, password: str) -> BrowserContext:
    """
    Launches a persistent browser context. If session is invalid, prompts user login.
    Returns a context with a valid session or exits on failure.
    """
    browser = await play.chromium.launch_persistent_context(
        headless=False,
        user_data_dir=USER_DATA_DIR
    )
    if await has_sessionid_cookie(browser):
        print("Existing session is valid; no login required.")
    else:
        print("Session not found or expired. Please log in...")
        ok = await do_login(browser, username, password)
        if not ok:
            print("Login failed or not completed.")
            await browser.close()
            sys.exit(1)
        print("Login successful.")
    return browser

async def expand_following_list(page: Page):
    """
    Repeatedly clicks the 'See more' button in the left nav until it says 'Show less' 
    or is no longer found, indicating all accounts are revealed.
    """
    while True:
        see_more_btn = await page.query_selector("#side-nav-following-see-all")
        if not see_more_btn:
            break  # Possibly can't find it anymore -> done or different UI

        text = (await see_more_btn.inner_text()).strip().lower()
        if text == "see less":
            break

        await see_more_btn.click()
        await asyncio.sleep(2)  # let it load more items

async def collect_following_urls(page: Page) -> List[str]:
    """
    Gathers anchor tags from the left nav, filtering out /video, /live, /likes, etc.
    Returns a list of absolute profile URLs, e.g. https://www.tiktok.com/@username
    """
    urls = set()
    anchors = await page.query_selector_all("a[href]")
    for a in anchors:
        href = await a.get_attribute("href")
        if not href:
            continue
        # Convert relative /@... to absolute
        if href.startswith("/@"):
            href = "https://www.tiktok.com" + href

        # Keep only user profiles, skip /video, /live, /likes
        if ("https://www.tiktok.com/@" in href 
                and "/video/" not in href
                and "/live" not in href
                and "/likes" not in href):
            urls.add(href)

    return list(urls)

async def get_last_avatar_src(page: Page) -> str:
    """
    Finds all elements matching [class*=ImgAvatar] and returns the src 
    of the LAST one. If none found, returns None.
    """
    avatar_els = await page.query_selector_all("[class*=ImgAvatar]")
    if not avatar_els:
        return None
    last_el = avatar_els[-1]
    return await last_el.get_attribute("src")

async def scrape_profile_info(page: Page) -> dict:
    """
    Scrapes:
      - Last avatar image (using [class*=ImgAvatar])
      - Bio text -> find URLs (excluding tiktok.com) & emails
    """
    result = {
        "profile_image_url": None,
        "bio_urls": [],
        "bio_emails": []
    }

    # Last avatar
    avatar_src = await get_last_avatar_src(page)
    if avatar_src:
        result["profile_image_url"] = avatar_src

    # Grab potential bio element(s). We might try [data-e2e='user-bio'] or do a fallback
    # This is just an example. Adapt to your DOM
    bio_el = await page.query_selector("[data-e2e='user-bio']")
    if bio_el:
        bio_text = (await bio_el.inner_text()).strip()
        # Find URLs not containing tiktok.com
        found_urls = URL_REGEX.findall(bio_text)
        found_urls = [u for u in found_urls if "tiktok.com" not in u.lower()]
        found_emails = list(set(EMAIL_REGEX.findall(bio_text)))
        result["bio_urls"].extend(found_urls)
        result["bio_emails"].extend(found_emails)

    return result

async def open_linktree_and_find_socials(context: BrowserContext, linktree_url: str) -> List[str]:
    """Opens a new page to linktree_url, collects known social links by domain check."""
    page = await context.new_page()
    await page.goto(linktree_url, wait_until="domcontentloaded")
    await asyncio.sleep(3)

    social_links = []
    anchors = await page.query_selector_all("a[href]")
    for a in anchors:
        href = await a.get_attribute("href")
        if href:
            lower_href = href.lower()
            for domain in SOCIAL_DOMAINS:
                if domain in lower_href:
                    social_links.append(href)
                    break

    await page.close()
    return social_links

async def scrape_profile(context: BrowserContext, account_url: str) -> dict:
    """
    Load the given account_url in a new Page, scrape image, bio, linktr.ee, etc.
    Return a dict with the gathered data.
    """
    data = {
        "tiktok_profile": account_url,
        "profile_image_url": None,
        "bio_urls": [],
        "bio_emails": [],
        "linktree_url": None,
        "social_links": []
    }

    page = await context.new_page()
    try:
        await page.goto(account_url, wait_until="domcontentloaded")
        await asyncio.sleep(3)
    except Exception as e:
        print(f"Error navigating to {account_url}: {e}")
        await page.close()
        return data

    # Scrape image + bio
    info = await scrape_profile_info(page)
    data["profile_image_url"] = info["profile_image_url"]
    data["bio_urls"] = info["bio_urls"]
    data["bio_emails"] = info["bio_emails"]

    # Check if there's a linktree
    anchors = await page.query_selector_all("a[href]")
    linktree_found = None
    for a in anchors:
        href = await a.get_attribute("href")
        if href and "linktr.ee" in href.lower():
            linktree_found = href
            break

    if linktree_found:
        data["linktree_url"] = linktree_found
        # Scrape known social links from linktree
        socials = await open_linktree_and_find_socials(context, linktree_found)
        data["social_links"] = socials

    await page.close()
    return data

async def main_async():
    print("╔╦╗┬┬┌─╔╦╗┌─┐┬┌─  ╔═╗┌─┐┬  ┬  ┌─┐┬ ┬┬┌┐┌┌─┐")
    print(" ║ │├┴┐ ║ │ │├┴┐  ╠╣ │ ││  │  │ │││││││││ ┬")
    print(" ╩ ┴┴ ┴ ╩ └─┘┴ ┴  ╚  └─┘┴─┘┴─┘└─┘└┴┘┴┘└┘└─┘")
    print("  ╔═╗┌─┐┌─┐┬┌─┐┬    ╔═╗┌─┐┬─┐┌─┐┌─┐┌─┐┬─┐  ")
    print("  ╚═╗│ ││  │├─┤│    ╚═╗│  ├┬┘├─┤├─┘├┤ ├┬┘  ")
    print("  ╚═╝└─┘└─┘┴┴ ┴┴─┘  ╚═╝└─┘┴└─┴ ┴┴  └─┘┴└─  ")
    print("      TikTok Following Social Scraper.     ")
    print("    Dan Houseman @neurodivergentnonsense   ")
    print("               ...a follow would be nice   ")
    print(" ")
    # Gather credentials & concurrency
    if len(sys.argv) < 3:
        username = input("TikTok username/email: ")
        password = getpass.getpass("TikTok password: ")
        concurrency = DEFAULT_CONCURRENCY
    else:
        username = sys.argv[1]
        password = sys.argv[2]
        concurrency = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_CONCURRENCY

    print(f"Using concurrency = {concurrency}")

    async with async_playwright() as play:
        # 1) Ensure we have a valid session
        context = await ensure_logged_in(play, username, password)

        # 2) Go to your main profile
        page = await context.new_page()
        profile_url = f"https://www.tiktok.com/@{username}"
        await page.goto(profile_url, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        # 3) Print ASCII Art Banner


        # 4) Expand all 'Following' until 'Show less'
        await expand_following_list(page)

        # 5) Collect followings
        following_accounts = await collect_following_urls(page)
        print(f"\nFound {len(following_accounts)} following accounts.")
        await page.close()

        # 6) Scrape in parallel, batch by concurrency
        tasks = [scrape_profile(context, acc) for acc in following_accounts]
        scraped_data = []
        for i in range(0, len(tasks), concurrency):
            batch = tasks[i : i + concurrency]
            batch_results = await asyncio.gather(*batch)
            scraped_data.extend(batch_results)

        # 7) Save results to JSON
        with open(FOLLOWING_JSON, "w", encoding="utf-8") as f:
            json.dump(scraped_data, f, indent=2, ensure_ascii=False)

        print(f"\nDone scraping. Saved data on {len(scraped_data)} accounts to {FOLLOWING_JSON}.\n")

        # 8) Execute another script (server.py) after scraping finishes
        print("Now running server.py ...")
        subprocess.run(["python", "server.py"])  # or ["python3", "server.py"] on some systems

        # Finally, close context
        await context.close()

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()