import xml.etree.ElementTree as ET
import requests
from deep_translator import GoogleTranslator
import re

# CONFIGURAZIONE DEI FEED
# Aggiungi qui tutti i feed che vuoi gestire indicando URL e nome del file output
CONFIG_FEED = [
    {
        "nome": "Pokémon Database",
        "url": "https://pokemondb.net/news/feed",
        "output": "pokemon_db.xml",
        "parole_chiave": []  # Es. ["Legends: Z-A", "Switch 2"] oppure [] per tutto
    },
    {
        "nome": "Nintendo Life",
        "url": "https://www.nintendolife.com/feeds/news",
        "output": "nintendo_life.xml",
        "parole_chiave": []
    }
    # Puoi aggiungere altri feed seguendo la stessa struttura
]

MAX_ARTICOLI = 10

def sanifica_testo(testo):
    if not testo:
        return ""
    testo_pulito = re.sub(r'<[^>]*>?', '', testo)
    return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', testo_pulito).strip()

def elabora_singolo_feed(config, translator):
    nome = config["nome"]
    url = config["url"]
    file_output = config["output"]
    parole_chiave = config["parole_chiave"]

    print(f"--- Inizio elaborazione feed: {nome} ---")
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        xml_clean = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', response.text)
        root = ET.fromstring(xml_clean)
        channel = root.find('channel')
        
        if channel is None:
            print(f"Errore: Impossibile trovare il canale nell'XML per {nome}.")
            return

        items = channel.findall('item')
        
        # Filtro parole chiave
        items_filtrati = []
        for item in items:
            titolo = item.findtext('title', '')
            desc = item.findtext('description', '')
            
            if not parole_chiave:
                items_filtrati.append(item)
            elif any(kw.lower() in titolo.lower() or kw.lower() in desc.lower() for kw in parole_chiave):
                items_filtrati.append(item)

        items_processati = items_filtrati[:MAX_ARTICOLI]

        # Rimuovi item originali per ricostruire il canale pulito
        for child in list(channel):
            if child.tag == 'item':
                channel.remove(child)

        for item in items_processati:
            title_elem = item.find('title')
            desc_elem = item.find('description')
            link_elem = item.find('link')
            
            orig_link = link_elem.text.strip() if link_elem is not None and link_elem.text else "#"
            
            # Traduzione Titolo
            if title_elem is not None and title_elem.text:
                titolo_pulito = sanifica_testo(title_elem.text)
                try:
                    title_elem.text = translator.translate(titolo_pulito)
                except Exception as e:
                    print(f"Errore traduzione titolo ({nome}): {e}")
                    title_elem.text = titolo_pulito

            # Traduzione Descrizione
            if desc_elem is not None and desc_elem.text:
                desc_pulita = sanifica_testo(desc_elem.text)
                try:
                    testo_tradotto = translator.translate(desc_pulita)
                    disclaimer = f"\n\n(Tradotto automaticamente. Fonte originale: {orig_link})"
                    desc_elem.text = testo_tradotto + disclaimer
                except Exception as e:
                    print(f"Errore traduzione descrizione ({nome}): {e}")
                    desc_elem.text = desc_pulita

            channel.append(item)

        # Salvataggio file XML specifico
        tree = ET.ElementTree(root)
        tree.write(file_output, encoding="utf-8", xml_declaration=True)
        print(f"File '{file_output}' salvato correttamente ({len(items_processati)} articoli).")

    except Exception as e:
        print(f"Errore durante l'elaborazione di {nome}: {e}")

def main():
    translator = GoogleTranslator(source='auto', target='it')
    for feed in CONFIG_FEED:
        elabora_singolo_feed(feed, translator)

if __name__ == "__main__":
    main()
