"""
FAQ system for the Tulum BTX WhatsApp bot.

Edit FAQ_DATA to adjust services, prices, hours, location, or booking flow.
The bot uses keyword matching first, then falls back to the AI responder.
"""

FAQ_DATA = [
    {
        "keywords": [
            "hello", "hi", "hey", "hola", "buenos", "buenas", "good morning",
            "good afternoon", "good evening",
        ],
        "question": "Greeting",
        "answer": (
            "Hi! Welcome to Tulum BTX. We can help with BTX / wrinkle-relaxer "
            "questions, appointment requests, and consultation details. What would "
            "you like to know?"
        ),
    },
    {
        "keywords": ["thank", "thanks", "gracias", "thx", "appreciate"],
        "question": "Thank you",
        "answer": (
            "You're very welcome. If you'd like to book or ask about pricing, "
            "send your preferred date and the area you'd like to treat."
        ),
    },
    {
        "keywords": ["spanish", "español", "espanol", "ingles", "inglés", "hablan"],
        "question": "Languages",
        "answer": (
            "Yes, you can message us in English or Spanish. Si prefieres español, "
            "escríbenos en español y te ayudamos."
        ),
    },
    {
        "keywords": [
            "book", "booking", "appointment", "schedule", "reserve",
            "availability", "available", "consultation", "cita", "agendar",
            "reservar", "disponible", "disponibilidad", "consulta",
        ],
        "question": "How do I book?",
        "answer": (
            "To request an appointment, send your name, preferred date/time, and "
            "the area you're interested in treating. A team member will confirm "
            "availability and next steps."
        ),
    },
    {
        "keywords": [
            "price", "pricing", "cost", "how much", "quote", "units",
            "precio", "cuanto", "cuánto", "costo", "cotizacion", "cotización",
            "unidades",
        ],
        "question": "Pricing",
        "answer": (
            "Pricing depends on the treatment area and provider assessment. Send "
            "the area you'd like treated and, if comfortable, a recent photo; our "
            "team can give you the right quote or consultation details."
        ),
    },
    {
        "keywords": [
            "botox", "btx", "botulinum", "toxin", "neurotoxin",
            "wrinkle", "wrinkles", "lines", "toxina", "arrugas",
            "líneas", "lineas",
        ],
        "question": "What is BTX?",
        "answer": (
            "BTX usually refers to botulinum toxin / wrinkle-relaxer treatments. "
            "It is commonly used to temporarily soften expression lines, and a "
            "qualified provider should confirm whether it's appropriate for you."
        ),
    },
    {
        "keywords": [
            "forehead", "frown", "glabella", "crow", "crow's feet", "crows feet",
            "bunny", "lip flip", "gummy smile", "jaw", "masseter", "chin",
            "neck", "frente", "entrecejo", "patas de gallo", "mandíbula",
            "mandibula", "sonrisa gingival", "menton", "mentón", "cuello",
        ],
        "question": "Treatment areas",
        "answer": (
            "Common BTX areas include forehead lines, frown lines, crow's feet, "
            "bunny lines, lip flip, gummy smile, chin, jaw/masseter, and neck "
            "bands. The provider will confirm the best plan during consultation."
        ),
    },
    {
        "keywords": [
            "how long", "last", "duration", "results", "when see", "cuanto dura",
            "cuánto dura", "resultados", "duracion", "duración",
        ],
        "question": "Results and duration",
        "answer": (
            "Results and duration vary by person, treatment area, dose, and product. "
            "Wrinkle-relaxer effects usually last several months, and your provider "
            "can set realistic expectations during consultation."
        ),
    },
    {
        "keywords": [
            "before", "prepare", "preparation", "alcohol", "blood thinner",
            "antes", "preparar", "preparacion", "preparación",
        ],
        "question": "Before appointment",
        "answer": (
            "Before booking, tell the team if you are pregnant, breastfeeding, have "
            "a neuromuscular condition, active skin infection, allergies, or take "
            "medications that affect bleeding. The provider will decide what is "
            "safe for you."
        ),
    },
    {
        "keywords": [
            "after", "aftercare", "recovery", "rub", "massage", "exercise",
            "despues", "después", "cuidados", "recuperacion", "recuperación",
            "masaje",
        ],
        "question": "Aftercare",
        "answer": (
            "Follow the provider's aftercare instructions. In general, avoid rubbing "
            "or massaging the treated areas right after treatment, because that can "
            "affect where the product settles."
        ),
    },
    {
        "keywords": [
            "safe", "safety", "risk", "risks", "side effect", "side effects",
            "seguro", "segura", "riesgo", "riesgos", "efectos secundarios",
        ],
        "question": "Safety",
        "answer": (
            "BTX should be performed by a qualified, licensed provider using an "
            "approved product from a proper source. The treatment is not risk-free, "
            "so the provider will review suitability, risks, and aftercare with you."
        ),
    },
    {
        "keywords": [
            "pregnant", "pregnancy", "breastfeeding", "nursing", "lactation",
            "embarazada", "embarazo", "lactancia", "amamantando",
        ],
        "question": "Pregnancy or breastfeeding",
        "answer": (
            "Please tell the team before booking if you are pregnant, trying to "
            "become pregnant, or breastfeeding. The provider may recommend waiting "
            "or discussing options directly with your medical clinician."
        ),
    },
    {
        "keywords": [
            "photo", "picture", "send photo", "face photo", "foto", "fotos",
            "imagen", "ver foto",
        ],
        "question": "Photos",
        "answer": (
            "You can send a clear, recent photo if you're comfortable. Please avoid "
            "sending sensitive medical details in WhatsApp; the provider can review "
            "personal health questions during consultation."
        ),
    },
    {
        "keywords": [
            "location", "where", "address", "tulum", "ubicacion", "ubicación",
            "direccion", "dirección", "donde", "dónde",
        ],
        "question": "Location",
        "answer": (
            "We're in Tulum. Send your preferred appointment date and our team will "
            "share the exact appointment details and location information."
        ),
    },
    {
        "keywords": [
            "urgent", "emergency", "reaction", "swelling", "pain", "drooping",
            "vision", "breathing", "swallowing", "urgente", "emergencia",
            "reaccion", "reacción", "hinchazon", "hinchazón", "dolor",
            "respirar", "tragar", "vision", "visión",
        ],
        "question": "Urgent symptoms",
        "answer": (
            "If you have trouble breathing, trouble swallowing, vision changes, "
            "severe swelling, or muscle weakness, seek emergency medical care now. "
            "For non-urgent concerns, send details and a team member will follow up."
        ),
    },
    {
        "keywords": ["human", "person", "real person", "agent", "team", "humano", "persona"],
        "question": "Human handoff",
        "answer": (
            "No problem. A team member will reply as soon as possible. If your "
            "message is urgent or symptom-related, please seek medical care now."
        ),
    },
]


def find_best_faq_match(user_message: str, threshold: float = 0.25) -> str | None:
    """
    Find the best matching FAQ for a user message.
    Returns the answer string, or None if no good match is found.
    """
    message_lower = user_message.lower()
    message_words = set(message_lower.split())

    best_score = 0.0
    best_answer = None

    for faq in FAQ_DATA:
        keywords = faq["keywords"]
        matches = 0

        for keyword in keywords:
            if keyword in message_lower or keyword in message_words:
                matches += 1

        if keywords:
            # Long keyword lists represent alternatives, not a checklist.
            score = matches / min(len(keywords), 4)

            if len(message_words) <= 5 and matches > 0:
                score = min(score * 2.0, 1.0)

            if score > best_score:
                best_score = score
                best_answer = faq["answer"]

    if best_score >= threshold:
        return best_answer

    return None


def faq_lookup(keyword: str) -> str | None:
    """Direct keyword lookup. Returns the first FAQ that contains the keyword."""
    keyword_lower = keyword.lower()
    for faq in FAQ_DATA:
        if keyword_lower in faq["keywords"]:
            return faq["answer"]
    return None
