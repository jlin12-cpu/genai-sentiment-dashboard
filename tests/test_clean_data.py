"""
test_clean_data.py
------------------
Unit tests for clean_data.py helper functions.

Tests cover:
  - compute_sentiment: polarity range, empty/None input
  - classify_theme: keyword matching for all four categories,
    priority ordering, edge cases

Run: python test_clean_data.py
Expected output: all tests passed
"""

from notebook.scraper.clean_data import compute_sentiment, classify_theme

def test_compute_sentiment():
    # Positive text should return positive polarity
    assert compute_sentiment("I love this app, it is amazing") > 0, \
        "Positive text should have positive polarity"

    # Negative text should return negative polarity
    assert compute_sentiment("This app is terrible and broken") < 0, \
        "Negative text should have negative polarity"

    # Polarity should be within -1.0 to 1.0
    result = compute_sentiment("This is a test sentence")
    assert -1.0 <= result <= 1.0, \
        f"Polarity {result} out of range [-1.0, 1.0]"

    # Empty string should return 0.0
    assert compute_sentiment("") == 0.0, \
        "Empty string should return 0.0"

    # None should return 0.0
    assert compute_sentiment(None) == 0.0, \
        "None should return 0.0"

    print("  ✓ compute_sentiment passed")

def test_classify_theme():
    # Pricing keywords
    assert classify_theme("I hate the subscription model") == "Pricing/Subscription", \
        "Should detect Pricing/Subscription"
    assert classify_theme("This app is too expensive to upgrade") == "Pricing/Subscription", \
        "Should detect Pricing/Subscription"

    # Bugs keywords
    assert classify_theme("The app keeps crashing on my phone") == "Bugs/Performance", \
        "Should detect Bugs/Performance"
    assert classify_theme("Very slow performance and lag") == "Bugs/Performance", \
        "Should detect Bugs/Performance"

    # Accuracy keywords
    assert classify_theme("It gives wrong answers and is inaccurate") == "Accuracy/Logic Issues", \
        "Should detect Accuracy/Logic Issues"
    assert classify_theme("The information is misleading and unreliable") == "Accuracy/Logic Issues", \
        "Should detect Accuracy/Logic Issues"

    # General (no keywords)
    assert classify_theme("I love this app") == "General", \
        "Should default to General"
    assert classify_theme("Nice app overall") == "General", \
        "Should default to General"

    # Priority: Pricing > Bugs
    assert classify_theme("The app crashes and subscription is expensive") == "Pricing/Subscription", \
        "Pricing should take priority over Bugs"

    # Priority: Pricing > Accuracy
    assert classify_theme("Wrong answers and I had to pay for premium") == "Pricing/Subscription", \
        "Pricing should take priority over Accuracy"

    # Edge cases
    assert classify_theme("") == "General", \
        "Empty string should return General"
    assert classify_theme(None) == "General", \
        "None should return General"

    print("  ✓ classify_theme passed")

def main():
    try:
        test_compute_sentiment()
        test_classify_theme()
        print("✓ All tests passed")
    except AssertionError as e:
        print(f"✗ Test failed: {e}")
    except Exception as e:
        print(f"✗ Error: {e}")

main()