# Регистратсия бо SMS — танзими Firebase

Барнома (APK ва PWA) аз мизоҷ рақами телефонро мепурсад, ба он SMS-код мефиристад,
баъд ному шаҳрро мегирад ва **коди шахсии харидор** (`EVRO-XXXXXX`) медиҳад.
Ин код дар паёми фармоиш дар WhatsApp худкор илова мешавад.
Дар сайти оддӣ (браузер) регистратсия талаб карда намешавад — SEO вайрон намешавад.

То ин қадамҳо иҷро нашаванд, барнома менависад «Регистратсия ҳоло дастрас нест»
ва мизоҷ метавонад бе регистратсия харид кунад.

## 1. Воридшавӣ бо телефонро фаъол кунед
Firebase Console → лоиҳаи **evrostar-c7c85** → **Authentication → Sign-in method → Add new provider → Phone → Enable → Save**.

## 2. Нақшаи Blaze
SMS дар Firebase пулакӣ аст: **Upgrade → Blaze** (пардохт барои ҳар SMS).
Дар **Google Cloud → Billing → Budgets** маҳдудияти моҳона гузоред (масалан $10).

## 3. Тоҷикистонро иҷозат диҳед
**Authentication → Settings → SMS region policy → Allow → Tajikistan (+992)**.
Ҳамаи кишварҳои дигарро бандед — ин аз сӯиистифода ва хароҷоти зиёд муҳофизат мекунад.

## 4. Домен
**Authentication → Settings → Authorized domains**: `evrostarshop.com` ва `www.evrostarshop.com` бояд бошанд.

## 5. Қоидаи Firestore барои мизоҷон
**Firestore → Rules**: ба қоидаҳои мавҷуда ин блокро дар дохили `match /databases/{database}/documents { ... }` илова кунед:

```
match /customers/{uid} {
  allow read: if request.auth != null && request.auth.uid == uid;
  allow create, update: if request.auth != null && request.auth.uid == uid
    && request.resource.data.keys().hasOnly(['name','city','phone','code','lang','createdAt'])
    && request.resource.data.name is string && request.resource.data.name.size() <= 100
    && request.resource.data.phone == request.auth.token.phone_number;
  allow delete: if false;
}
```

Қоидаҳои дигарро нест накунед — танҳо ин блокро илова кунед → **Publish**.

## 6. Рақами санҷишӣ (ройгон)
**Authentication → Sign-in method → Phone → Phone numbers for testing**:
масалан `+992 900 000 001` → код `123456`. Бо ин рақам бе SMS-и пулакӣ санҷед.

## 7. APK-и нав
Барнома нишонаи `EVROSTARApp` мефиристад (версияи 1.1.0). Барои дидани регистратсия
APK-и навро аз **Actions → Build EVROSTAR APK** гирифта, имзо кунед ва насб кунед.
