# EVROSTAR дар Google Play — дастури пурра

Ҳамаи файлҳо тайёранд. Дар поён ҳар қадам бо матни тайёр барои нусхабардорӣ омадааст.

## 0. Чӣ тайёр аст
| Чиз | Дар куҷо |
|---|---|
| Файли барнома (AAB, имзошуда) | GitHub → **Releases** (пас аз қадами 2) |
| Иконка 512×512 | `play/icon-512.png` |
| Тасвири калон 1024×500 | `play/feature-graphic-1024x500.png` |
| Скриншотҳо 1080×1920 (ru, tg) | шохаи `play-assets` → `screenshots/` |
| Сиёсати махфият | https://evrostarshop.com/privacy.html |
| Нест кардани аккаунт | https://evrostarshop.com/privacy.html#delete-ru |

## 1. Аккаунти таҳиягар (як бор, $25)
https://play.google.com/console → **Create developer account**.
- **Personal** (шахсӣ): осон, аммо пеш аз нашри пурра бояд **санҷиши пӯшида бо 12 нафар дар давоми 14 рӯз** гузарад.
- **Organization** (ташкилот): рақами D-U-N-S лозим аст, вале санҷиши 14-рӯза ҳатмӣ нест.

## 2. Калиди имзо дар GitHub (як бор)
GitHub → репозиторий → **Settings → Secrets and variables → Actions → New repository secret**:
1. Name: `UPLOAD_KEYSTORE` → Secret: ҳамаи матни файли `UPLOAD_KEYSTORE.txt`
2. Name: `UPLOAD_KEYSTORE_PASSWORD` → Secret: матни файли `UPLOAD_KEYSTORE_PASSWORD.txt`

Баъд: **Actions → Google Play release → Run workflow**. Дар **Releases** файлҳои `EVROSTAR.aab` ва `EVROSTAR.apk` пайдо мешаванд.

⚠️ Файли `EVROSTAR-upload-key.jks` ва паролро дар ҷои бехатар нигоҳ доред (Google Drive-и шахсӣ). Ба касе надиҳед ва дар репозиторий нагузоред.

## 3. Сохтани барнома дар Play Console
**Create app**:
- App name: `EVROSTAR — солнечные панели`
- Default language: **Русский – ru-RU**
- App or game: **App** · Free or paid: **Free**
- Розигиҳоро қайд кунед → **Create app**

## 4. Store listing (Main store listing)
**App name** (≤30):
```
EVROSTAR — солнечные панели
```
**Short description** (≤80):
```
Солнечные панели, инверторы и АКБ в Таджикистане. Заказ в WhatsApp.
```
**Full description**:
```
EVROSTAR — магазин солнечной энергетики и электроники в Гиссаре (Большой рынок Гиссара). Доставляем и обслуживаем по всему Таджикистану.

В приложении:
• Каталог: солнечные панели, гибридные инверторы, аккумуляторы LiFePO4, камеры видеонаблюдения, 4G солнечные камеры, роутеры, стабилизаторы, кабели и контроллеры
• Готовые комплекты для дома и магазина: панели + инвертор + АКБ
• Калькулятор: какая система нужна и сколько вы сэкономите по сравнению с генератором
• Корзина и заказ в WhatsApp в один клик — без обязательной онлайн-оплаты
• Личный кабинет: ваши заказы, их статус и срок гарантии
• Сравнение товаров, избранное, уведомление о поступлении
• Сервис и гарантия: заявка мастеру прямо из приложения
• Языки: таджикский и русский

Телефон и WhatsApp: +992 405 555 530
Instagram: @evrostar001

—

EVROSTAR — мағозаи панелҳои офтобӣ, инверторҳо ва аккумуляторҳо дар Ҳисор. Фармоиш тавассути WhatsApp, расонидан ба тамоми Тоҷикистон, кабинети шахсӣ бо ҳолати фармоиш ва кафолат. Забонҳо: тоҷикӣ ва русӣ.
```
**Graphics**: App icon → `icon-512.png`; Feature graphic → `feature-graphic-1024x500.png`; Phone screenshots → `ru-1…ru-6` (ҳадди ақал 2).
**Category**: Shopping · **Contact**: телефон +992405555530, email-и шумо, website `https://evrostarshop.com`

## 5. App content (ҳамаашро пур кунед)
- **Privacy policy**: `https://evrostarshop.com/privacy.html`
- **Ads**: No, my app does not contain ads
- **App access**: All functionality is available without special access. *(Агар Google пурсад: регистратсия бо SMS аст; рақами санҷишӣ `+992 900 000 001`, код `123456`.)*
- **Content rating**: саволнома → Category **Utility/Productivity/Communication/Other** → ҳама ҷавобҳо **No** → натиҷа «3+/Everyone»
- **Target audience**: **18 and over**
- **News app**: No · **Government app**: No · **Financial features**: None · **Health**: No
- **Data safety** — ҷавобҳо:
  - Does your app collect or share user data? **Yes**
  - Is all data encrypted in transit? **Yes**
  - Do you provide a way to request deletion? **Yes** → URL: `https://evrostarshop.com/privacy.html#delete-ru`
  - Data types (Collected: **Yes**, Shared: **No**, Processed ephemerally: **No**):
    - Personal info → **Name** — App functionality, Account management — Optional
    - Personal info → **Phone number** — App functionality, Account management — Required
    - Personal info → **Address** — App functionality — Optional
    - Financial info → **Purchase history** — App functionality — Optional
    - Messages → **Other in-app messages** (шарҳҳо/дархостҳо) — App functionality — Optional

## 6. Нашр
1. **Testing → Closed testing → Create track** → AAB-ро аз Releases бор кунед → 12+ санҷишгар (email-ҳои Google) илова кунед → **Start rollout**.
2. 14 рӯз санҷиш (барои аккаунти Personal).
3. **Production → Create new release** → ҳамон AAB → **Review release → Start rollout**. Санҷиши Google одатан 1–7 рӯз.

Барои нусхаи нав: **Actions → Google Play release → Run workflow** → AAB-и навро бор кунед (versionCode худкор зиёд мешавад).
