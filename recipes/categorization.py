import re

CATEGORIES = {
    "Frukt & Grönt": [
        "tomat", "gurka", "sallad", "lök", "vitlök", "morot", "potatis", "paprika", "chili", "ingefära",
        "citron", "lime", "apelsin", "äpple", "banan", "bär", "spenat", "ruccola", "kål", "broccoli",
        "blomkål", "svamp", "champinjon", "avokado", "bönor", "linser", "ärtor", "majs", "persilja",
        "dill", "koriander", "basilika", "timjan", "rosmarin", "mynta", "gräslök", "purjolök", "palsternacka",
        "rotselleri", "kålrot", "zucchini", "aubergine", "pumpa", "sparris", "rädisa", "fänkål"
    ],
    "Mejeri & Ost": [
        "mjölk", "grädde", "smör", "ost", "yoghurt", "fil", "creme fraiche", "crème fraiche", "kvarg",
        "keso", "mascarpone", "ricotta", "feta", "halloumi", "mozzarella", "parmesan", "ägg", "margarin"
    ],
    "Kött, Fisk & Fågel": [
        "kyckling", "färs", "nötkött", "fläsk", "skinka", "bacon", "korv", "fisk", "lax", "torsk",
        "räkor", "skaldjur", "tonfisk", "sill", "köttbullar", "biff", "entrecote", "filé", "grytbitar"
    ],
    "Bröd & Bageri": [
        "bröd", "limpa", "fralla", "baguette", "tortilla", "tunnbröd", "knäckebröd", "kex", "skorpor",
        "bullar", "kakor"
    ],
    "Skafferi": [
        "mjöl", "socker", "salt", "peppar", "krydda", "olja", "vinäger", "soja", "fond", "buljong",
        "pasta", "ris", "bulgur", "couscous", "quinoa", "nudlar", "havregryn", "flingor", "müsli",
        "nötter", "frön", "mandlar", "russin", "kakao", "bakpulver", "jäst", "sirap", "honung",
        "senap", "ketchup", "majonnäs", "tomatpuré", "krossade tomater", "passerade tomater",
        "kokosmjölk", "bönor i tetra", "linser i tetra", "ströbröd", "potatismjöl", "maizena"
    ],
    "Frys": [
        "glass", "is", "fryst", "frysta"
    ]
}

def categorize_ingredient(name: str) -> str:
    name_lower = name.lower()
    
    for category, keywords in CATEGORIES.items():
        for keyword in keywords:
            # Check for whole word match or if keyword is a significant part
            if re.search(rf'\b{re.escape(keyword)}\w*', name_lower):
                return category
                
    return "Övrigt"
