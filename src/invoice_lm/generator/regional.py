"""Regional-language invoices for the hard-case test set (milestone 7).

Small shops print the shop name, and often the goods, in the local script,
with numbers, GSTINs and codes in Latin. Hindi (Devanagari) is used for Delhi,
Uttar Pradesh and Rajasthan suppliers, Kannada for Karnataka. Only the text
changes, so the tax maths stays correct by construction. Translations are the
generator's own; they need a native speaker's check before the set is published.
"""

import random

from invoice_lm.generator.data import random_invoice
from invoice_lm.schema import GSTInvoice

SCRIPT_BY_STATE = {"07": "deva", "09": "deva", "08": "deva", "29": "knda"}

NAMES = {
    "deva": {
        "Shree": "श्री", "Sri": "श्री", "Om": "ओम", "Ganesh": "गणेश", "Lakshmi": "लक्ष्मी",
        "Bharat": "भारत", "Sai": "साई", "Annapurna": "अन्नपूर्णा", "Krishna": "कृष्णा",
        "Vinayaka": "विनायक", "Navkar": "नवकार", "Balaji": "बालाजी", "Kaveri": "कावेरी",
        "Sahyadri": "सह्याद्री", "Ganga": "गंगा", "Traders": "ट्रेडर्स",
        "Enterprises": "एंटरप्राइजेज", "Agencies": "एजेंसीज", "Industries": "इंडस्ट्रीज",
        "Distributors": "डिस्ट्रीब्यूटर्स", "Stores": "स्टोर्स", "Suppliers": "सप्लायर्स",
        "Corporation": "कॉर्पोरेशन", "&": "एंड", "Sons": "संस", "Marketing": "मार्केटिंग",
        "Solutions": "सॉल्यूशंस",
    },
    "knda": {
        "Shree": "ಶ್ರೀ", "Sri": "ಶ್ರೀ", "Om": "ಓಂ", "Ganesh": "ಗಣೇಶ", "Lakshmi": "ಲಕ್ಷ್ಮೀ",
        "Bharat": "ಭಾರತ್", "Sai": "ಸಾಯಿ", "Annapurna": "ಅನ್ನಪೂರ್ಣ", "Krishna": "ಕೃಷ್ಣ",
        "Vinayaka": "ವಿನಾಯಕ", "Navkar": "ನವಕಾರ್", "Balaji": "ಬಾಲಾಜಿ", "Kaveri": "ಕಾವೇರಿ",
        "Sahyadri": "ಸಹ್ಯಾದ್ರಿ", "Ganga": "ಗಂಗಾ", "Traders": "ಟ್ರೇಡರ್ಸ್",
        "Enterprises": "ಎಂಟರ್ಪ್ರೈಸಸ್", "Agencies": "ಏಜೆನ್ಸೀಸ್", "Industries": "ಇಂಡಸ್ಟ್ರೀಸ್",
        "Distributors": "ಡಿಸ್ಟ್ರಿಬ್ಯೂಟರ್ಸ್", "Stores": "ಸ್ಟೋರ್ಸ್", "Suppliers": "ಸಪ್ಲೈಯರ್ಸ್",
        "Corporation": "ಕಾರ್ಪೊರೇಷನ್", "&": "ಅಂಡ್", "Sons": "ಸನ್ಸ್", "Marketing": "ಮಾರ್ಕೆಟಿಂಗ್",
        "Solutions": "ಸೊಲ್ಯೂಷನ್ಸ್",
    },
}

GOODS = {
    "deva": {
        "Basmati Rice 25kg Bag": "बासमती चावल 25 किलो बोरी",
        "Refined Sunflower Oil 15L": "रिफाइंड सूरजमुखी तेल 15 लीटर",
        "Toor Dal": "तूर दाल",
        "Masala Tea 1kg": "मसाला चाय 1 किलो",
        "Ball Pen (Box of 50)": "बॉल पेन (50 का डिब्बा)",
        "Cement OPC 53 Grade 50kg": "सीमेंट OPC 53 ग्रेड 50 किलो",
        "TMT Steel Bar 12mm": "टीएमटी सरिया 12mm",
        "Ceiling Fan 1200mm": "छत का पंखा 1200mm",
        "Cotton Shirt": "सूती कमीज़",
        "Leather Shoes": "चमड़े के जूते",
        "Plastic Chair": "प्लास्टिक कुर्सी",
        "Office Table": "ऑफिस मेज़",
        "Freight Charges (GTA)": "भाड़ा शुल्क (GTA)",
    },
    "knda": {
        "Basmati Rice 25kg Bag": "ಬಾಸ್ಮತಿ ಅಕ್ಕಿ 25 ಕೆಜಿ ಚೀಲ",
        "Refined Sunflower Oil 15L": "ಸೂರ್ಯಕಾಂತಿ ಎಣ್ಣೆ 15 ಲೀ",
        "Toor Dal": "ತೊಗರಿ ಬೇಳೆ",
        "Masala Tea 1kg": "ಮಸಾಲಾ ಚಹಾ 1 ಕೆಜಿ",
        "Ball Pen (Box of 50)": "ಬಾಲ್ ಪೆನ್ (50ರ ಡಬ್ಬಿ)",
        "Cement OPC 53 Grade 50kg": "ಸಿಮೆಂಟ್ OPC 53 ಗ್ರೇಡ್ 50 ಕೆಜಿ",
        "TMT Steel Bar 12mm": "ಟಿಎಂಟಿ ಕಬ್ಬಿಣದ ಸರಳು 12mm",
        "Ceiling Fan 1200mm": "ಸೀಲಿಂಗ್ ಫ್ಯಾನ್ 1200mm",
        "Cotton Shirt": "ಹತ್ತಿ ಶರ್ಟ್",
        "Leather Shoes": "ಚರ್ಮದ ಶೂ",
        "Plastic Chair": "ಪ್ಲಾಸ್ಟಿಕ್ ಕುರ್ಚಿ",
        "Office Table": "ಆಫೀಸ್ ಮೇಜು",
        "Freight Charges (GTA)": "ಸಾಗಣೆ ಶುಲ್ಕ (GTA)",
    },
}


def _name(name: str, script: str) -> str:
    """Translate the shop-name words; legal suffixes (Pvt Ltd, LLP) stay in Latin, as printed."""
    table = NAMES[script]
    return " ".join(table.get(w, w) for w in name.split())


def regional_invoice(rng: random.Random, script: str | None = None,
                     max_tries: int = 500) -> tuple[GSTInvoice, str]:
    """A random invoice from a Hindi/Kannada-speaking state, with local-script text."""
    for _ in range(max_tries):
        inv = random_invoice(rng)
        drawn = SCRIPT_BY_STATE.get(inv.supplier.state_code)
        if drawn and (script is None or drawn == script):
            script = drawn
            break
    else:
        raise RuntimeError("no regional supplier drawn")
    out = inv.model_copy(deep=True)
    out.supplier.name = _name(out.supplier.name, script)
    if out.buyer.state_code == out.supplier.state_code and rng.random() < 0.5:
        out.buyer.name = _name(out.buyer.name, script)
    for it in out.line_items:
        it.description = GOODS[script].get(it.description, it.description)
    return out, script
