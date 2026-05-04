"""
FAQ System for Tulum Botox WhatsApp Bot

Edit the FAQ_DATA below to add, remove, or update your FAQ entries.
Each entry has:
  - keywords: words that trigger this answer (lowercase)
  - question: the question this answers (for your reference)
  - answer: what the bot sends back

The bot uses keyword matching to find the best FAQ. If no FAQ matches
well enough, it falls back to the AI responder.
"""

# ─── Your FAQ Database ───────────────────────────────────────
# ✏️ EDIT THIS LIST to customize your bot's answers!

FAQ_DATA = [

    # ── GREETINGS ────────────────────────────────────────────
    {
        "keywords": ["hola", "hello", "hi", "hey", "buenos", "buenas", "good morning", "good afternoon", "sup", "what's up", "buen dia", "buen día"],
        "question": "Greeting",
        "answer": (
            "Hey there! 👋 Welcome to Tulum Botox!\n\n"
            "We're a luxury aesthetic clinic in Tulum specializing in Botox (Dysport), "
            "dermal fillers, skin rejuvenation, and more. How can we help you? 💉✨\n\n"
            "📅 Book at: tulumbotox.com\n"
            "📍 Tulum Centro & Playa del Carmen"
        ),
    },
    {
        "keywords": ["thank", "thanks", "gracias", "thx", "appreciate", "tysm", "ty"],
        "question": "Thank you",
        "answer": (
            "You're welcome! 😊 We're happy to help!\n\n"
            "If you have any other questions, just ask. "
            "We look forward to seeing you at Tulum Botox! 💉🌴"
        ),
    },
    {
        "keywords": ["español", "spanish", "espanol", "hablan", "inglés", "ingles", "idioma"],
        "question": "Do you speak Spanish?",
        "answer": (
            "¡Claro que sí! Hablamos español e inglés. 🇲🇽🇺🇸\n\n"
            "Puedes escribirnos en el idioma que prefieras. "
            "¿En qué te podemos ayudar?\n\n"
            "Of course! We speak both Spanish and English. Feel free to write in whichever you prefer!"
        ),
    },

    # ── ABOUT / GENERAL ──────────────────────────────────────
    {
        "keywords": ["what is", "about", "who are", "tulum botox", "clinic", "clínica", "sobre", "que es", "qué es"],
        "question": "What is Tulum Botox?",
        "answer": (
            "✨ *Tulum Botox* is a luxury aesthetic clinic in Tulum, Mexico!\n\n"
            "We specialize in:\n"
            "• Botox & Dysport neurotoxins\n"
            "• Dermal fillers (HA, Radiesse, Sculptra, HarmonyCa)\n"
            "• Skin rejuvenation & facials\n"
            "• Body contouring\n"
            "• CO2 laser, threads, rhinomodeling & more!\n\n"
            "Our internationally trained doctors & nurses have 10+ years of experience. "
            "We combine medical excellence with a personalized boutique approach. 💎\n\n"
            "📅 Book: tulumbotox.com\n"
            "📍 Tulum Centro & Playa del Carmen"
        ),
    },
    {
        "keywords": ["where", "location", "located", "address", "find you", "directions", "ubicación", "ubicacion", "donde", "dónde", "maps", "google maps"],
        "question": "Where are you located?",
        "answer": (
            "📍 *We're located in Tulum Centro!*\n\n"
            "Google Maps: https://maps.google.com/?q=20.210726,-87.460243\n\n"
            "We also have a location in *Playa del Carmen (PDC)*. "
            "Book through tulumbotox.com to choose the location nearest you!\n\n"
            "📅 tulumbotox.com"
        ),
    },
    {
        "keywords": ["hours", "open", "schedule", "when", "horario", "horarios", "hora", "appointment", "cita", "available", "availability"],
        "question": "What are your hours?",
        "answer": (
            "🕐 We're available *by appointment*!\n\n"
            "Book directly at: tulumbotox.com\n"
            "Or message us here on WhatsApp: +52-984-156-8826\n\n"
            "We have appointments available at both our *Tulum* and *Playa del Carmen* locations. "
            "Check the website for real-time availability!"
        ),
    },
    {
        "keywords": ["book", "booking", "reserve", "reservation", "appointment", "schedule", "reservar", "reserva", "agendar", "cita"],
        "question": "How do I book?",
        "answer": (
            "📅 *Booking is easy!*\n\n"
            "👉 Go to: *tulumbotox.com*\n"
            "Click \"Book Appointment\" to see availability and schedule your treatment!\n\n"
            "You can also message us directly on WhatsApp and we'll help you find the perfect time. 😊"
        ),
    },
    {
        "keywords": ["doctor", "nurse", "practitioner", "who performs", "trained", "experience", "médico", "doctor", "enfermera", "quien"],
        "question": "Who performs the treatments?",
        "answer": (
            "👨‍⚕️ All treatments are performed by *internationally trained doctors and nurses* "
            "with 10+ years of experience.\n\n"
            "Each practitioner specializes in different treatments and may offer different price points. "
            "Your safety and results are our top priority! 💎"
        ),
    },
    {
        "keywords": ["playa del carmen", "pdc", "playa", "other location", "otra ubicación"],
        "question": "Do you have locations outside Tulum?",
        "answer": (
            "Yes! 🗺️ We have treatment hubs across the Riviera Maya:\n\n"
            "• 📍 *Tulum Centro*\n"
            "• 📍 *Playa del Carmen (PDC)*\n\n"
            "Book through tulumbotox.com to choose the location nearest you!"
        ),
    },

    # ── SERVICES ─────────────────────────────────────────────
    {
        "keywords": ["services", "treatments", "what do you offer", "menu", "servicios", "tratamientos", "que ofrecen", "qué ofrecen", "offerings"],
        "question": "What services do you offer?",
        "answer": (
            "💉 *Tulum Botox Full Treatment Menu:*\n\n"
            "• Botox & Dysport (neurotoxins)\n"
            "• Dermal Fillers (HA, Radiesse, Sculptra, HarmonyCa)\n"
            "• Rhinomodeling (non-surgical nose job)\n"
            "• Threads\n"
            "• Stem Cell IV Therapy\n"
            "• Skin Rejuvenation & Facials\n"
            "• Body Contouring\n"
            "• PRP, Micro-Needling, Dermapen\n"
            "• CO2 Laser\n"
            "• Tattoo Removal\n"
            "• Blepharoplasty\n"
            "• Mole Removal\n"
            "• ...and more!\n\n"
            "Visit tulumbotox.com for the full menu and pricing! 🌐"
        ),
    },
    {
        "keywords": ["botox", "dysport", "neurotoxin", "toxin", "neuromodulator"],
        "question": "What brand of Botox do you use?",
        "answer": (
            "💉 We use *Dysport* — a premium botulinum toxin!\n\n"
            "With 10+ years of experience, we've found Dysport delivers beautiful, "
            "natural-looking results that tend to last *longer* than other brands.\n\n"
            "💰 Price: *135 MXN per unit*\n\n"
            "The number of units depends on the treatment area. "
            "Book a free consultation at tulumbotox.com for an exact quote!"
        ),
    },
    {
        "keywords": ["filler", "fillers", "relleno", "rellenos", "hyaluronic", "ha filler", "juvederm", "allergan"],
        "question": "What filler brands do you use?",
        "answer": (
            "✨ *We use only premium filler brands:*\n\n"
            "• Hyaluronic Acid (HA) fillers — from 8,900 MXN/CC\n"
            "• Allergan / Juvederm\n"
            "• Radiesse (CaHa) — 10,500 MXN\n"
            "• Sculptra — 17,000 MXN\n"
            "• HarmonyCa (2 syringes) — 22,000 MXN\n\n"
            "Each filler suits different areas and goals. "
            "Your doctor will recommend the best option for you! 💎\n\n"
            "📅 Book a free consult: tulumbotox.com"
        ),
    },
    {
        "keywords": ["lip", "lips", "lip filler", "labios", "labio", "lip augmentation"],
        "question": "How much is lip filler?",
        "answer": (
            "💋 *Lip filler starts at 8,900 MXN per CC.*\n\n"
            "Most lips need 1–2 CC depending on your goals and current volume.\n\n"
            "Book a free consultation at tulumbotox.com to find out what's best for you! "
            "Our doctors love creating beautiful, natural-looking lips! 😊"
        ),
    },
    {
        "keywords": ["rhinomodeling", "nose job", "rhinoplasty", "nose filler", "rhinomodelacion", "rinomodelación", "nariz", "nose"],
        "question": "How much does rhinomodeling cost?",
        "answer": (
            "👃 *Rhinomodeling (non-surgical nose job):*\n\n"
            "💰 *9,500 MXN*\n\n"
            "This is a quick, non-invasive procedure that can reshape and refine "
            "the nose with filler — no surgery needed!\n\n"
            "📅 Book at tulumbotox.com"
        ),
    },
    {
        "keywords": ["thread", "threads", "thread lift", "hilos", "hilo", "lifting"],
        "question": "How much do threads cost?",
        "answer": (
            "🧵 *Thread Lift:*\n\n"
            "💰 *7,500 MXN (4 threads)*\n\n"
            "For a custom quote based on your specific needs, "
            "book a free consultation at tulumbotox.com!"
        ),
    },
    {
        "keywords": ["stem cell", "iv therapy", "células madre", "celulas madre", "regenerative", "iv"],
        "question": "Do you offer stem cell therapy?",
        "answer": (
            "🔬 *Yes! We offer cutting-edge Stem Cell IV Therapy:*\n\n"
            "• Face: *9,200 MXN*\n"
            "• IV 50 Million (Body): *28,000 MXN*\n"
            "• IV 100 Million (Body): *53,500 MXN*\n\n"
            "These are regenerative treatments that promote healing and rejuvenation from within. "
            "Book a consultation at tulumbotox.com to learn more!"
        ),
    },
    {
        "keywords": ["facial", "facials", "hydrafacial", "prp", "micro-needling", "microneedling", "peel", "dermapen", "facial treatment"],
        "question": "Do you offer facials?",
        "answer": (
            "✨ *Yes! Our facial treatments:*\n\n"
            "• PRP + Facial — 5,500 MXN\n"
            "• Hydrafacial — 2,000 MXN\n"
            "• Face Peel — 3,000 MXN\n"
            "• Luxe Diamond Glow — 3,500 MXN\n"
            "• Micro-Needling + Facial — 3,700 MXN\n"
            "• Deep Clean Facial — 2,470 MXN\n"
            "• Anti-Acne Facial — 3,500 MXN\n"
            "• Facial Hydration — 2,900 MXN\n"
            "• Hollywood Peel — 2,990 MXN\n\n"
            "Visit tulumbotox.com for the full facial menu! 🌐"
        ),
    },
    {
        "keywords": ["dermapen", "micro needling", "microneedling", "exosomes", "pdrn", "salmon", "vitamin c", "dark spots", "melasma", "manchas"],
        "question": "How much does dermapen/micro-needling cost?",
        "answer": (
            "💉 *Dermapen / Micro-Needling Options:*\n\n"
            "• Dermapen + Hyaluronic Acid — 4,000 MXN\n"
            "• Vitamin C (Dark Spots & Melasma) — 4,000 MXN\n"
            "• PDRN (Luminosity & Rejuvenation) — 6,000 MXN\n"
            "• Exosomes (Rejuvenation) — 8,900 MXN\n"
            "• ADN de Salmón Reyuran — 9,500 MXN\n\n"
            "📅 Book at tulumbotox.com"
        ),
    },
    {
        "keywords": ["laser", "co2", "co2 laser", "tattoo removal", "tattoo", "tatuaje", "laser treatment", "láser"],
        "question": "How much does laser treatment cost?",
        "answer": (
            "⚡ *CO2 Laser Pricing:*\n\n"
            "• Small Area — 4,300 MXN\n"
            "• Medium Area — 9,500 MXN\n"
            "• Large Area — 19,000 MXN\n\n"
            "Tattoo Removal & Laser Hair Removal: By consultation.\n\n"
            "📅 Book a consult at tulumbotox.com"
        ),
    },
    {
        "keywords": ["body contouring", "booty", "butt", "glutes", "body", "contorno", "glúteos", "cuerpo", "booty volume"],
        "question": "How much does body contouring cost?",
        "answer": (
            "💪 *Body Contouring:*\n\n"
            "• Booty Volume (6ML HA) — 23,400 MXN\n\n"
            "Body contouring treatments vary. Book a free consultation at "
            "tulumbotox.com for a personalized quote!"
        ),
    },
    {
        "keywords": ["blepharoplasty", "eyelid", "blefaroplastia", "párpados", "eye lift"],
        "question": "How much is blepharoplasty?",
        "answer": (
            "👁️ *Blepharoplasty (Eyelid Rejuvenation):*\n\n"
            "💰 *4,000 MXN*\n\n"
            "This treatment rejuvenates the eyelid area for a more refreshed, youthful look. "
            "Book a consultation at tulumbotox.com!"
        ),
    },
    {
        "keywords": ["mole", "mole removal", "lunar", "lunares", "remove mole"],
        "question": "Do you offer mole removal?",
        "answer": (
            "Yes! ✅ We offer *mole removal*.\n\n"
            "Book a consultation at tulumbotox.com so our doctor can evaluate "
            "the mole and recommend the best removal method for you."
        ),
    },
    {
        "keywords": ["sculptra", "radiesse", "harmonyca", "harmony ca", "calcium hydroxylapatite", "caha"],
        "question": "What is Sculptra/Radiesse/HarmonyCa?",
        "answer": (
            "💎 *Premium Filler Options:*\n\n"
            "• *Radiesse (CaHa)* — 10,500 MXN — Calcium hydroxylapatite filler, great for deep volume & collagen stimulation\n"
            "• *Sculptra* — 17,000 MXN — Poly-L-lactic acid, stimulates your own collagen over time\n"
            "• *HarmonyCa* (2 syringes) — 22,000 MXN — Hybrid filler combining HA + CaHA for lift and volume\n\n"
            "Your doctor will recommend the best option for your goals! 📅 tulumbotox.com"
        ),
    },
    {
        "keywords": ["rha", "juvederm", "allergan", "brand", "what brand", "which brand"],
        "question": "Do you carry Juvederm / RHA?",
        "answer": (
            "We carry *Allergan (Juvederm)* and other premium HA fillers. ✅\n\n"
            "We do *not* carry RHA at this time.\n\n"
            "Book a free consultation and we'll recommend the best filler for your goals! "
            "📅 tulumbotox.com"
        ),
    },
    {
        "keywords": ["mix filler", "different brands", "had filler", "previous filler", "combinar rellenos", "already have filler"],
        "question": "Can I mix fillers from different brands?",
        "answer": (
            "Generally yes! ✅ Hyaluronic acid (HA) fillers from different brands are compatible.\n\n"
            "If you've had filler elsewhere recently, we recommend waiting *at least 2 weeks* "
            "before getting more.\n\n"
            "Book a free consultation so the doctor can assess and advise you properly. "
            "📅 tulumbotox.com"
        ),
    },

    # ── PRICING ──────────────────────────────────────────────
    {
        "keywords": ["price", "prices", "cost", "how much", "pricing", "rates", "fee", "precio", "precios", "cuanto", "cuánto", "costo", "tarifa"],
        "question": "General pricing question",
        "answer": (
            "💰 *Tulum Botox — Key Prices:*\n\n"
            "• Dysport (Botox): *135 MXN/unit*\n"
            "• HA Filler: *8,900 MXN/CC*\n"
            "• Rhinomodeling: *9,500 MXN*\n"
            "• Threads (4): *7,500 MXN*\n"
            "• Radiesse: *10,500 MXN*\n"
            "• Sculptra: *17,000 MXN*\n"
            "• HarmonyCa (2 syringes): *22,000 MXN*\n"
            "• Hydrafacial: *2,000 MXN*\n"
            "• CO2 Laser (Small): *4,300 MXN*\n\n"
            "_All prices in Mexican Pesos (MXN). CC fee: +5%_\n\n"
            "Full menu at: tulumbotox.com 🌐"
        ),
    },
    {
        "keywords": ["mxn", "pesos", "currency", "usd", "dollars", "moneda", "divisa"],
        "question": "Are prices in MXN?",
        "answer": (
            "Yes! 💰 All prices are in *Mexican Pesos (MXN)*.\n\n"
            "We also accept USD cash. Each practitioner may offer different price points. "
            "Visit tulumbotox.com for the most current pricing!"
        ),
    },
    {
        "keywords": ["consultation", "free consult", "consulta", "free consultation", "quote", "cotización", "cotizacion"],
        "question": "Do you offer free consultations?",
        "answer": (
            "Yes! 🎉 We offer *free consultations*!\n\n"
            "Come in with no commitment — our doctors will review your goals "
            "and recommend the best treatment plan with exact pricing.\n\n"
            "📅 Book at: tulumbotox.com\n"
            "📱 WhatsApp: +52-984-156-8826"
        ),
    },

    # ── PAYMENT ──────────────────────────────────────────────
    {
        "keywords": ["payment", "pay", "cash", "credit card", "card", "wise", "transfer", "pago", "tarjeta", "efectivo", "how to pay", "payment methods"],
        "question": "What payment methods do you accept?",
        "answer": (
            "💳 *We accept:*\n\n"
            "• Credit cards (Visa, Mastercard) — *+5% processing fee*\n"
            "• Cash (USD or MXN pesos) — *no extra fee* ✅\n"
            "• Wise / TransferWise — *no extra fee* ✅\n\n"
            "To avoid the credit card fee, pay with cash or Wise!"
        ),
    },
    {
        "keywords": ["credit card fee", "5%", "surcharge", "cargo", "cargo tarjeta", "card fee"],
        "question": "Is there a credit card fee?",
        "answer": (
            "Yes, credit card payments have a *5% processing fee*. 💳\n\n"
            "To avoid the fee, pay with:\n"
            "• Cash (USD or MXN pesos) ✅\n"
            "• Wise / TransferWise ✅\n\n"
            "No extra fees with those payment methods!"
        ),
    },

    # ── SAFETY & AFTERCARE ───────────────────────────────────
    {
        "keywords": ["safe", "safety", "is it safe", "seguro", "segura", "trust", "trusted", "reliable", "mexico"],
        "question": "Is it safe to get Botox in Mexico?",
        "answer": (
            "Absolutely! ✅ *Yes, it's completely safe at Tulum Botox.*\n\n"
            "• We use only *premium, regulated products* (Dysport, Allergan, Radiesse, etc.)\n"
            "• All treatments performed by *internationally trained doctors & nurses*\n"
            "• *10+ years of experience*\n"
            "• Medical excellence + boutique personalized experience\n\n"
            "Your safety is our #1 priority. 💎"
        ),
    },
    {
        "keywords": ["side effects", "bruising", "swelling", "pain", "efectos secundarios", "hinchazón", "moretones", "dolor", "risk"],
        "question": "What are the side effects?",
        "answer": (
            "Common side effects are minimal:\n\n"
            "• Minor swelling 💧\n"
            "• Slight redness\n"
            "• Occasional bruising\n\n"
            "These typically resolve within *a few hours to a few days*. "
            "We'll give you full aftercare instructions after your treatment! 📋"
        ),
    },
    {
        "keywords": ["hurt", "pain", "painful", "does it hurt", "duele", "dolor", "numbing", "anesthesia"],
        "question": "Does Botox or filler hurt?",
        "answer": (
            "Most clients say it's *very minimal! 😊*\n\n"
            "We use *topical numbing cream* before all injectable treatments. "
            "The procedures are very quick — most describe it as a small pinch that's over fast!\n\n"
            "You're in good hands with our experienced team. 💎"
        ),
    },
    {
        "keywords": ["fly", "travel", "flight", "airplane", "after treatment", "después", "despues", "travel after", "can i fly"],
        "question": "Can I fly after getting Botox or filler?",
        "answer": (
            "✈️ Yes!\n\n"
            "• *Botox/Dysport:* You can fly the *same day*!\n"
            "• *Fillers:* We recommend waiting *24–48 hours* if possible, "
            "but it's generally safe to travel.\n\n"
            "_For 24 hours after treatment, avoid:_\n"
            "• Intense sun exposure ☀️\n"
            "• Alcohol 🍹\n"
            "• Strenuous exercise 🏃"
        ),
    },
    {
        "keywords": ["touch up", "touchup", "retoque", "adjustment", "2 weeks", "follow up"],
        "question": "What about touch-ups?",
        "answer": (
            "Touch-ups are easy! 😊\n\n"
            "• *Botox/Dysport:* Touch-ups can be done after *2 weeks* if needed\n"
            "• *Fillers:* Touch-ups recommended at *2 weeks* — this lets the product settle "
            "so we can fine-tune your results\n\n"
            "We want you to *love* your look! 💎"
        ),
    },
    {
        "keywords": ["first visit", "first time", "primera vez", "what to expect", "que esperar", "how does it work", "process", "new client"],
        "question": "What should I expect on my first visit?",
        "answer": (
            "Welcome! 🎉 Here's what to expect on your first visit:\n\n"
            "1. *Free consultation* — doctor reviews your goals & recommends a treatment plan\n"
            "2. *Numbing cream* — applied before any injections\n"
            "3. *Treatment* — quick and precise\n"
            "4. *Aftercare instructions* — we'll walk you through everything\n\n"
            "The whole visit usually takes *30–45 minutes*. Easy and relaxed! 😊\n\n"
            "📅 Book at tulumbotox.com"
        ),
    },

    # ── BEFORE & AFTER / SOCIAL ──────────────────────────────
    {
        "keywords": ["before after", "before and after", "photos", "pictures", "results", "instagram", "social media", "fotos", "antes y después", "antes y despues", "@tulumbotox"],
        "question": "Can I see before & after photos?",
        "answer": (
            "📸 Yes! Check out our before & after photos:\n\n"
            "👉 Instagram: *@tulumbotox*\n\n"
            "You can also ask us for photos of specific treatments during your consultation! "
            "We're proud of our results. ✨"
        ),
    },

    # ── CONTACT ──────────────────────────────────────────────
    {
        "keywords": ["contact", "reach", "email", "instagram", "website", "contacto", "contactar", "website", "sitio web"],
        "question": "How do I contact you?",
        "answer": (
            "📱 *Contact Tulum Botox:*\n\n"
            "• WhatsApp: +52-984-156-8826\n"
            "• Email: Ally@TulumBotox.com\n"
            "• Website & Booking: tulumbotox.com\n"
            "• Instagram: @tulumbotox\n"
            "• 📍 Tulum Centro & Playa del Carmen"
        ),
    },

    # ── HUMAN HANDOFF ────────────────────────────────────────
    {
        "keywords": ["human", "person", "real person", "agent", "persona", "humano", "team", "talk to someone", "speak to"],
        "question": "I want to talk to a real person",
        "answer": (
            "Of course! 🙌 A team member will get back to you shortly.\n\n"
            "You can also reach us directly:\n"
            "📱 WhatsApp: +52-984-156-8826\n"
            "📧 Email: Ally@TulumBotox.com\n"
            "📅 Book: tulumbotox.com"
        ),
    },
]


# ─── Matching Logic ──────────────────────────────────────────

def find_best_faq_match(user_message: str, threshold: float = 0.35) -> str | None:
    """
    Find the best matching FAQ for a user message.
    Returns the answer string, or None if no good match found.

    Uses keyword overlap scoring — fast and doesn't need any AI API calls.
    """
    message_lower = user_message.lower()
    message_words = set(message_lower.split())

    best_score = 0
    best_answer = None

    for faq in FAQ_DATA:
        keywords = faq["keywords"]
        matches = 0

        for keyword in keywords:
            # Check for keyword as a substring (handles phrases like "how much")
            if keyword in message_lower:
                matches += 1
            # Also check word-level matches
            elif keyword in message_words:
                matches += 1

        if len(keywords) > 0:
            score = matches / len(keywords)

            # Boost score if message is short (likely a direct question)
            if len(message_words) <= 4 and matches > 0:
                score = min(score * 1.5, 1.0)

            if score > best_score:
                best_score = score
                best_answer = faq["answer"]

    if best_score >= threshold:
        return best_answer

    return None


def faq_lookup(keyword: str) -> str | None:
    """Direct keyword lookup — returns the first FAQ that contains the keyword."""
    keyword_lower = keyword.lower()
    for faq in FAQ_DATA:
        if keyword_lower in faq["keywords"]:
            return faq["answer"]
    return None
