"""EPUB procesor za ekstrakciju teksta"""
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import re

class EPUBProcessor:
    def extract_metadata(self, epub_path):
        try:
            book = epub.read_epub(epub_path)
            metadata = {'title': 'Nepoznat naslov', 'author': 'Nepoznat autor', 'language': 'hr'}
            titles = book.get_metadata('DC', 'title')
            if titles: metadata['title'] = titles[0][0]
            creators = book.get_metadata('DC', 'creator')
            if creators: metadata['author'] = creators[0][0]
            return metadata
        except:
            return {'title': 'Greska', 'author': 'Greska', 'language': 'hr'}
    
    def extract_chapters(self, epub_path):
        book = epub.read_epub(epub_path)
        chapters = []
        chapter_index = 0
        
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            try:
                content = item.get_content()
                soup = BeautifulSoup(content, 'html.parser')
                for script in soup(["script", "style"]): script.decompose()
                
                text = soup.get_text(separator='\n', strip=True)
                if len(text) < 100: continue
                
                title = f"Poglavlje {chapter_index + 1}"
                for h_tag in ['h1', 'h2', 'h3']:
                    header = soup.find(h_tag)
                    if header:
                        title = header.get_text(strip=True)
                        break
                
                chapters.append({'id': chapter_index, 'title': title, 'text': text, 'char_count': len(text)})
                chapter_index += 1
            except: continue
        
        return chapters if chapters else [{'id': 0, 'title': 'Kompletan tekst', 'text': 'Nema teksta', 'char_count': 0}]
