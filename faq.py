"""
FAQ System for Rent A Scooter Tulum WhatsApp Bot

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
        "keywords": ["hola", "hello", "hi", "hey", "buenos", "buenas", "good morning", "good afternoon", "sup", "what's up"],
        "question": "Greeting",
        "answer": (
            "Hey there! 👋 Welcome to Rent A Scooter Tulum!\n\n"
            "How can we help you today? Whether you want to book a scooter, "
            "ATV, or car — check prices, or have any questions — just ask! 🛵"
        ),
    },
    {
        "keywords": ["thank", "thanks", "gracias", "thx", "appreciate"],
        "question": "Thank you",
        "answer": (
            "You're welcome! 😊 Happy to help!\n\n"
            "If you need anything else, just send us a message. "
            "Enjoy Tulum! 🌴🛵"
        ),
    },
    {
        "keywords": ["español", "spanish", "espanol", "hablan", "inglés", "ingles"],
        "question": "Do you speak Spanish?",
        "answer": (
            "¡Claro que sí! Hablamos español e inglés. 🇲🇽🇺🇸\n\n"
            "Puedes escribirnos en el idioma que prefieras. "
            "¿En qué te podemos ayudar?"
        ),
    },

    # ── RENTAL PROCESS & BOOKING ─────────────────────────────
    {
        "keywords": ["how", "rent", "process", "book", "reserve", "reservation", "rentar", "reservar", "como", "cómo"],
        "question": "What is the scooter rental process?",
        "answer": (
            "Renting with us is super easy! 🛵\n\n"
            "Step 1: Check out our website for pricing and availability:\n"
            "👉 rentscootertulum.com\n"
            "Step 2: Pick your ride and lock in your reservation\n"
            "Step 3: Fill out the waiver and make your payment\n"
            "Step 4: Pick up your scooter — and start exploring!\n\n"
            "No stress. Just fast, reliable service. Ready to book?"
        ),
    },
    {
        "keywords": ["walk in", "show up", "without reserving", "sin reservar", "walk-in", "just come"],
        "question": "Can we just show up without reserving?",
        "answer": (
            "Please make a reservation before arriving! It helps us prepare "
            "your scooter in advance — and lets you complete everything "
            "comfortably indoors with A/C and no mosquitoes. 😄\n\n"
            "Just message us here to reserve — takes 2 minutes!"
        ),
    },
    {
        "keywords": ["advance", "ahead", "anticipation", "high season", "temporada alta", "how early"],
        "question": "How early should I book during high season?",
        "answer": (
            "Booking 1–2 weeks in advance is ideal during high season! 📆\n\n"
            "We get busy, so reserving early guarantees you get the scooter "
            "you want. Just send us your dates and we'll lock it in!"
        ),
    },
    {
        "keywords": ["online", "book online", "reservar en línea", "en linea"],
        "question": "Can I book online?",
        "answer": (
            "Absolutely! Head to our booking link to see pricing and availability:\n"
            "👉 rentscootertulum.com\n\n"
            "You can select your dates, vehicle type, and delivery location to get exact pricing. 📲\n\n"
            "Or just message us your dates here and we'll get you set up!"
        ),
    },

    # ── PRICING ──────────────────────────────────────────────
    {
        "keywords": ["price", "cost", "how much", "rate", "pricing", "precio", "cuanto", "cuánto", "scooter price"],
        "question": "How much does it cost to rent a scooter?",
        "answer": (
            "Scooter rentals start at 400 MXN and go up to 1,500 MXN per day, "
            "depending on rental length and season. 🛵\n\n"
            "Longer rentals = better daily rate! 💰\n\n"
            "We also offer ATVs (from 900 MXN/day), electric scooters, and cars.\n\n"
            "Delivery to your hotel/Airbnb is available for an extra fee.\n\n"
            "For exact pricing based on your dates and delivery location, check out our booking link:\n"
            "👉 rentscootertulum.com\n\n"
            "Or message us your dates for a fast quote!"
        ),
    },
    {
        "keywords": ["atv price", "atv cost", "cuatrimoto precio", "atv rate", "atv how much"],
        "question": "How much does it cost to rent an ATV?",
        "answer": (
            "ATV rentals range from 900 MXN to 2,200 MXN per day, "
            "depending on how many days you rent. 🏍️\n\n"
            "Want something different? We also have scooters (from 400 MXN/day), electric scooters, and cars!\n\n"
            "Delivery available for an extra fee.\n\n"
            "For exact pricing based on your dates, check our booking link:\n"
            "👉 rentscootertulum.com\n\n"
            "Or message us your dates for a quick quote!"
        ),
    },
    {
        "keywords": ["season", "temporada", "price change", "discount", "descuento"],
        "question": "Do prices change by season?",
        "answer": (
            "Yes! Prices are a bit higher during high season and discounted "
            "for longer rentals. 📈\n\n"
            "The best way to get today's rate is to message us your dates "
            "and we'll send you a quick quote!"
        ),
    },
    {
        "keywords": ["dollar", "usd", "peso", "currency", "moneda", "dólar"],
        "question": "Can I pay in USD or pesos?",
        "answer": (
            "You can pay in either USD or MXN (pesos) — whatever works "
            "best for you! 💵"
        ),
    },
    {
        "keywords": ["long term", "monthly", "long-term", "mensual", "largo plazo", "month"],
        "question": "Do you offer long-term or monthly rentals?",
        "answer": (
            "Yes! We offer long-term and monthly rentals. 📅\n\n"
            "Head to our booking link, select your dates, and you'll "
            "see the exact cost right away:\n"
            "👉 rentscootertulum.com\n\n"
            "The longer you rent, the better the daily rate!"
        ),
    },

    # ── PAYMENT & DEPOSIT ────────────────────────────────────
    {
        "keywords": ["pay", "payment", "card", "venmo", "cash", "credit", "pago", "pagar", "tarjeta", "efectivo"],
        "question": "How can I pay?",
        "answer": (
            "We accept Venmo, cash, and credit cards. 💳\n\n"
            "Credit cards have a 5% processing fee. Venmo and cash have no extra fees!\n\n"
            "You can pay in USD or MXN — whatever works best for you."
        ),
    },
    {
        "keywords": ["deposit", "passport", "depósito", "deposito", "pasaporte", "hold", "leave"],
        "question": "Do I need to leave my passport or a deposit?",
        "answer": (
            "Nope! 🙌 You don't need to leave your passport, ID, or cash.\n\n"
            "We simply place a credit card on file (Visa or MasterCard) for your rental — just a $0.50 authorization. "
            "That's it — safe, easy, and secure.\n\n"
            "No credit card? You can leave a $250 USD cash deposit or your passport instead.\n\n"
            "We're the only rental company in Tulum with NO deposits!"
        ),
    },
    {
        "keywords": ["no credit card", "without card", "sin tarjeta", "no card"],
        "question": "Can I rent without a credit card?",
        "answer": (
            "Yes! But you'll need to leave a $250 USD cash deposit or your passport "
            "as an alternative. 🪪\n\n"
            "With a credit card on file (Visa or MasterCard only) it's much simpler — just $0.50!\n\n"
            "Note: Debit cards, prepaid cards, Revolut, and Wise cards are not accepted for the card-on-file option."
        ),
    },
    {
        "keywords": ["pay end", "pay later", "pagar al final", "pay after"],
        "question": "Can I pay at the end of the rental?",
        "answer": (
            "Yes! Payment can be made at the end of your rental. ✅\n\n"
            "Just let us know your preference when you book!"
        ),
    },

    # ── SCOOTER DETAILS ──────────────────────────────────────
    {
        "keywords": ["scooter", "about", "tell me", "details", "info", "información", "detalles"],
        "question": "Tell me about the scooters",
        "answer": (
            "Here's what you get with every scooter rental:\n\n"
            "🩖 Two helmets included (required by law)\n"
            "⛽ Full tank of gas (just return it full)\n"
            "🛵 2022 model or newer — smooth, reliable rides\n"
            "🎨 Variety of colors and styles\n"
            "🧳 Trunk for extra storage\n"
            "📍 Built-in GPS tracker\n\n"
            "Every scooter is clean, safe, and ready to ride!"
        ),
    },

    # ── ATV DETAILS ──────────────────────────────────────────
    {
        "keywords": ["atv", "cuatrimoto", "quad", "four wheeler", "all terrain"],
        "question": "Tell me about the ATVs",
        "answer": (
            "Our ATVs are perfect for Tulum's roads! 🏍️\n\n"
            "Depending on the model, your rental includes:\n"
            "🩖 Two helmets\n"
            "⛽ Full tank of gas\n"
            "🏍️ Powerful 150cc, 180cc or 200cc engine\n"
            "🧳 Rear storage trunk\n"
            "👥 Comfortable back seat for passengers\n"
            "🛢️ Emergency gas can\n"
            "📍 Built-in GPS tracker\n\n"
            "ATVs handle Tulum's potholes and dirt roads way better "
            "than scooters — great if you're not an experienced rider!"
        ),
    },
    {
        "keywords": ["atv rule", "atv driving", "reglas atv", "atv law"],
        "question": "What are the driving rules for ATVs?",
        "answer": (
            "Same rules as scooters and cars:\n\n"
            "🪪 Valid driver's license required\n"
            "🩖 Helmets mandatory — no exceptions\n"
            "🚦 Obey all traffic signs and laws\n"
            "🚫 No drinking and driving\n"
            "👥 Max 2 people per ATV\n"
            "🛑 Respect pedestrian zones and protected areas\n\n"
            "Stay safe and enjoy the ride! 🌴"
        ),
    },

    # ── OTHER VEHICLES ───────────────────────────────────────
    {
        "keywords": ["car", "carro", "auto", "coche", "vehicle"],
        "question": "Do you rent cars?",
        "answer": (
            "Yes! We also offer car rentals in addition to scooters and ATVs. 🚗\n\n"
            "Message us with your dates and we'll send you options and pricing!"
        ),
    },
    {
        "keywords": ["buggy", "buggies", "buggie"],
        "question": "Do you have buggies?",
        "answer": (
            "We don't currently offer buggies — but we have ATVs, scooters, "
            "and cars! 🛵🏍️🚗\n\n"
            "ATVs are a great alternative — they handle Tulum's roads "
            "like a champ. Want to know more?"
        ),
    },
    {
        "keywords": ["electric", "eléctrico", "electrico", "e-scooter", "stand up", "standing"],
        "question": "Do you have electric scooters?",
        "answer": (
            "We offer electric stand-up scooters as well! ⚡\n\n"
            "For gas scooters, ATVs, and cars — we've got you covered too. "
            "What are you looking for?"
        ),
    },

    # ── REQUIREMENTS ─────────────────────────────────────────
    {
        "keywords": ["license", "permit", "licencia", "need", "requirement", "requisito", "drive"],
        "question": "Do I need a license to rent?",
        "answer": (
            "You just need a valid driver's license from any country — "
            "no special motorcycle or international license required! 🪪\n\n"
            "You'll also need a valid ID or passport. That's it!"
        ),
    },
    {
        "keywords": ["age", "old", "edad", "años", "how old", "minimum age"],
        "question": "How old do I need to be?",
        "answer": (
            "You need to be legally old enough to drive with a valid "
            "driver's license. 👤\n\n"
            "If you have a valid license, you're good to go!"
        ),
    },
    {
        "keywords": ["bring", "what to bring", "need to bring", "llevar", "qué llevar", "pick up need"],
        "question": "What do I need to bring for pickup?",
        "answer": (
            "If you've already completed your form online, you don't "
            "need to bring anything! 📄\n\n"
            "If not, just bring your driver's license and a credit/debit card."
        ),
    },
    {
        "keywords": ["someone else", "another person", "pick up for me", "otra persona", "recoger por mi"],
        "question": "Can someone else pick up the vehicle for me?",
        "answer": (
            "Only people listed on the waiver may pick up the vehicle. 📝\n\n"
            "If someone else will be riding, they just need to fill out "
            "the form too — and they're good to go!"
        ),
    },
    {
        "keywords": ["another driver", "add driver", "second driver", "otro conductor", "agregar conductor"],
        "question": "Can I add another driver?",
        "answer": (
            "Yes! They just need to fill out the waiver form. ✅\n\n"
            "Let us know and we'll send them the link!"
        ),
    },

    # ── DELIVERY & LOCATION ──────────────────────────────────
    {
        "keywords": ["deliver", "delivery", "pickup", "pick up", "entrega", "recoger", "bring"],
        "question": "Do you deliver scooters?",
        "answer": (
            "Yes! We deliver scooters anywhere in Tulum — including "
            "El Centro, Aldea Zama, and the beach zone "
            "(not inside the National Parks). 🚗💨\n\n"
            "Delivery and pickup are available at an extra cost. "
            "Just send us your address!"
        ),
    },
    {
        "keywords": ["location", "where", "address", "shop", "office", "ubicacion", "ubicación", "donde", "dónde", "find you"],
        "question": "Where are you located?",
        "answer": (
            "Our main pickup location is in La Veleta — "
            "Sur 8 (across from BocaNegra). 📍\n\n"
            "We also deliver to your hotel or Airbnb anywhere in Tulum. "
            "Just send us your location!"
        ),
    },
    {
        "keywords": ["hotel", "airbnb", "deliver to", "entregar en"],
        "question": "Can you deliver to my hotel or Airbnb?",
        "answer": (
            "Yes! As long as it's not inside Jaguar Park or too far "
            "on the highway. 🏡\n\n"
            "Just send us your address and we'll bring the scooter to you!"
        ),
    },
    {
        "keywords": ["airport", "aeropuerto", "cancun airport"],
        "question": "Do you offer airport pickup or drop-off?",
        "answer": (
            "We don't currently offer airport service. ❌\n\n"
            "But we can deliver to your hotel or Airbnb once you arrive in Tulum!"
        ),
    },

    # ── HOURS & RETURNS ──────────────────────────────────────
    {
        "keywords": ["hour", "hours", "open", "close", "time", "horario", "abierto", "when"],
        "question": "What are your hours?",
        "answer": (
            "To speak with someone: 7:30 AM – 11:00 PM 🕖\n"
            "Pick-up & drop-off: Available 24/7! ⏰\n\n"
            "Late flight? Early trip? You're covered — pick up or "
            "return in-store anytime!"
        ),
    },
    {
        "keywords": ["return after hours", "late return", "devolver fuera", "after hours", "return late"],
        "question": "Can I return the vehicle after hours?",
        "answer": (
            "Yes! As long as the drop-off is at our store. ✅\n\n"
            "We offer 24/7 pickup and drop-off at our La Veleta location."
        ),
    },
    {
        "keywords": ["late", "late fee", "tarde", "retraso", "cargo por retraso"],
        "question": "What if I'm late returning it?",
        "answer": (
            "Late fees per hour (if you let us know in advance): ⏰\n"
            "🛵 Scooter: 100 MXN/hr\n"
            "🏍️ ATV: 200 MXN/hr\n"
            "🚗 Car: 250 MXN/hr\n\n"
            "Unapproved late returns are DOUBLE those rates.\n\n"
            "Or you can extend for a full extra day at your daily rate (subject to availability).\n\n"
            "Just give us a heads up before your return time — "
            "we'll always try to work with you!"
        ),
    },

    # ── EXTEND RENTAL ────────────────────────────────────────
    {
        "keywords": ["extend", "extension", "more days", "longer", "extender", "más días", "mas dias", "keep it longer", "extra day", "extra days", "one more day", "few more days", "another day", "stay longer", "can i extend", "keep longer", "add days", "additional days", "un día más", "otro día"],
        "question": "What if I need to extend my rental?",
        "answer": (
            "Yes, you can absolutely extend your rental! 🙌\n\n"
            "Just let us know how many extra days you need and "
            "a team member will send you a payment link with the exact amount.\n\n"
            "Quick heads up: the rate you start with is the rate you keep — "
            "extending doesn't unlock a lower daily price. "
            "For the best deal, always book more days up front!"
        ),
    },

    # ── UPGRADE VEHICLE ───────────────────────────────────────
    {
        "keywords": ["upgrade", "bigger", "larger", "switch up", "better scooter", "better atv",
                     "trade up", "swap for", "change to", "move up", "get an atv", "get a car",
                     "mejorar", "cambiar a", "uno más grande", "mas grande"],
        "question": "Can I upgrade my vehicle?",
        "answer": (
            "Yes, you can upgrade your vehicle! 🔄\n\n"
            "Just let us know what you'd like to switch to "
            "(e.g., scooter → ATV, or a bigger model) and "
            "a team member will get back to you with the price "
            "difference and a payment link.\n\n"
            "Upgrades depend on availability, so the sooner you "
            "let us know, the better!"
        ),
    },

    # ── INSURANCE & SAFETY ───────────────────────────────────
    {
        "keywords": ["insurance", "coverage", "insured", "seguro", "cobertura", "protected"],
        "question": "What about insurance?",
        "answer": (
            "All our scooters come fully insured! ✅\n\n"
            "Your rental includes:\n"
            "• Material Damage (10% deductible)\n"
            "• Accidental Death coverage (up to 50,000 MXN)\n"
            "• Limited Liability (up to 400,000 MXN)\n"
            "• Medical Expenses (up to 20,000 MXN)\n"
            "• Roadside Assistance (towing, gas, jump-starts)\n"
            "• Legal & Bail Support\n"
            "• GPS Tracker on every vehicle\n\n"
            "Extra theft coverage is also available for purchase! 🔒"
        ),
    },
    {
        "keywords": ["stolen", "theft", "robado", "robo", "steal"],
        "question": "What if my scooter gets stolen?",
        "answer": (
            "All our scooters have built-in GPS trackers so we can "
            "locate them quickly. 📍\n\n"
            "You can add theft insurance — your only responsibility "
            "would be the deductible. Without it, you'd be liable for "
            "the full value of the scooter.\n\n"
            "It's a small add-on for major peace of mind! 🔒"
        ),
    },
    {
        "keywords": ["helmet", "casco", "safety gear"],
        "question": "Do you provide helmets?",
        "answer": (
            "Yes! Two helmets are included with every rental. 🩖\n\n"
            "Helmets are required by law in Tulum. We want you to ride safe!"
        ),
    },

    # ── CANCELLATION ─────────────────────────────────────────
    {
        "keywords": ["cancel", "refund", "cancelar", "reembolso", "cancellation", "cancelación"],
        "question": "What's your cancellation policy?",
        "answer": (
            "Here's how it works:\n\n"
            "• Cancel more than 24 hours before: 50% cancellation fee\n"
            "• Cancel within 24 hours: 100% of rental cost charged\n"
            "• No refunds for early returns, unused days, or weather\n\n"
            "Need to change your dates? Just let us know ASAP and we'll "
            "do our best to adjust your booking! 📅"
        ),
    },

    # ── FUEL ─────────────────────────────────────────────────
    {
        "keywords": ["gas", "fuel", "gasoline", "gasolina", "fill", "tank", "tanque"],
        "question": "What's the fuel policy?",
        "answer": (
            "Every vehicle goes out with a full tank! ⛽\n\n"
            "We just ask that you return it full too. "
            "If not, there's a 315 MXN charge plus the cost of missing fuel.\n\n"
            "We'll show you the closest gas stations when you pick up."
        ),
    },

    # ── DRIVING ZONES & RESTRICTIONS ─────────────────────────
    {
        "keywords": ["sian kaan", "sian ka'an", "biosphere", "biosfera", "reserve"],
        "question": "Can I drive to Sian Ka'an?",
        "answer": (
            "You can drive only up to 5–7 minutes max into the reserve area. 🚫\n\n"
            "No highways longer than 5–7 minutes are allowed for safety reasons."
        ),
    },
    {
        "keywords": ["dos ojos", "cenote dos"],
        "question": "Can I drive to Dos Ojos cenote?",
        "answer": (
            "No, unfortunately — Dos Ojos is too far on the highway. 🚫\n\n"
            "But there are tons of amazing cenotes closer to town "
            "that you can visit!"
        ),
    },
    {
        "keywords": ["gran cenote", "cobá", "coba"],
        "question": "Can I drive to Gran Cenote?",
        "answer": (
            "Yes! You can drive to Gran Cenote — it's one of the most popular cenotes "
            "and you'll love it! 💦\n\n"
            "Important: You cannot go past Gran Cenote toward Cobá. Gran Cenote is the "
            "farthest you can go on that road. ⚠️"
        ),
    },
    {
        "keywords": ["cenote", "cenotes", "which cenote", "que cenote", "best cenote", "cenote recommend"],
        "question": "Which cenotes can I visit?",
        "answer": (
            "There are amazing cenotes you can visit near Tulum! 💦\n\n"
            "Gran Cenote is the most popular and the farthest you can go "
            "on the Cobá Road.\n\n"
            "⚠️ Please note these restrictions:\n"
            "• No cenotes past Gran Cenote toward Cobá\n"
            "• No cenotes past the ruins toward Playa del Carmen\n"
            "• No cenotes past Vesica toward Bacalar\n"
            "• Dos Ojos is NOT allowed (too far on highway)\n\n"
            "Ask us for our map with recommended cenotes! 🗺️"
        ),
    },
    {
        "keywords": ["beach", "sand", "playa", "arena"],
        "question": "Can I take the scooter/ATV on the beach?",
        "answer": (
            "You can drive on the beach road, but not directly on the sand. 🏖️\n\n"
            "The beach road takes you right past the best beach clubs and restaurants!"
        ),
    },
    {
        "keywords": ["highway", "carretera", "where can i drive", "restrict", "zones"],
        "question": "Are there areas I'm not allowed to drive?",
        "answer": (
            "Here are the driving zones to know: ✅🚫\n\n"
            "✅ Tulum town, Aldea Zama, beach zone — all good!\n"
            "✅ Gran Cenote — OK (farthest point on Cobá Road)\n"
            "✅ Beach road — OK (but NOT on the sand)\n\n"
            "🚫 Past Gran Cenote toward Cobá — NO\n"
            "🚫 Past the ruins toward Playa del Carmen — NO\n"
            "🚫 Past Vesica toward Bacalar — NO\n"
            "🚫 Dos Ojos cenote — too far on highway\n"
            "🚫 Sian Ka'an — max 5-7 min into the reserve\n\n"
            "Stick to the safe zones and enjoy the ride! 🛵"
        ),
    },

    # ── ISSUES & DAMAGE ──────────────────────────────────────
    {
        "keywords": ["flat tire", "tire", "mechanical", "break down", "llanta", "ponchada", "avería", "problem"],
        "question": "What if I get a flat tire or mechanical issue?",
        "answer": (
            "Just message us right away! 📲 We'll support you immediately.\n\n"
            "We have roadside assistance included with your rental — "
            "towing, gas delivery, and jump-starts are covered!"
        ),
    },
    {
        "keywords": ["damage", "scratch", "broken", "daño", "roto", "scratched"],
        "question": "What about damage costs?",
        "answer": (
            "We're transparent about damage costs. Common examples:\n\n"
            "• Broken mirror: 400 MXN\n"
            "• Flat tire: 700 MXN\n"
            "• Broken pedal: 700 MXN\n"
            "• Major crash: 2,000–10,000 MXN\n\n"
            "Our insurance covers serious damage (over 10% of vehicle value) "
            "with a 10% deductible. For most small stuff, we keep costs fair!"
        ),
    },
    {
        "keywords": ["lost key", "key", "llave", "perdí", "lost helmet"],
        "question": "What if I lose the keys or helmet?",
        "answer": (
            "Just message us for help! 📲\n\n"
            "Replacement costs apply:\n"
            "• Missing helmet or clip: 600 MXN\n"
            "• Missing/broken phone holder: 400 MXN\n"
            "• Missing AirTag: 800 MXN\n\n"
            "We'll get you sorted out quickly!"
        ),
    },
    {
        "keywords": ["accident", "crash", "accidente", "choque"],
        "question": "What if I have an accident?",
        "answer": (
            "First, make sure you're safe! Then message us right away. 🚨\n\n"
            "Your insurance covers:\n"
            "• Medical expenses up to 20,000 MXN\n"
            "• Third-party liability up to 400,000 MXN\n"
            "• Legal & bail support\n"
            "• Roadside assistance\n\n"
            "We'll walk you through everything — you're covered!"
        ),
    },
    {
        "keywords": ["switch", "change vehicle", "cambiar", "swap", "different"],
        "question": "Can I switch to a different vehicle?",
        "answer": (
            "Just message us on WhatsApp! 💬 We'll do our best to "
            "accommodate a switch depending on availability.\n\n"
            "Let us know what you'd prefer and we'll figure it out!"
        ),
    },

    # ── MAPS & TIPS ──────────────────────────────────────────
    {
        "keywords": ["map", "route", "mapa", "ruta", "suggestion", "where to go", "recommend"],
        "question": "Do you provide maps or route suggestions?",
        "answer": (
            "Yes! We make sure you're fully prepared for your trip. 🗺️\n\n"
            "We'll give you tips on the best routes, cenotes, restaurants, "
            "and hidden gems. We also have a Tulum on a Budget guide — "
            "ask us about it!"
        ),
    },
    {
        "keywords": ["budget", "guide", "tips", "save money", "cheap", "guía", "barato"],
        "question": "Tulum on a Budget guide",
        "answer": (
            "We've got an awesome Tulum on a Budget Guide! 💰🌴\n\n"
            "It's packed with local secrets and price hacks you won't find "
            "on your own. Comes with a 100% money-back guarantee and "
            "truly pays for itself!\n\n"
            "Check it out: tulumonabudget.com"
        ),
    },

    # ── CLEANING & FEES ──────────────────────────────────────
    {
        "keywords": ["cleaning", "clean", "limpieza", "dirty", "sucio"],
        "question": "Is there a cleaning fee?",
        "answer": (
            "A cleaning fee of 250 MXN applies if the vehicle is returned "
            "with food, sand, garbage, or mud. 🧹\n\n"
            "Normal use is totally fine — just don't bring it back "
            "caked in mud! 😄"
        ),
    },

    # ── CONTRACT HIGHLIGHTS ───────────────────────────────────
    {
        "keywords": ["new driver", "first time", "beginner", "never driven", "learn", "primera vez", "principiante", "no sé manejar"],
        "question": "Can I rent if I've never driven a scooter?",
        "answer": (
            "Important heads up: We do not rent to new drivers. 🚫\n\n"
            "If you arrive at the store and can't operate the scooter, "
            "you'll lose 100% of your payment.\n\n"
            "If you're unsure, let us know — we can help you find the "
            "right vehicle for your experience level!"
        ),
    },
    {
        "keywords": ["parking", "park", "estacionar", "where to park", "tow", "towed", "remolque"],
        "question": "Where can I park?",
        "answer": (
            "Here are Tulum's parking rules: 🅿️\n\n"
            "🚫 No parking in front of signs with 'E' crossed out\n"
            "🚫 No parking on corners (stay at least 10m away)\n"
            "🚫 Don't park on the main beach road — vehicles get towed!\n\n"
            "Always lock the steering wheel when you leave the scooter. 🔒\n\n"
            "If your vehicle gets towed, fines can be up to 5,000 MXN."
        ),
    },
    {
        "keywords": ["passenger", "riders", "how many", "two people", "baby", "infant", "child", "niño", "bebé", "pasajero"],
        "question": "How many people can ride?",
        "answer": (
            "Max 2 riders per scooter. 👥\n\n"
            "Infants that can be held are allowed as a third rider, "
            "but larger children are not permitted.\n\n"
            "Everyone who rides must be listed on the waiver!"
        ),
    },
    {
        "keywords": ["google maps", "apple maps", "directions", "navigate", "gps", "find you", "navigation"],
        "question": "How do I navigate in Tulum?",
        "answer": (
            "Important tip: Use Google Maps ONLY — not Apple Maps! 📍\n\n"
            "Also, Google Maps is often wrong about one-way streets in Tulum. "
            "Always follow the actual street signs, not your GPS.\n\n"
            "We'll share our exact Google Maps pin when you book! 🗺️"
        ),
    },
    {
        "keywords": ["rain", "lluvia", "weather", "clima", "rainy"],
        "question": "What if it rains?",
        "answer": (
            "If it's raining during your scheduled delivery or pickup, "
            "we'll delay until the rain stops for everyone's safety. 🌧️\n\n"
            "No refunds for weather-related issues, but we'll always "
            "work with you on timing!"
        ),
    },

    # ── PHOTOS ──────────────────────────────────────────────
    {
        "keywords": ["photo", "photos", "picture", "pictures", "pic", "pics", "see", "look like", "imagen", "imagen", "foto", "fotos", "ver", "show me", "what do they look like", "what does it look like"],
        "question": "Can I see photos of the scooters/ATVs?",
        "answer": (
            "Of course! 📸 Check out photos of our scooters and ATVs here:\n"
            "👉 https://drive.google.com/drive/folders/1sEhjBWvxUTVJoKyKsgFfa1U8gvwBzmbH\n\n"
            "You can also see photos and book directly on our website:\n"
            "👉 rentscootertulum.com"
        ),
    },

    # ── HUMAN HANDOFF ────────────────────────────────────────
    {
        "keywords": ["human", "person", "real person", "agent", "persona", "humano", "team"],
        "question": "I want to talk to a real person",
        "answer": (
            "No problem! A team member will get back to you shortly. 🙌\n\n"
            "Our hours are 7:30 AM – 11:00 PM (Tulum time). "
            "We'll respond as fast as we can!"
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
