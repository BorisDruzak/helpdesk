"""Vendor the reference's OFL fonts for a self-contained local prototype."""
from pathlib import Path
import re
from urllib.request import Request, urlopen

root = Path(__file__).resolve().parents[1]
folder = root / 'public' / 'fonts'
folder.mkdir(parents=True, exist_ok=True)
url = 'https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;650;700;750;800&family=Sora:wght@500;600;650;700&display=swap'
request = Request(url, headers={'User-Agent': 'Mozilla/5.0 Chrome/124.0.0.0 Safari/537.36'})
css = urlopen(request, timeout=30).read().decode()
urls = list(dict.fromkeys(re.findall(r'url\((https://[^)]+)\)', css)))
for i, asset_url in enumerate(urls):
    suffix = '.woff2' if '.woff2' in asset_url else '.woff'
    name = f'font-{i}{suffix}'
    (folder / name).write_bytes(urlopen(asset_url, timeout=30).read())
    css = css.replace(asset_url, f'/fonts/{name}')
(folder / 'fonts.css').write_text(css, encoding='utf-8')
for family in ('manrope', 'sora'):
    license_url = f'https://raw.githubusercontent.com/google/fonts/main/ofl/{family}/OFL.txt'
    (folder / f'{family}-OFL.txt').write_bytes(urlopen(license_url, timeout=30).read())
print(f'Vendored {len(urls)} font files and both OFL licenses.')
