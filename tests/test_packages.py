from google_play_scraper import reviews, Sort

apps = {
    'ChatGPT':           'com.openai.chatgpt',
    'Claude':            'com.anthropic.claude',
    'Google_Gemini':     'com.google.android.apps.bard',
    'Microsoft_Copilot': 'com.microsoft.copilot',
    'Perplexity':        'ai.perplexity.app.android',
}

for name, pkg in apps.items():
    try:
        result, _ = reviews(pkg, lang='en', country='us', sort=Sort.NEWEST, count=1)
        print(f'✓ {name}: {pkg}')
    except Exception as e:
        print(f'✗ {name}: {e}')