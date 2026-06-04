import zipfile, os, re, logging, functools
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.WARNING)

class EPUBProcessor:
    def extract_metadata(self, epub_path):
        try:
            with zipfile.ZipFile(epub_path, 'r') as zf:
                for f in zf.namelist():
                    if f.endswith('.opf'):
                        soup = BeautifulSoup(zf.read(f), 'xml')
                        title = soup.find('dc:title')
                        author = soup.find('dc:creator')
                        lang_tag = soup.find('dc:language')
                        lang = lang_tag.text if lang_tag else 'hr'
                        return {
                            'title': title.text if title else 'Nepoznat naslov',
                            'author': author.text if author else 'Nepoznat autor',
                            'language': lang
                        }
            return {'title':'Nepoznat naslov','author':'Nepoznat autor','language':'hr'}
        except Exception as e:
            logging.warning(f"Metadata error: {e}")
            return {'title':'Greska','author':'Greska','language':'hr'}
    
    @functools.lru_cache(maxsize=5)
    def extract_chapters_cached(self, epub_path, mtime):
        return self._extract_chapters(epub_path)
    
    def extract_chapters(self, epub_path):
        mtime = os.path.getmtime(epub_path) if os.path.exists(epub_path) else 0
        return self.extract_chapters_cached(epub_path, mtime)
    
    def _extract_chapters(self, epub_path):
        chapters = []
        try:
            with zipfile.ZipFile(epub_path, 'r') as zf:
                html_files = [f for f in zf.namelist()
                            if f.endswith(('.html','.xhtml','.htm'))
                            and 'nav' not in f.lower()
                            and 'toc' not in f.lower()
                            and 'cover' not in f.lower()]
                
                for idx, html_file in enumerate(html_files):
                    try:
                        soup = BeautifulSoup(zf.read(html_file), 'html.parser')
                        for tag in soup(['script','style','nav']): tag.decompose()
                        text = soup.get_text(separator='\n', strip=True)
                        text = re.sub(r'\n\s*\n', '\n\n', text)
                        text = re.sub(r'[ \t]+', ' ', text)
                        
                        if len(text) < 100: continue
                        
                        title = f"Poglavlje {idx+1}"
                        for h in ['h1','h2','h3','title']:
                            htag = soup.find(h)
                            if htag and len(htag.get_text(strip=True)) > 2:
                                title = htag.get_text(strip=True)[:100]
                                break
                        
                        chapters.append({
                            'id': len(chapters),
                            'title': title,
                            'text': text,
                            'char_count': len(text)
                        })
                    except Exception as e:
                        logging.warning(f"Chapter {html_file}: {e}")
        except Exception as e:
            logging.error(f"EPUB read error: {e}")
        
        return chapters
