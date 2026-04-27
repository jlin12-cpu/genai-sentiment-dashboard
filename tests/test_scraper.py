"""
test_scraper.py
---------------
Unit test for the Google Play Store scraper.
Verifies that the google-play-scraper library can successfully fetch
reviews for the ChatGPT app and that the returned data contains
the expected fields (score, content, at).

Run: python test_scraper.py
Expected output: ✓ Scraper test passed
"""

from google_play_scraper import reviews, Sort

def test_scraper():
    try:
        result, _ = reviews(
            'com.openai.chatgpt',
            lang='en',
            country='us',
            sort=Sort.NEWEST,
            count=10
        )
        assert len(result) == 10, f"Expected 10 reviews, got {len(result)}"
        assert all('score' in r and 'content' in r and 'at' in r for r in result), \
            "Missing expected fields"
        print("✓ Scraper test passed")
    except AssertionError as e:
        print(f"✗ Test failed: {e}")
    except Exception as e:
        print(f"✗ Scraper error: {e}")

test_scraper()