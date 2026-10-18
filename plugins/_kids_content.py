"""
Bachon ki Dunya — original stories & Islamic lessons for kids.

All content here is ORIGINAL, written for SHIRAZI in simple Roman Urdu for
children aged ~4-10. No copied text, no copyright issues. The library is
meant to grow — just append new dicts to STORIES / LESSONS.

Each story: id, title, theme, text (spoken aloud, ~150-220 words ≈ 1.5-2 min),
sabaq (one-line moral), quiz (question + answer).
"""
from __future__ import annotations

import random

STORIES = [
    {
        "id": "sach_lakadhara",
        "title": "Sach Bolne Wala Lakadhara",
        "theme": "sach",
        "text": (
            "Bohat purani baat hai. Ek gaon mein Rahim naam ka lakadhara rehta tha. "
            "Wo roz jungle se lakriyan kaat kar bechta aur apne bachon ka pait palta tha. "
            "Ek din nadi ke kinare lakri kaat-te hue uski kulhari paani mein gir gayi. "
            "Rahim rone laga. Itne mein nadi se ek pari nikli. Usne sunehri kulhari dikhai aur poocha: "
            "'Kya ye tumhari hai?' Rahim ne kaha: 'Nahi, meri to lohe ki purani kulhari thi.' "
            "Pari ne chaandi ki kulhari dikhai. Rahim phir bola: 'Nahi, ye bhi meri nahi.' "
            "Aakhir mein pari ne uski purani lohe ki kulhari nikali. Rahim khushi se bola: "
            "'Haan! Yehi meri hai!' Pari muskurayi aur teeno kulhariyan use de di. Boli: "
            "'Tumne sach bola, is liye ye inaam tumhara.' "
            "Dosto, sach bolne wale ko Allah bhi pasand karta hai aur log bhi."
        ),
        "sabaq": "Hamesha sach bolo — sach ka phal meetha hota hai.",
        "quiz": ("Rahim ne sunehri kulhari kyun nahi li?", "Kyunki wo uski nahi thi — usne sach bola."),
    },
    {
        "id": "pyaasa_kutta",
        "title": "Pyaasa Kutta aur Ahmed",
        "theme": "meherbani",
        "text": (
            "Garmiyon ka din tha. Ahmed school se ghar aa raha tha. Raste mein usne dekha "
            "ek kutta dhoop mein hanp raha tha, uski zabaan bahar nikli hui thi. "
            "Ahmed ne apni bottle se paani ek mitti ke bartan mein dala aur kutte ke saamne rakh diya. "
            "Kutte ne paani piya aur khushi se dum hilane laga. "
            "Ghar ja kar Ahmed ne ammi ko ye baat batayi. Ammi ne uske sar par haath phaira aur kaha: "
            "'Beta, hamare Nabi ﷺ ne farmaya hai ke janwaron par meherbani karna bohat bara sawab hai. "
            "Ek shakhs ne pyase kutte ko paani pilaya tha to Allah ne use jannat de di.' "
            "Ahmed bohat khush hua. Us din ke baad wo roz apne ghar ke bahar janwaron ke liye "
            "paani ka bartan rakhne laga."
        ),
        "sabaq": "Janwaron aur sab makhlooq par meherbani karo — ye bohat bara sawab hai.",
        "quiz": ("Ahmed ne pyase kutte ke liye kya kiya?", "Usne apni bottle se use paani pilaya."),
    },
    {
        "id": "yusuf_sabr",
        "title": "Yusuf (AS) ka Sabr",
        "theme": "sabr",
        "text": (
            "Bohat purane zamane mein Yusuf (AS) naam ke ek Nabi the. Wo bohat khubsurat aur nek the. "
            "Unke bhai unse hasad karte the. Ek din unhone Yusuf (AS) ko ek gehre kuen mein daal diya. "
            "Socho, kitni mushkil ghari thi! Lekin Yusuf (AS) ne sabr kiya aur Allah par bharosa rakha. "
            "Ek qafila aaya aur unhein kuen se nikal kar Misr le gaya. Wahan unhein ghulam bana kar bech diya gaya. "
            "Phir un par jhoota ilzam laga aur wo qaid khane mein daal diye gaye. "
            "Itni mushkilon ke baad bhi Yusuf (AS) ne kabhi shikayat nahi ki, hamesha sabr kiya. "
            "Aakhir mein Allah ne unhein Misr ka wazeer bana diya. "
            "Dosto, mushkil waqt mein ghabrana nahi chahiye. Sabr ka phal hamesha meetha hota hai."
        ),
        "sabaq": "Mushkil waqt mein sabr karo aur Allah par bharosa rakho.",
        "quiz": ("Yusuf (AS) ne mushkilon mein kya kiya?", "Unhone sabr kiya aur Allah par bharosa rakha."),
    },
    {
        "id": "shukr_kisan",
        "title": "Shukr Guzar Kisan",
        "theme": "shukr",
        "text": (
            "Ek gaon mein Kareem naam ka kisan rehta tha. Har saal wo apne khet mein gandum ugata tha. "
            "Ek saal baarish na hui aur fasal kharab ho gayi. Logon ne kaha: 'Kareem, tum udaas kyun nahi?' "
            "Kareem muskuraya aur bola: 'Allah ne pichle saalon mein bohat diya. Ek saal kam hua to kya hua? "
            "Mere paas sehat hai, biwi bachay hain, ghar hai. Main Allah ka shukr ada karta hoon.' "
            "Agle saal itni achi baarish hui ke uski fasal sab se achi hui. "
            "Gaon walon ne poocha: 'Tumhara raaz kya hai?' Kareem ne kaha: "
            "'Shukr. Jo Allah ka shukr ada karta hai, Allah use aur deta hai.' "
            "Dosto, choti ya bari har naimat par 'Alhamdulillah' kehna seekho."
        ),
        "sabaq": "Har haal mein Allah ka shukr ada karo — shukr se naimatein barhti hain.",
        "quiz": ("Fasal kharab hone par Kareem ne kya kiya?", "Usne udaasi ke bajaye Allah ka shukr ada kiya."),
    },
    {
        "id": "safai_amina",
        "title": "Safai Pasand Amina",
        "theme": "safai",
        "text": (
            "Amina paanch saal ki pyari bachi thi. Uske abbu ne use ek hadees sunayi thi: "
            "'Safai nisf iman hai.' Amina ne is baat ko dil se laga liya. "
            "Wo roz subah uth kar apna bistar khud theek karti, apne khilone sambhal kar rakhti, "
            "aur khana khane se pehle aur baad mein haath zaroor dhoti. "
            "Ek din usne dekha ke masjid ke bahar kachra para hai. Usne apne doston ko bulaya aur sab ne "
            "mil kar safai ki. Imam sahab ne dekha to bohat khush hue aur dua di: "
            "'Allah tum jese bachon ko hamesha khush rakhe.' "
            "Dosto, safai sirf ghar ki nahi, dil ki bhi honi chahiye — hasad aur ghusse se dil ko saaf rakho."
        ),
        "sabaq": "Safai nisf iman hai — apne ghar, jism aur dil ko saaf rakho.",
        "quiz": ("Amina ne masjid ke bahar kya kiya?", "Usne doston ke saath mil kar safai ki."),
    },
    {
        "id": "ammi_khidmat",
        "title": "Ammi ki Khidmat",
        "theme": "walidain",
        "text": (
            "Usman aath saal ka tha. Ek din usne dekha ammi bohat thaki hui hain — "
            "kapre dhoye, khana pakaya, ghar saaf kiya. Usman ne socha: 'Aaj main ammi ki madad karunga.' "
            "Usne bartan uthaye, dastarkhuwan lagaya, aur chote bhai ko kahani sunayi taake ammi aaram kar saken. "
            "Ammi ki aankhon mein aansu aa gaye. Unhone Usman ko gale lagaya aur kaha: "
            "'Beta, hamare Nabi ﷺ ne farmaya hai ke jannat maa ke qadmon tale hai.' "
            "Us din Usman ne faisla kiya ke wo roz ammi abbu ki koi na koi khidmat karega. "
            "Dosto, ammi abbu ki baat mano, unki khidmat karo — ye duniya aur aakhirat dono mein kamyabi ka raasta hai."
        ),
        "sabaq": "Ammi abbu ki khidmat karo — jannat maa ke qadmon tale hai.",
        "quiz": ("Nabi ﷺ ne jannat ke baare mein kya farmaya?", "Jannat maa ke qadmon tale hai."),
    },
    {
        "id": "alamin",
        "title": "Al-Amin — Amanatdar Nabi ﷺ",
        "theme": "eman",
        "text": (
            "Jab hamare pyare Nabi Muhammad ﷺ jawan the, Makkah ke log unhein 'Al-Amin' kehte the, "
            "yaani sab se zyada amanatdar. Log apni qeemti cheezein unke paas amanat rakhtay the, "
            "kyunki sab jaante the ke wo kabhi khayanat nahi karte. "
            "Jab Allah ne unhein Nabi banaya aur kuch log dushman ban gaye, tab bhi unhone amanaton mein "
            "khayanat nahi ki. Hijrat ki raat jab wo Makkah se Madina ja rahe the, unhone Hazrat Ali (RA) ko "
            "peeche chhora taake wo sab logon ki amanatein wapas kar dein — un logon ki bhi jo unke dushman the! "
            "Dosto, yehi hai asli eman — dost ho ya dushman, amanat mein khayanat kabhi nahi karni chahiye."
        ),
        "sabaq": "Amanat mein kabhi khayanat na karo — chahe dost ho ya dushman.",
        "quiz": ("Log Nabi ﷺ ko kya kehte the aur kyun?", "Al-Amin, kyunki wo sab se zyada amanatdar the."),
    },
    {
        "id": "chirya_himmat",
        "title": "Choti Chirya ki Himmat",
        "theme": "himmat",
        "text": (
            "Ek choti si chirya ne darakht par apna ghonsla banaya. Usmein uske nanhe munnay bachay the. "
            "Ek din tez aandhi aayi. Darakht hilne laga. Chirya dar gayi, lekin usne himmat nahi haari. "
            "Usne apne paron se bachon ko dhaka aur tez hawa mein urti rahi taake ghonsla na gire. "
            "Aandhi guzar gayi. Ghonsla mehfooz raha. Bachay chirya se bole: 'Ammi, aap kitni bahadur hain!' "
            "Chirya boli: 'Beta, mushkil waqt mein dar lagna buri baat nahi. Buri baat himmat haarna hai. "
            "Jo himmat karta hai, Allah uski madad karta hai.' "
            "Dosto, imtihan ho ya koi mushkil kaam — himmat se kaam lo, Allah madad karega."
        ),
        "sabaq": "Mushkil waqt mein himmat na haro — himmat karne walon ki Allah madad karta hai.",
        "quiz": ("Chirya ne aandhi mein kya kiya?", "Usne himmat se apne bachon ki hifazat ki."),
    },
    {
        "id": "taif_maafi",
        "title": "Taif Walon ko Maaf Kar Diya",
        "theme": "maafi",
        "text": (
            "Ek baar hamare Nabi ﷺ Taif sheher gaye taake wahan ke logon ko Islam ki dawat dein. "
            "Lekin wahan ke logon ne unke saath bohat bura sulook kiya. Unhein pathar mare, "
            "unke paon mubarak zakhmi ho gaye. "
            "Hazrat Jibrael (AS) aaye aur kaha: 'Agar aap chahein to Allah in paharon ko in par gira de.' "
            "Lekin Rehmat-ul-lil-Alameen ﷺ ne kya kaha? Unhone dua ki: "
            "'Aye Allah! Inhein hidayat de, ye nahi jaante.' Unhone badla nahi liya, maaf kar diya. "
            "Dosto, maaf kar dena sab se bara badla hai. Jo maaf karta hai, Allah use buland karta hai."
        ),
        "sabaq": "Dusron ko maaf kar do — maaf karne wala Allah ko bohat pyara hai.",
        "quiz": ("Nabi ﷺ ne Taif walon ke liye kya dua ki?", "Ke Allah unhein hidayat de — unhone maaf kar diya."),
    },
    {
        "id": "cheenti_mehnat",
        "title": "Mehnati Cheenti",
        "theme": "mehnat",
        "text": (
            "Garmiyon ke din the. Ek cheenti roz subah se shaam tak dane utha kar apne ghar le jaati. "
            "Uska dost tiddi dhoop mein gaane gaata aur kehta: 'Cheenti, aaram kar! Itni mehnat kyun?' "
            "Cheenti muskurati aur kehti: 'Sardiyan aayengi to ye dane kaam aayenge.' "
            "Tiddi hansta raha. Phir sardiyan aayen. Har taraf barf. Tiddi bhooka tha, uske paas kuch nahi tha. "
            "Wo cheenti ke paas gaya. Cheenti ne use khana bhi diya aur naseehat bhi: "
            "'Waqt par mehnat karne wala kabhi mohtaj nahi hota.' "
            "Dosto, parhai ho ya koi kaam — aaj ki mehnat kal ka aaram hai."
        ),
        "sabaq": "Waqt par mehnat karo — aaj ki mehnat kal ka aaram hai.",
        "quiz": ("Cheenti garmiyon mein kya karti thi?", "Wo sardiyon ke liye dane jama karti thi."),
    },
    {
        "id": "oontni_shikayat",
        "title": "Oontni ki Shikayat",
        "theme": "meherbani",
        "text": (
            "Ek din hamare Nabi ﷺ ek bagh mein gaye. Wahan ek oontni thi jo ro rahi thi — "
            "uski aankhon se aansu beh rahe the. Nabi ﷺ uske paas gaye aur uske sar par haath phaira. "
            "Oontni khamosh ho gayi. Phir Nabi ﷺ ne uske malik ko bulaya aur farmaya: "
            "'Kya tum Allah se nahi darte? Ye oontni mujhse shikayat kar rahi hai ke tum use bhooka rakhte ho "
            "aur zyada kaam lete ho.' Malik sharminda hua aur us din ke baad oontni ka khayal rakhne laga. "
            "Dosto, dekho hamare Nabi ﷺ janwaron se kitni meherbani karte the. "
            "Jo janwaron par reham karta hai, Allah us par reham karta hai."
        ),
        "sabaq": "Janwaron par reham karo — ye Nabi ﷺ ki sunnat hai.",
        "quiz": ("Oontni ne Nabi ﷺ se kya shikayat ki?", "Ke uska malik use bhooka rakhta aur zyada kaam leta tha."),
    },
    {
        "id": "bilal_azan",
        "title": "Bilal (RA) ki Pehli Azan",
        "theme": "namaz",
        "text": (
            "Jab Musalman Madina aaye to namaz ke liye bulane ka koi tareeqa nahi tha. "
            "Nabi ﷺ ne sahaba se mashwara kiya. Hazrat Umar (RA) ne khuwab mein azan ke alfaaz sune. "
            "Nabi ﷺ bohat khush hue aur Hazrat Bilal (RA) se kaha: 'Bilal! Utho aur azan do.' "
            "Hazrat Bilal (RA) ki awaz bohat khubsurat thi. Wo Kaabe ki chhat par charhe aur buland awaz mein kaha: "
            "'Allahu Akbar! Allahu Akbar!' Ye duniya ki pehli azan thi. "
            "Log daur daur kar aaye. Us din se aaj tak, din mein paanch baar ye pyari awaz "
            "duniya bhar mein goonjti hai. Dosto, azan sun kar namaz ke liye uthna har Musalman bache ka farz hai."
        ),
        "sabaq": "Azan sun kar namaz parho — ye Allah ka bulawa hai.",
        "quiz": ("Duniya ki pehli azan kis ne di?", "Hazrat Bilal (RA) ne."),
    },
]

THEMES = {
    "sach": "Sachchai aur emanadari",
    "meherbani": "Meherbani aur reham",
    "sabr": "Sabr aur bharosa",
    "shukr": "Shukr guzari",
    "safai": "Safai",
    "walidain": "Walidain ki khidmat",
    "eman": "Amanatdari",
    "himmat": "Himmat aur bahaduri",
    "maafi": "Maaf karna",
    "mehnat": "Mehnat",
    "namaz": "Namaz",
    "koi bhi": "Koi bhi achi kahani",
}

LESSONS = {
    "dua": {
        "title": "Choti Duain",
        "intro": "Dosto! Dua Allah se baat karne ka sab se pyara tareeqa hai. Aao kuch choti duain seekhein:",
        "points": [
            "Sone ki dua: 'Allahumma bismika amootu wa ahya' — Aye Allah, tere naam se marta hoon aur jeeta hoon.",
            "Jagte waqt: 'Alhamdulillahil lazi ahyana ba'da ma amatana' — Shukr hai us Allah ka jis ne humein jagaya.",
            "Khane se pehle: 'Bismillah' — Allah ke naam se shuru karta hoon.",
            "Khane ke baad: 'Alhamdulillah' — Sab tareef Allah ke liye.",
            "Ghar se nikalte waqt: 'Bismillahi tawakkaltu alallah' — Allah ke naam se, Allah par bharosa.",
            "Mushkil waqt mein: 'Hasbunallahu wa ni'mal wakeel' — Allah hamare liye kaafi hai.",
        ],
        "outro": "Ye duain yaad kar lo aur roz parho. Allah apne bandon ki dua zaroor sunta hai.",
    },
    "seerah": {
        "title": "Pyare Nabi ﷺ ki Pyari Baatein",
        "intro": "Hamare Nabi Muhammad ﷺ duniya ke sab se achay insaan the. Aao unki kuch pyari baatein seekhein:",
        "points": [
            "Nabi ﷺ bachon se bohat pyar karte the. Wo unhein god mein uthate, unse khelte aur unke liye dua karte.",
            "Ek baar ek bacha ro raha tha kyunki uski chirya mar gayi thi. Nabi ﷺ uske paas gaye aur use tasalli di.",
            "Nabi ﷺ kabhi jhoot nahi bolte the. Log unhein 'Sadiq' yaani sab se sacha kehte the.",
            "Wo apne kapre khud seete, apne joote khud theek karte — itne azeem ho kar bhi aajizi karte the.",
            "Nabi ﷺ ne farmaya: 'Tum mein se behtareen wo hai jo apne ghar walon se acha sulook kare.'",
            "Unhone farmaya: 'Muskurana bhi sadqa hai.' To dosto, hamesha muskurate raho!",
        ],
        "outro": "Nabi ﷺ ki zindagi hamare liye sab se achi misaal hai. Unki sunnat par chalo ge to kamyab ho ge.",
    },
    "akhlaq": {
        "title": "Achay Bachon ki 10 Adatein",
        "intro": "Achay bachay banne ke liye ye 10 sunheri adatein apnao:",
        "points": [
            "1. Hamesha sach bolo, kabhi jhoot na bolo.",
            "2. Ammi abbu ki baat mano aur unki izzat karo.",
            "3. Baro ka adab karo aur choton par shafqat karo.",
            "4. Apne khilone aur cheezein doston se share karo.",
            "5. Kisi ka mazaq na urao, sab se pyar se baat karo.",
            "6. Waqt par soya karo aur subah jaldi utha karo.",
            "7. Khana khane se pehle Bismillah aur baad mein Alhamdulillah kaho.",
            "8. Apne kamre aur cheezon ko saaf suthra rakho.",
            "9. Gussa aaye to 'Auzu billah' parho aur khamosh ho jao.",
            "10. Roz Allah ka shukr ada karo aur dusron ki madad karo.",
        ],
        "outro": "Ye adatein apnao ge to sab tumse pyar karein ge aur Allah bhi raazi ho ga.",
    },
    "namaz": {
        "title": "Namaz — Allah se Mulaqat",
        "intro": "Namaz Musalman ka sab se pyara farz hai. Din mein 5 namazein hain. Aao seekhein:",
        "points": [
            "5 namazein: Fajr (subah), Zuhr (dopahar), Asr (shaam se pehle), Maghrib (suraj doobte waqt), Isha (raat).",
            "Namaz se pehle wudu karte hain: niyyat, haath dhona, kulli, naak mein paani, chehra, baazu, sar ka masah, paon.",
            "Wudu mein paani zaya na karo — Nabi ﷺ ne farmaya tha ke nadi kinare bhi ho to paani bacha kar istemal karo.",
            "Namaz mein hum Allah se baat karte hain. Dil laga kar parho, jaldi jaldi nahi.",
            "Jo bacha 7 saal ka ho jaye, use namaz parhni chahiye. Tum bhi aaj se pakki namaz parho!",
        ],
        "outro": "Namaz jannat ki kunji hai. Jo namaz parhta hai, Allah use duniya aur aakhirat mein kamyab karta hai.",
    },
    "prophets": {
        "title": "Allah ke Pyare Nabi",
        "intro": "Allah ne insanon ki hidayat ke liye bohat se Nabi bheje. Kuch mashhoor Nabi:",
        "points": [
            "Hazrat Adam (AS) — sab se pehle insaan aur pehle Nabi.",
            "Hazrat Nooh (AS) — unhone kashti banayi aur toofan se bachay.",
            "Hazrat Ibrahim (AS) — unhein aag mein daala gaya, Allah ne aag ko thanda kar diya.",
            "Hazrat Musa (AS) — unhone samandar ko cheer diya Allah ke hukm se.",
            "Hazrat Isa (AS) — wo Allah ke hukm se murdon ko zinda karte the.",
            "Hazrat Yusuf (AS) — khubsurat Nabi jinhone sabr se Misr ki hukumat payi.",
            "Hazrat Muhammad ﷺ — aakhri Nabi, sab se afzal, Rehmat-ul-lil-Alameen.",
        ],
        "outro": "Sab Nabiyon par iman lana hamare iman ka hissa hai. Unki zindagiyon se sabaq seekho.",
    },
    "quran": {
        "title": "Quran — Allah ki Kitaab",
        "intro": "Quran Allah ki aakhri kitaab hai jo Nabi ﷺ par nazil hui. Iske baare mein kuch pyari baatein:",
        "points": [
            "Quran mein 114 suratein hain. Sab se pehli surah Al-Fatiha hai jo har namaz mein parhi jaati hai.",
            "Sab se choti surah Al-Kausar hai — sirf 3 aayatein! Tum bhi aasani se yaad kar sakte ho.",
            "Ayat-ul-Kursi Quran ki sab se azeem ayat hai. Sone se pehle parho, Allah hifazat karega.",
            "Jo bacha Quran parhta hai, uske walidain ko qayamat ke din noor ka taaj pehnaya jayega.",
            "Roz thoda thoda Quran parho aur samajhne ki koshish karo.",
        ],
        "outro": "Quran hamari zindagi ka roshni ka chiraagh hai. Ise parho, samjho aur is par amal karo.",
    },
}

LESSON_TOPICS = {
    "dua": "Choti duain",
    "seerah": "Nabi ﷺ ki seerat",
    "akhlaq": "Achay akhlaq",
    "namaz": "Namaz",
    "prophets": "Nabiyon ke qissay",
    "quran": "Quran ki baatein",
}


def pick_story(theme: str | None = None, seed: int | None = None) -> dict:
    """Pick a story by theme (or any). Deterministic-ish via optional seed."""
    pool = [s for s in STORIES if not theme or theme in ("koi bhi", None) or s["theme"] == theme]
    if not pool:
        pool = STORIES
    rng = random.Random(seed) if seed is not None else random
    return rng.choice(pool)


def format_story(story: dict, child_name: str | None = None) -> str:
    greeting = f"{child_name}, " if child_name else ""
    return (
        f"{greeting}aao, tumhein ek pyari kahani sunata hoon. Kahani ka naam hai: {story['title']}.\n\n"
        f"{story['text']}\n\n"
        f"Is kahani ka sabaq: {story['sabaq']}"
    )


def format_lesson(topic: str) -> str:
    lesson = LESSONS.get(topic) or LESSONS["akhlaq"]
    lines = [lesson["intro"], ""]
    lines.extend(lesson["points"])
    lines += ["", lesson["outro"]]
    return "\n".join(lines)


def quiz_question(seed: int | None = None) -> dict:
    rng = random.Random(seed) if seed is not None else random
    story = rng.choice(STORIES)
    q, a = story["quiz"]
    return {"story_title": story["title"], "question": q, "answer": a}
