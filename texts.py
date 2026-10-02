"""User-facing texts per language. Edit freely — the bot re-syncs its profile on every start.

Keys are Telegram language codes. "en" is the default for everyone else.
Limits: SHORT ≤ 120 chars, DESCRIPTION ≤ 512 chars (checked at start-up).
Translations: have a native speaker check them before going live.
"""

LANGS = ["en", "lt", "lv", "hr", "bg", "es", "ru", "ar"]
ALIASES = {"sr": "hr", "bs": "hr", "me": "hr", "cnr": "hr", "sh": "hr"}   # ex-Yu users get the Croatian text

# bot profile "About" — shown in the profile and when the bot is shared
SHORT = {
    "en": "Questions or complaints about our Telegram channels? Write here — our team replies right in this chat.",
    "lt": "Klausimai ar skundai dėl mūsų kanalų? Rašykite čia – mūsų komanda atsakys šiame pokalbyje.",
    "lv": "Jautājumi vai sūdzības par mūsu kanāliem? Rakstiet šeit – mūsu komanda atbildēs šajā sarunā.",
    "hr": "Pitanja ili pritužbe vezane uz naše kanale? Pišite ovdje – naš tim odgovara u ovom razgovoru.",
    "bg": "Въпроси или оплаквания за нашите канали? Пишете тук – нашият екип ще отговори в този чат.",
    "es": "¿Preguntas o quejas sobre nuestros canales? Escribe aquí: nuestro equipo te responde en este chat.",
    "ru": "Вопросы или жалобы по нашим каналам? Пишите сюда — команда ответит прямо в этом чате.",
    "ar": "أسئلة أو شكاوى حول قنواتنا؟ اكتب هنا وسيرد فريقنا في هذه المحادثة.",
}

# shown in the empty chat before the user presses Start
DESCRIPTION = {
    "en": "👋 This is the official support contact for our Telegram channels.\n\n"
          "Write to us about:\n"
          "• questions about posts, bonuses or offers\n"
          "• problems with a casino or bookmaker you joined through us\n"
          "• complaints and suggestions\n\n"
          "Text, screenshots and voice messages are welcome — our team replies right here.\n\n"
          "🔒 We never ask for passwords, card details or payments in this chat.\n"
          "Conversations are stored to handle your request.\n"
          "18+ · Play responsibly.",
    "lt": "👋 Tai oficialus mūsų Telegram kanalų pagalbos kontaktas.\n\n"
          "Rašykite mums dėl:\n"
          "• klausimų apie įrašus, bonusus ar pasiūlymus\n"
          "• problemų su kazino ar lažybų bendrove, prie kurios prisijungėte per mus\n"
          "• skundų ir pasiūlymų\n\n"
          "Galite siųsti tekstą, ekrano nuotraukas ir balso žinutes – mūsų komanda atsakys čia.\n\n"
          "🔒 Šiame pokalbyje niekada neprašome slaptažodžių, kortelės duomenų ar mokėjimų.\n"
          "Pokalbiai saugomi, kad galėtume išspręsti jūsų užklausą.\n"
          "18+ · Žaiskite atsakingai.",
    "lv": "👋 Šis ir mūsu Telegram kanālu oficiālais atbalsta kontakts.\n\n"
          "Rakstiet mums par:\n"
          "• jautājumiem par ierakstiem, bonusiem vai piedāvājumiem\n"
          "• problēmām ar kazino vai derību kompāniju, kurai pievienojāties caur mums\n"
          "• sūdzībām un ieteikumiem\n\n"
          "Varat sūtīt tekstu, ekrānuzņēmumus un balss ziņas – mūsu komanda atbildēs šeit.\n\n"
          "🔒 Šajā sarunā mēs nekad neprasām paroles, kartes datus vai maksājumus.\n"
          "Sarunas tiek saglabātas, lai apstrādātu jūsu pieprasījumu.\n"
          "18+ · Spēlējiet atbildīgi.",
    "hr": "👋 Ovo je službeni kontakt za podršku naših Telegram kanala.\n\n"
          "Pišite nam o:\n"
          "• pitanjima o objavama, bonusima ili ponudama\n"
          "• problemima s kasinom ili kladionicom kojoj ste se pridružili preko nas\n"
          "• pritužbama i prijedlozima\n\n"
          "Možete slati tekst, snimke zaslona i glasovne poruke – naš tim odgovara ovdje.\n\n"
          "🔒 U ovom razgovoru nikada ne tražimo lozinke, podatke o kartici ni uplate.\n"
          "Razgovori se pohranjuju radi obrade vašeg upita.\n"
          "18+ · Igrajte odgovorno.",
    "bg": "👋 Това е официалният контакт за поддръжка на нашите Telegram канали.\n\n"
          "Пишете ни за:\n"
          "• въпроси за публикации, бонуси или оферти\n"
          "• проблеми с казино или букмейкър, в който сте се регистрирали чрез нас\n"
          "• оплаквания и предложения\n\n"
          "Можете да изпращате текст, екранни снимки и гласови съобщения – нашият екип отговаря тук.\n\n"
          "🔒 В този чат никога не искаме пароли, данни за карти или плащания.\n"
          "Разговорите се съхраняват, за да обработим запитването ви.\n"
          "18+ · Играйте отговорно.",
    "es": "👋 Este es el contacto oficial de soporte de nuestros canales de Telegram.\n\n"
          "Escríbenos sobre:\n"
          "• dudas sobre publicaciones, bonos u ofertas\n"
          "• problemas con un casino o casa de apuestas en la que te registraste a través de nosotros\n"
          "• quejas y sugerencias\n\n"
          "Puedes enviar texto, capturas de pantalla y mensajes de voz: nuestro equipo responde aquí.\n\n"
          "🔒 En este chat nunca pedimos contraseñas, datos de tarjeta ni pagos.\n"
          "Las conversaciones se guardan para gestionar tu solicitud.\n"
          "18+ · Juega con responsabilidad.",
    "ru": "👋 Это официальный контакт поддержки наших Telegram-каналов.\n\n"
          "Пишите нам, если у вас:\n"
          "• вопрос о постах, бонусах или предложениях\n"
          "• проблема с казино или букмекером, где вы зарегистрировались через нас\n"
          "• жалоба или предложение\n\n"
          "Можно отправлять текст, скриншоты и голосовые — наша команда ответит здесь.\n\n"
          "🔒 В этом чате мы никогда не просим пароли, данные карт или платежи.\n"
          "Переписка сохраняется для обработки вашего обращения.\n"
          "18+ · Играйте ответственно.",
    "ar": "👋 هذا هو جهة الاتصال الرسمية للدعم الخاصة بقنواتنا على تيليجرام.\n\n"
          "راسلنا بخصوص:\n"
          "• أسئلة حول المنشورات أو المكافآت أو العروض\n"
          "• مشاكل مع كازينو أو موقع مراهنات سجّلت فيه عن طريقنا\n"
          "• الشكاوى والاقتراحات\n\n"
          "يمكنك إرسال نص أو لقطات شاشة أو رسائل صوتية، وسيرد فريقنا هنا.\n\n"
          "🔒 لا نطلب أبدًا كلمات المرور أو بيانات البطاقة أو أي مدفوعات في هذه المحادثة.\n"
          "يتم حفظ المحادثات لمعالجة طلبك.\n"
          "+18 · العب بمسؤولية.",
}

# reply to /start (per channel: the channel's language; /welcome key text overrides)
WELCOME = {
    "en": "Hi! 👋 Write your question, problem or complaint — screenshots help a lot. Our team will reply right here.\n"
          "🔒 We never ask for passwords or card details.",
    "lt": "Sveiki! 👋 Parašykite savo klausimą, problemą ar skundą – ekrano nuotraukos labai padeda. Mūsų komanda atsakys čia.\n"
          "🔒 Niekada neprašome slaptažodžių ar kortelės duomenų.",
    "lv": "Sveiki! 👋 Uzrakstiet savu jautājumu, problēmu vai sūdzību – ekrānuzņēmumi ļoti palīdz. Mūsu komanda atbildēs šeit.\n"
          "🔒 Mēs nekad neprasām paroles vai kartes datus.",
    "hr": "Bok! 👋 Napišite svoje pitanje, problem ili pritužbu – snimke zaslona puno pomažu. Naš tim će odgovoriti ovdje.\n"
          "🔒 Nikada ne tražimo lozinke ni podatke o kartici.",
    "bg": "Здравейте! 👋 Напишете въпроса, проблема или оплакването си – екранните снимки много помагат. Нашият екип ще отговори тук.\n"
          "🔒 Никога не искаме пароли или данни за карти.",
    "es": "¡Hola! 👋 Escribe tu pregunta, problema o queja; las capturas de pantalla ayudan mucho. Nuestro equipo te responderá aquí.\n"
          "🔒 Nunca pedimos contraseñas ni datos de tarjeta.",
    "ru": "Здравствуйте! 👋 Напишите ваш вопрос, проблему или жалобу — скриншоты очень помогают. Наша команда ответит здесь.\n"
          "🔒 Мы никогда не просим пароли или данные карт.",
    "ar": "مرحبًا! 👋 اكتب سؤالك أو مشكلتك أو شكواك، ولقطات الشاشة تساعد كثيرًا. سيرد فريقنا هنا.\n"
          "🔒 لا نطلب أبدًا كلمات المرور أو بيانات البطاقة.",
}

# auto-reply outside working hours. {reply_hours} {opens} are filled in by the bot
AWAY = {
    "en": "Thanks for your message! 🙏 Our team is offline right now — we'll reply within {reply_hours} hours (from {opens}).",
    "lt": "Ačiū už žinutę! 🙏 Šiuo metu mūsų komanda nedirba – atsakysime per {reply_hours} val. (nuo {opens}).",
    "lv": "Paldies par ziņu! 🙏 Mūsu komanda pašlaik nav tiešsaistē – atbildēsim {reply_hours} stundu laikā (no {opens}).",
    "hr": "Hvala na poruci! 🙏 Naš tim trenutno nije dostupan – odgovorit ćemo u roku od {reply_hours} sati (od {opens}).",
    "bg": "Благодарим за съобщението! 🙏 В момента екипът ни не е на линия – ще отговорим до {reply_hours} часа (от {opens}).",
    "es": "¡Gracias por tu mensaje! 🙏 Ahora mismo nuestro equipo no está disponible; te responderemos en {reply_hours} horas (desde {opens}).",
    "ru": "Спасибо за сообщение! 🙏 Сейчас команда не на связи — ответим в течение {reply_hours} ч (с {opens}).",
    "ar": "شكرًا لرسالتك! 🙏 فريقنا غير متصل حاليًا، وسنرد خلال {reply_hours} ساعة (ابتداءً من {opens}).",
}

# short weekday names Mon…Sun for {opens}
WEEKDAYS = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "lt": ["Pr", "An", "Tr", "Kt", "Pn", "Št", "Sk"],
    "lv": ["P", "O", "T", "C", "Pk", "S", "Sv"],
    "hr": ["pon", "uto", "sri", "čet", "pet", "sub", "ned"],
    "bg": ["пн", "вт", "ср", "чт", "пт", "сб", "нд"],
    "es": ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"],
    "ru": ["пн", "вт", "ср", "чт", "пт", "сб", "вс"],
    "ar": ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"],
}

FAILED = {
    "en": "Sorry, this message could not be delivered. Please try sending it as text.",
    "lt": "Atsiprašome, šios žinutės nepavyko pristatyti. Pabandykite išsiųsti tekstu.",
    "lv": "Atvainojiet, šo ziņu neizdevās nosūtīt. Lūdzu, mēģiniet nosūtīt to kā tekstu.",
    "hr": "Nažalost, ova poruka nije dostavljena. Pokušajte je poslati kao tekst.",
    "bg": "За съжаление съобщението не беше доставено. Опитайте да го изпратите като текст.",
    "es": "Lo sentimos, no se pudo entregar este mensaje. Intenta enviarlo como texto.",
    "ru": "Извините, это сообщение не удалось доставить. Попробуйте отправить его текстом.",
    "ar": "عذرًا، تعذّر توصيل هذه الرسالة. يرجى إرسالها كنص.",
}

UNAVAILABLE = {
    "en": "Sorry, support is not available right now. Please try again later.",
    "lt": "Atsiprašome, pagalba šiuo metu nepasiekiama. Pabandykite vėliau.",
    "lv": "Atvainojiet, atbalsts pašlaik nav pieejams. Lūdzu, mēģiniet vēlāk.",
    "hr": "Nažalost, podrška trenutno nije dostupna. Pokušajte kasnije.",
    "bg": "За съжаление поддръжката в момента не е достъпна. Опитайте по-късно.",
    "es": "Lo sentimos, el soporte no está disponible ahora. Inténtalo más tarde.",
    "ru": "Извините, поддержка сейчас недоступна. Попробуйте позже.",
    "ar": "عذرًا، الدعم غير متاح حاليًا. يرجى المحاولة لاحقًا.",
}

# bot menu command
START_CMD = {
    "en": "Contact support", "lt": "Susisiekti su pagalba", "lv": "Sazināties ar atbalstu",
    "hr": "Kontaktirajte podršku", "bg": "Свържете се с поддръжката", "es": "Contactar con soporte",
    "ru": "Связаться с поддержкой", "ar": "التواصل مع الدعم",
}


def norm(lang):
    """'hr-HR' / 'sr' / None → a key of LANGS or None."""
    if not lang:
        return None
    l = str(lang).split("-")[0].split("_")[0].lower()
    l = ALIASES.get(l, l)
    return l if l in LANGS else None


def pick(table, *langs):
    for l in langs:
        l = norm(l)
        if l and l in table:
            return table[l]
    return table["en"]
