import xml.etree.ElementTree as ET
import requests
from deep_translator import GoogleTranslator
import re

# CONFIGURAZIONE FEED
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

MAX_ARTICOLI = 10

def pulisci_xml(testo):
    if not testo:
        return ""
    # Rimuove caratteri di controllo non validi mantenendo l'HTML integro
    return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', testo).strip()

def elabora_singolo_feed(config, translator):
    nome = config["nome"]
    url = config["url"]
    file_output = config["output"]
    parole_chiave = config["parole_chiave"]

    print(f"--- Elaborazione feed: {nome} ---")
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        xml_clean = pulisci_xml(response.text)
        root = ET.fromstring(xml_clean)
        channel = root.find('channel')
        
        if channel is None:
            print(f"Errore: Canale non trovato per {nome}.")
            return

        items = channel.findall('item')
        
        # Filtro opzionale per parole chiave
        items_filtrati = []
        for item in items:
            titolo = item.findtext('title', '')
            desc = item.findtext('description', '')
            
            if not parole_chiave:
                items_filtrati.append(item)
            elif any(kw.lower() in titolo.lower() or kw.lower() in desc.lower() for kw in parole_chiave):
                items_filtrati.append(item)

        items_processati = items_filtrati[:MAX_ARTICOLI]

        # Svuota il canale originale per ricostruirlo
        for child in list(channel):
            if child.tag == 'item':
                channel.remove(child)

        for item in items_processati:
            title_elem = item.find('title')
            desc_elem = item.find('description')
            link_elem = item.find('link')
            
            orig_link = link_elem.text.strip() if link_elem is not None and link_elem.text else "#"
            desc_originale = pulisci_xml(desc_elem.text) if desc_elem is not None and desc_elem.text else ""

            # --- 1. ESTRAZIONE IMMAGINE DI COPERTINA (ENCLOSURE PER FEEDZY) ---
            img_url = None
            match_img = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc_originale, re.IGNORECASE)
            if match_img:
                img_url = match_img.group(1)
            
            # Se trova un'immagine, imposta il tag <enclosure> per la Featured Image
            if img_url:
                for enc in item.findall('enclosure'):
                    item.remove(enc)
                enc_elem = ET.SubElement(item, 'enclosure')
                enc_elem.set('url', img_url)
                enc_elem.set('type', 'image/jpeg')

            # --- 2. TRADUZIONE TITOLO ---
            if title_elem is not None and title_elem.text:
                titolo_pulito = pulisci_xml(title_elem.text)
                try:
                    title_elem.text = translator.translate(titolo_pulito)
                except Exception as e:
                    print(f"Errore traduzione titolo ({nome}): {e}")
                    title_elem.text = titolo_pulito

            # --- 3. CONSERVAZIONE MEDIA (IFRAME YOUTUBE & IMG) E TRADUZIONE TESTO ---
            if desc_elem is not None and desc_originale:
                # Estrae gli iframe (video YouTube) e le immagini dal codice originale
                iframes = re.findall(r'<iframe[^>]*>.*?</iframe>|<iframe[^>]*/>', desc_originale, re.IGNORECASE | re.DOTALL)
                immagini = re.findall(r'<img[^>]*>', desc_originale, re.IGNORECASE)

                # Isola e traduce solo la parte testuale
                testo_solo = re.sub(r'<[^>]*>?', '', desc_originale).strip()
                try:
                    testo_tradotto = translator.translate(testo_solo) if testo_solo else ""
                except Exception as e:
                    print(f"Errore traduzione testo ({nome}): {e}")
                    testo_tradotto = testo_solo

                # Blocco multimediale in testa (Video YouTube + Immagini)
                blocco_media = ""
                if iframes:
                    blocco_media += "".join(iframes) + "<br><br>"
                if immagini:
                    blocco_media += "".join(immagini) + "<br><br>"

                disclaimer = f"<br><br>(Tradotto automaticamente. Fonte originale: <a href='{orig_link}' target='_blank'>{orig_link}</a>)"
                
                # Assemblaggio finale del contenuto dell'articolo
                desc_elem.text = f"{blocco_media}{testo_tradotto}{disclaimer}"

            channel.append(item)

        # Salvataggio XML
        tree = ET.ElementTree(root)
        tree.write(file_output, encoding="utf-8", xml_declaration=True)
        print(f"File '{file_output}' generato con successo (Video, Immagini ed Enclosure inclusi).")

    except Exception as e:
        print(f"Errore durante l'elaborazione di {nome}: {e}")

def main():
    translator = GoogleTranslator(source='auto', target='it')
    for feed in CONFIG_FEED:
        elabora_singolo_feed(feed, translator)

if __name__ == "__main__":
    main()
