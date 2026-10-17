# Bachon ki Dunya — Kids Plugin

Teen tools jo bachon (~4-10 saal) se pyaar bhare andaz mein interact karte hain,
simple Roman Urdu mein. Saara content **original** hai (`plugins/_kids_content.py`)
— koi copy-paste nahi, koi copyright issue nahi. Offline bhi kaam karta hai.

## Tools

| Tool | Kya karta hai |
|---|---|
| `shirazi_kids_story` | Sabaq-amoz kahani sunata hai. `theme`: sach, meherbani, sabr, shukr, safai, walidain, eman, himmat, maafi, mehnat, namaz, koi bhi. `child_name` do to kahani bachay ke naam se shuru hoti hai. Har kahani ke aakhir mein sabaq. |
| `shirazi_kids_lesson` | Islami sabaq: `dua` (choti duain), `seerah` (Nabi ﷺ ki pyari baatein), `akhlaq` (10 sunheri aadatain), `namaz` (tareeqa), `prophets` (Nabiyon ke qissay), `quran` (Quran ki baatein). |
| `shirazi_kids_quiz` | Khel khel mein seekhna: `ask` se kahaniyon par sawal, `check` se bachay ke jawab ki pyaar bhari checking (sahi par shabashi, ghalat par halka hint + sahi jawab sikha deta hai). |

## Misaal

- "Shirazi, bachon ko kahani sunao" → `shirazi_kids_story(theme="koi bhi")`
- "Ahmed ko sabr ki kahani sunao" → `shirazi_kids_story(theme="sabr", child_name="Ahmed")`
- "Bachon ko duain sikhayo" → `shirazi_kids_lesson(topic="dua")`
- "Bachon se sawal poocho" → `shirazi_kids_quiz(operation="ask")`

## Content barhana

`plugins/_kids_content.py` mein `STORIES` ya `LESSONS` mein naya dict append kar dein —
restart ki zaroorat nahi, agla call khud utha le ga. Har kahani: `id`, `title`,
`theme`, `text` (~150-220 alfaaz), `sabaq`, `quiz` (sawal + jawab).
