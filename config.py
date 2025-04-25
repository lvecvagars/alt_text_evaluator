# Analīzes konfigurācijas vērtības

# Maksimālais pieļaujamais ALT teksta garums
MAX_ALT_LENGTH = 150

# Minimālais garums, zem kura parādīt brīdinājumu par īsu tekstu
MIN_ALT_LENGTH_THRESHOLD = 5

# Frāzes, kas ALT tekstā nav vēlamas (īpaši sākumā vai kā vienīgais saturs)
# Pārbaude notiks ar .startswith() vai precīzu sakritību (case-insensitive)
FORBIDDEN_PHRASES = [
    "attēls par", "bilde par", "picture of", "image of", 
    "logo", "ikona", "grafiks", "diagramma", "foto" 
]

# User-Agent string, ko izmantot HTTP pieprasījumos
# Ieteicams norādīt kontaktinformāciju vai saiti uz rīka aprakstu
USER_AGENT = 'Mozilla/5.0 (compatible; AltTextCheckerBot/1.0; +http://example.com/alt-text-checker-info)' 

# Noklusētais HTTP pieprasījuma laika limits (sekundēs)
REQUEST_TIMEOUT = 15