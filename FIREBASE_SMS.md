# Регистратсия бо SMS — танзими Firebase (тартиби дуруст)

> **Ҳоло регистратсия хомӯш аст.** Барнома бе регистратсия кушода мешавад, коди харидор ба фармоиш илова намешавад.
> Калид дар боли `index.html`: `window.EVRO_REGISTRATION=window.EVRO_REGISTRATION??false`.
> Барои фаъол кардан `false`-ро ба `true` иваз кунед — SMS-регистратсия, «Кабинети ман» ва коди харидор бармегарданд.

Барнома (APK ва PWA) аз мизоҷ рақами телефонро мепурсад, ба он SMS-код мефиристад,
баъд ному шаҳрро мегирад ва **коди шахсии харидор** (`EVRO-XXXXXX`) медиҳад.
Код дар паёми фармоиш дар WhatsApp худкор илова мешавад ва дар `admin.html` → «Покупатели» дида мешавад.
Дар сайти оддӣ (браузер, Instagram) регистратсия талаб карда намешавад — SEO вайрон намешавад.

> ⚠️ **Тартиб муҳим аст.** Аввал қоидаҳои Firestore (қадами 1), баъд SMS (қадами 2).
> Агар SMS пеш аз қоидаҳо фаъол шавад ва қоидаҳои ҳозира танҳо `request.auth != null`-ро санҷанд,
> ҳар мизоҷи регистратсияшуда метавонад молҳо ва фармоишҳоро тағйир диҳад.

## 1. Қоидаҳои Firestore (амният)
1. UID-и админ аллакай дар [`firestore.rules`](firestore.rules) гузошта шудааст.
2. Матнро аз https://raw.githubusercontent.com/saidolimov280-afk/EVROSTAR.TJ/main/firestore.rules нусха гиред.
3. Firebase Console → **evrostar-c7c85** → **Firestore Database → Rules** → ҳамаи матнро иваз кунед → **Publish**.
4. Санҷед: сайт молҳоро нишон медиҳад, фармоиш кор мекунад, `admin.html` фармоишҳо ва «Покупатели»-ро нишон медиҳад.

Қоидаҳо дар GitHub Actions худкор санҷида мешаванд (`tests/rules`).

## 2. Воридшавӣ бо телефон
**Authentication → Sign-in method → Add new provider → Phone → Enable → Save**.

## 3. Нақшаи Blaze ва буҷет
SMS пулакӣ аст: **Upgrade → Blaze**. Дар **Google Cloud → Billing → Budgets & alerts** буҷети моҳона гузоред (масалан $10).

## 4. Танҳо Тоҷикистон
**Authentication → Settings → SMS region policy → Allow only → Tajikistan (+992)**.
Ин аз сӯиистифода (SMS pumping) ва хароҷоти зиёд муҳофизат мекунад.

## 5. Домен
**Authentication → Settings → Authorized domains**: `evrostarshop.com` ва `www.evrostarshop.com`.

## 6. Рақами санҷишӣ (ройгон)
**Sign-in method → Phone → Phone numbers for testing**: `+992 900 000 001` → код `123456`.
Бо ин рақам дар APK-и санҷишӣ тамоми роҳро гузаред, бе SMS-и пулакӣ.

## 7. APK ва нашр
1. APK-и санҷишӣ: GitHub → **Actions → Build EVROSTAR APK** → артефакти охирин → имзо → насб.
2. Бо рақами санҷишӣ ва як рақами воқеӣ санҷед.
3. Pull Request-ро merge кунед — сайт ва APK нав мешаванд.

То қадамҳои 2–5 иҷро нашаванд, барнома менависад «Регистратсия ҳоло дастрас нест»
ва мизоҷ метавонад бе регистратсия харид кунад — мағоза баста намешавад.
