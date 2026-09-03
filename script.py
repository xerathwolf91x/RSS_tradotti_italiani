import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import re
import time

CONFIG_FEED = [
    {
        "nome": "Pokémon Database",
        "url": "https://pokemondb.net/news/feed",
        "output": "pokemon_db.xml",
        "parole_chiave": []
    },
    {
        "nome": "Nintendo Life",
        "url": "https://www.nintendolife.com/feeds/news",
        "output": "nintendo_life.xml",
        "parole_chiave": []
    }
]

MAX_ARTICOLI = 5

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
}

def pulisci_testo(testo):
    if not testo:
        return ""
    return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', testo).strip()

def estrai_articolo_completo(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return None
        
        soup = BeautifulSoup(res.text, 'html.parser')
        articolo_body = soup.find('article') or soup.find('div', class_=re.compile(r'content|post-body|entry-content|article-body', re.I))
        
        if not articolo_body:
            return None

        paragrafi = articolo_body.find_all('p')
        testo = "<br><br>".join([p.get_text().strip() for p in paragrafi if len(p.get_text().strip()) > 20])
        return testo if testo else None
    except Exception as e:
        print(f"Errore scraping {url}: {e}")
        return None

def traduci_sicuro(translator, testo):
    """Traduce il testo prevenendo errori 500 o blocchi di rete."""
    if not testo:
        return ""
    try:
        # Pulisce eventuali errori 500 o risposte anomale
        risultato = translator.translate(testo)
        if "Error 500" in risultato or "Server Error" in risultato:
            return testo  # Fallback sul testo originale in caso di errore di Google
        return risultato
    except Exception as e:
        print(f"Avviso traduzione: {e}")
        return testo

def elabora_singolo_feed(config, translator):
    nome = config["nome"]
    url = config["url"]
    file_output = config["output"]
    parole_chiave = config["parole_chiave"]

    print(f"--- Elaborazione avanzata feed: {nome} ---")
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        xml_text = pulisci_testo(response.text)
        root = ET.fromstring(xml_text)
        channel = root.find('channel')
        
        if channel is None:
            return

        items = channel.findall('item')
        items_filtrati = []
        for item in items:
            titolo = item.findtext('title', '')
            desc = item.findtext('description', '')
            if not parole_chiave or any(kw.lower() in titolo.lower() or kw.lower() in desc.lower() for kw in parole_chiave):
                items_filtrati.append(item)

        items_processati = items_filtrati[:MAX_ARTICOLI]

        for child in list(channel):
            if child.tag == 'item':
                channel.remove(child)

        for item in items_processati:
            title_elem = item.find('title')
            desc_elem = item.find('description')
            link_elem = item.find('link')
            
            orig_link = link_elem.text.strip() if link_elem is not None and link_elem.text else "#"
            desc_originale = pulisci_testo(desc_elem.text) if desc_elem is not None and desc_elem.text else ""

            # 1. ENCLOSURE PER ANTEPRIMA
            match_img = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc_originale, re.IGNORECASE)
            if match_img:
                for enc in item.findall('enclosure'):
                    item.remove(enc)
                enc_elem = ET.SubElement(item, 'enclosure')
                enc_elem.set('url', match_img.group(1))
                enc_elem.set('type', 'image/jpeg')

            # 2. TRADUZIONE TITOLO SICURA
            if title_elem is not None and title_elem.text:
                title_elem.text = traduci_sicuro(translator, pulisci_testo(title_elem.text))

            # 3. SCRAPING E TRADUZIONE TESTO
            testo_grezzo = estrai_articolo_completo(orig_link)
            if not testo_grezzo:
                testo_grezzo = re.sub(r'<[^>]*>?', '', desc_originale).strip()

            testo_tradotto = ""
            if testo_grezzo:
                # Blocchi da 1500 caratteri per evitare l'Errore 500 di Google
                blocchi = [testo_grezzo[i:i+1500] for i in range(0, len(testo_grezzo), 1500)]
                for blocco in blocchi:
                    testo_tradotto += traduci_sicuro(translator, blocco) + " "
                    time.sleep(0.5)

            # Video YouTube
            iframes = re.findall(r'<iframe[^>]*>.*?</iframe>|<iframe[^>]*/>', desc_originale, re.IGNORECASE | re.DOTALL)
            blocco_video = "".join(iframes) + "<br><br>" if iframes else ""

            # Dicitura trasparenza AGCOM e Fonte
            dicitura_agcom = (
                f"<br><br><hr><p><small><strong>Trasparenza e rispetto delle fonti:</strong> "
                f"Contenuto tradotto automaticamente per la community italiana. "
                f"Fonte originale e articolo completo: <a href='{orig_link}' target='_blank' rel='noopener'>{orig_link}</a>.</small></p>"
            )

            html_finale = f"{blocco_video}{testo_tradotto.strip()}{dicitura_agcom}"

            if desc_elem is not None:
                desc_elem.text = html_finale

            channel.append(item)

        # Scrittura XML personalizzata per preservare i tag HTML non convertiti
        xml_str = ET.tostring(root, encoding='utf-8').decode('utf-8')
        
        # Sostituisce le entità convertite per restituire HTML puro nell'XML
        xml_str = xml_str.replace('&lt;', '<').replace('&gt;', '>')

        with open(file_output, 'w', encoding='utf-8') as f:
            f.write(xml_str)
            
        print(f"File '{file_output}' generato correttamente in HTML puro.")

    except Exception as e:
        print(f"Errore durante l'elaborazione di {nome}: {e}")

def main():
    translator = GoogleTranslator(source='auto', target='it')
    for feed in CONFIG_FEED:
        elabora_singolo_feed(feed, translator)

if __name__ == "__main__":
    main()
