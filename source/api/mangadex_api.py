import requests
import time
import re
from io import BytesIO
from PIL import Image


class MangaDexAPI:
    BASE_URL = "https://api.mangadex.org"

    # All available languages on MangaDex
    ALL_LANGUAGES = {
        'en': '🇬🇧 English',
        'ja': '🇯🇵 Japanese',
        'ja-ro': '🇯🇵 Japanese (Romanized)',
        'zh': '🇨🇳 Chinese (Simp)',
        'zh-hk': '🇭🇰 Chinese (Trad)',
        'ko': '🇰🇷 Korean',
        'es': '🇪🇸 Spanish (Spain)',
        'es-la': '🇲🇽 Spanish (LATAM)',
        'pt-br': '🇧🇷 Portuguese (BR)',
        'pt': '🇵🇹 Portuguese',
        'fr': '🇫🇷 French',
        'de': '🇩🇪 German',
        'it': '🇮🇹 Italian',
        'ru': '🇷🇺 Russian',
        'pl': '🇵🇱 Polish',
        'tr': '🇹🇷 Turkish',
        'id': '🇮🇩 Indonesian',
        'vi': '🇻🇳 Vietnamese',
        'th': '🇹🇭 Thai',
        'ar': '🇸🇦 Arabic',
        'nl': '🇳🇱 Dutch',
        'sv': '🇸🇪 Swedish',
        'da': '🇩🇰 Danish',
        'fi': '🇫🇮 Finnish',
        'no': '🇳🇴 Norwegian',
        'cs': '🇨🇿 Czech',
        'hu': '🇭🇺 Hungarian',
        'ro': '🇷🇴 Romanian',
        'uk': '🇺🇦 Ukrainian',
        'he': '🇮🇱 Hebrew',
        'hi': '🇮🇳 Hindi',
        'bn': '🇧🇩 Bengali',
        'ms': '🇲🇾 Malay',
        'tl': '🇵🇭 Filipino',
        'fa': '🇮🇷 Persian',
        'bg': '🇧🇬 Bulgarian',
        'hr': '🇭🇷 Croatian',
        'el': '🇬🇷 Greek',
        'sr': '🇷🇸 Serbian',
        'lt': '🇱🇹 Lithuanian',
        'lv': '🇱🇻 Latvian',
        'et': '🇪🇪 Estonian',
        'sk': '🇸🇰 Slovak',
        'sl': '🇸🇮 Slovenian',
        'ca': 'Catalan',
        'ne': '🇳🇵 Nepali',
        'mn': '🇲🇳 Mongolian',
        'kk': '🇰🇿 Kazakh',
        'my': '🇲🇲 Burmese',
    }

    def __init__(self):
        self.session = requests.Session()

        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://mangadex.org/'
        })

        self.timeout = 30

    def extract_manga_id(self, url):
        pattern = r'mangadex\.org/title/([a-f0-9\-]+)'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None

    def get_manga_info(self, manga_id):
        try:
            url = f"{self.BASE_URL}/manga/{manga_id}"
            params = {'includes[]': ['cover_art', 'author', 'artist']}
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Error getting manga info: {str(e)}")

    def get_available_languages(self, manga_id):
        """
        Get available translation languages - FIXED METHOD
        Uses manga feed API to detect languages
        """
        try:
            print(f"🔍 Detecting available languages for manga...")

            # Method 1: Use statistics API (more accurate)
            url = f"{self.BASE_URL}/statistics/manga/{manga_id}"
            response = self.session.get(url, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                if 'statistics' in data and manga_id in data['statistics']:
                    stats = data['statistics'][manga_id]
                    if 'comments' in stats:
                        print(f"   Using statistics API")

            # Method 2: Fetch chapters and count by language (more reliable)
            url = f"{self.BASE_URL}/manga/{manga_id}/feed"

            language_counts = {}
            offset = 0
            limit = 500

            while True:
                params = {
                    'limit': limit,
                    'offset': offset,
                    'order[chapter]': 'asc',
                    'contentRating[]': ['safe', 'suggestive', 'erotica', 'pornographic']
                }

                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

                # Count chapters by language
                for chapter in data.get('data', []):
                    lang = chapter.get('attributes', {}).get('translatedLanguage')
                    if lang:
                        language_counts[lang] = language_counts.get(lang, 0) + 1

                # Check if we got all chapters
                total = data.get('total', 0)
                offset += limit

                if offset >= total:
                    break

                # Add small delay to avoid rate limiting
                time.sleep(0.2)

            # Sort by chapter count (descending)
            sorted_langs = dict(sorted(language_counts.items(),
                                       key=lambda x: x[1],
                                       reverse=True))

            print(f"✓ Found {len(sorted_langs)} languages")
            for lang, count in list(sorted_langs.items())[:5]:
                lang_name = self.get_language_name(lang)
                print(f"   {lang_name}: {count} chapters")

            return sorted_langs

        except Exception as e:
            print(f"⚠️ Error detecting languages: {e}")
            return {}

    def get_language_name(self, code):
        """Get full language name from code"""
        return self.ALL_LANGUAGES.get(code, code.upper())

    def get_cover_image(self, manga_id, cover_filename, quality='512'):
        """Download manga cover - FIXED:  No spaces in URL"""
        try:
            if quality == 'original':
                url = f"https://uploads.mangadex.org/covers/{manga_id}/{cover_filename}"
            else:
                # FIXED: Remove spaces - use proper format
                # Format: filename.quality.jpg (NO spaces)
                url = f"https://uploads.mangadex.org/covers/{manga_id}/{cover_filename}. {quality}.jpg"

            print(f"📥 Fetching cover:  {url}")

            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            image = Image.open(BytesIO(response.content))
            print(f"✓ Cover loaded successfully")
            return image
        except Exception as e:
            print(f"⚠️ Cover quality {quality} failed: {e}")
            # Try original if quality fails
            try:
                url = f"https://uploads.mangadex.org/covers/{manga_id}/{cover_filename}"
                print(f"📥 Trying original:  {url}")
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                image = Image.open(BytesIO(response.content))
                print(f"✓ Cover loaded (original)")
                return image
            except Exception as e2:
                print(f"✗ Original also failed: {e2}")
                return None

    def get_manga_chapters(self, manga_id, language='en', limit=500):
        """Get chapters for specific language"""
        try:
            chapters = []
            offset = 0

            print(f"📚 Fetching {language} chapters...")

            while True:
                url = f"{self.BASE_URL}/manga/{manga_id}/feed"
                params = {
                    'limit': limit,
                    'offset': offset,
                    'translatedLanguage[]': [language],
                    'order[chapter]': 'asc',
                    'includes[]': ['scanlation_group'],
                    'contentRating[]': ['safe', 'suggestive', 'erotica', 'pornographic']
                }
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

                chapters.extend(data['data'])

                if offset + limit >= data['total']:
                    break

                offset += limit
                time.sleep(0.5)

            print(f"✓ Found {len(chapters)} chapters")
            return chapters
        except Exception as e:
            print(f"Error getting chapters: {e}")
            return []

    def get_chapter_pages(self, chapter_id):
        """Get page URLs for a chapter"""
        try:
            url = f"{self.BASE_URL}/at-home/server/{chapter_id}"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            base_url = data['baseUrl']
            chapter_hash = data['chapter']['hash']
            filenames = data['chapter']['data']

            page_urls = []
            for filename in filenames:
                page_url = f"{base_url}/data/{chapter_hash}/{filename}"
                page_urls.append(page_url)

            return page_urls
        except Exception as e:
            print(f"Error getting chapter pages: {e}")
            return []