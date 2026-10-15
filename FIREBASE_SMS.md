# Регистратсия бо SMS — танзими Firebase (тартиби дуруст)

Барнома (APK ва PWA) аз мизоҷ рақами телефонро мепурсад, ба он SMS-код мефиристад,
баъд ному шаҳрро мегирад ва **коди шахсии харидор** (`EVRO-XXXXXX`) медиҳад.
Код дар паёми фармоиш дар WhatsApp худкор илова мешавад ва дар `admin.html` → «Покупатели» дида мешавад.
Дар сайти оддӣ (браузер, Instagram) регистратсия талаб карда намешавад — SEO вайрон намешавад.

> ⚠️ **Тартиб муҳим аст.** Аввал қоидаҳои Firestore (қадами 1), баъд SMS (қадами 2).
> Агар SMS пеш аз қоидаҳо фаъол шавад ва қоидаҳои ҳозира танҳо `request.auth != null`-ро санҷанд,
> ҳар мизоҷи регистратсияшуда метавонад молҳо ва фармоишҳоро тағйир диҳад.

## 1. Қоидаҳои Firestore (амният)
1. Firebase Console → лоиҳаи **evrostar-c7c85** → **Authentication → Users**.
   «User UID»-и аккаунти админ (бо email)-ро нусха гиред.
2. Файли [`firestore.rules`](firestore.rules)-ро кушоед, `PASTE_ADMIN_UID`-ро бо ин UID иваз кунед.
3. **Firestore Database → Rules** → ҳамаи матнро бо ин файл иваз кунед → **Publish**.
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
