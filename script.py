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
    },

    {
        "nome": "PokèmonBlog",
        "url": "https://pokemonblog.com/feed/",
        "output": "pokemonblog.xml",
        "parole_chiave": []
    },
    
]

MAX_ARTICOLI = 20

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def pulisci_testo(testo):
    if not testo:
        return ""
    return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', testo).strip()

def traduci_sicuro(translator, testo):
    if not testo:
        return ""
    try:
        risultato = translator.translate(testo)
        if "Error 500" in risultato or "Server Error" in risultato:
            return testo
        return risultato
    except Exception as e:
        print(f"Avviso traduzione: {e}")
        return testo

def elabora_singolo_feed(config, translator):
    nome = config["nome"]
    url = config["url"]
    file_output = config["output"]
    parole_chiave = config["parole_chiave"]

    print(f"--- Generazione Schede News Veloci per: {nome} ---")
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

            # 1. ENCLOSURE PER ANTEPRIMA / IMMAGINE IN EVIDENZA
            match_img = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc_originale, re.IGNORECASE)
            if match_img:
                for enc in item.findall('enclosure'):
                    item.remove(enc)
                enc_elem = ET.SubElement(item, 'enclosure')
                enc_elem.set('url', match_img.group(1))
                enc_elem.set('type', 'image/jpeg')

            # 2. TRADUZIONE TITOLO
            if title_elem is not None and title_elem.text:
                title_elem.text = traduci_sicuro(translator, pulisci_testo(title_elem.text))

            # 3. PULIZIA E TRADUZIONE DELL'ESTRATTO SINTETICO
            soup_desc = BeautifulSoup(desc_originale, 'html.parser')
            
            # Preserva iframe di eventuali video YouTube allegati nell'RSS
            iframes = [str(iframe) for iframe in soup_desc.find_all('iframe')]
            blocco_video = "".join(iframes) + "<br><br>" if iframes else ""

            # Estrae solo il testo senza tag HTML per una traduzione pulita
            testo_estratto_grezzo = soup_desc.get_text().strip()
            testo_estratto_tradotto = traduci_sicuro(translator, testo_estratto_grezzo)

            # 4. BOX GRAFICO CON INVITO ALLA LETTURA SULLA FONTE UFFICIALE
            box_invito_fonte = (
                f"<br><br>"
                f"<div style='background-color: #f8f9fa; border-left: 4px solid #0073aa; padding: 12px 16px; margin: 15px 0;'>"
                f"<p style='margin: 0; font-weight: bold;'>📖 Vuoi approfondire questa notizia?</p>"
                f"<p style='margin: 5px 0 0 0;'>Leggi l'articolo integrale e tutti i dettagli direttamente sul sito di origine: "
                f"<a href='{orig_link}' target='_blank' rel='noopener noreferrer'><strong>Continua la lettura su {nome} &raquo;</strong></a></p>"
                f"</div>"
            )

            # 5. DICITURA TRASPARENZA AGCOM OBBILGATORIA
            dicitura_agcom = (
                f"<br><hr><p><small><strong>Trasparenza e rispetto delle fonti (AGCOM):</strong> "
                f"Contenuto sintetizzato e tradotto automaticamente per la community italiana a scopo informativo. "
                f"Fonte originale: <a href='{orig_link}' target='_blank' rel='noopener'>{orig_link}</a>.</small></p>"
            )

            # Composizione HTML finale dell'articolo
            html_finale = f"{blocco_video}<p>{testo_estratto_tradotto}</p>{box_invito_fonte}{dicitura_agcom}"

            if desc_elem is not None:
                desc_elem.text = html_finale

            channel.append(item)

        # Scrittura XML con estrazione tag HTML pulita
        xml_str = ET.tostring(root, encoding='utf-8').decode('utf-8')
        xml_str = xml_str.replace('&lt;', '<').replace('&gt;', '>')

        with open(file_output, 'w', encoding='utf-8') as f:
            f.write(xml_str)
            
        print(f"File '{file_output}' generato con successo (Formato Scheda News).")

    except Exception as e:
        print(f"Errore durante la generazione per {nome}: {e}")

def main():
    translator = GoogleTranslator(source='auto', target='it')
    for feed in CONFIG_FEED:
        elabora_singolo_feed(feed, translator)

if __name__ == "__main__":
    main()
