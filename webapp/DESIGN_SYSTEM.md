# Design System - Botanical Garden Theme

## Концепция

**"Органический ботанический сад"** — уникальный дизайн для садоводческого приложения с мягкими природными тонами, органическими формами и элегантной типографикой.

## Типографика

### Шрифты
```css
--font-display: 'Cormorant Garamond', Georgia, serif;  /* Заголовки */
--font-body: 'Source Sans 3', sans-serif;              /* Основной текст */
```

### Использование
- **h1, h2, заголовки месяца** — `font-display` (serif), придаёт элегантность
- **Кнопки, лейблы, основной текст** — `font-body` (sans-serif), читаемость

## Цветовая палитра

### Светлая тема (Morning Garden)
| Назначение | Цвет | HEX |
|------------|------|-----|
| Основной акцент | Garden Green | `#4A7C59` |
| Сегодняшний день | Berry Red | `#C75B5B` |
| Выходные | Earth Brown | `#8B6B4D` |
| Основной фон | Warm Cream | `#FDFBF7` |
| Вторичный фон | Soft Linen | `#F5F2EB` |
| Текст основной | Deep Forest | `#2D3A28` |
| Текст вторичный | Mossy Grey | `#5A6B52` |

### Тёмная тема (Moonlit Greenhouse)
| Назначение | Цвет | HEX |
|------------|------|-----|
| Основной акцент | Moonlit Leaf | `#6BA86B` |
| Сегодняшний день | Soft Berry | `#E07070` |
| Выходные | Warm Amber | `#C4A35A` |
| Основной фон | Deep Forest Night | `#1A1F1A` |
| Вторичный фон | Dark Moss | `#232923` |
| Текст основной | Soft Moonlight | `#E8EDE5` |

### Цвета типов событий
```css
--color-nutrition: #5B8A3C;   /* Питание — зелёный лист */
--color-soil: #8B6B4D;        /* Почва — земля */
--color-protection: #C75B5B;  /* Защита — ягодный */
--color-harvest: #D4A84B;     /* Урожай — золотой */
--color-planting: #4A90A4;    /* Посадка — небесный */
--color-other: #7A8B7A;       /* Прочее — шалфей */
```

## Органические формы

### Border Radius
```css
--radius-sm: 6px;
--radius-md: 12px;
--radius-lg: 18px;
--radius-xl: 24px;
--radius-full: 9999px;

/* Уникальные органические формы */
--radius-organic: 30% 70% 70% 30% / 30% 30% 70% 70%;  /* Декоративные элементы */
--radius-leaf: 60% 40% 40% 60% / 60% 40% 60% 40%;    /* Выбранный день, кнопка "Сегодня" */
```

### Применение
- **Выбранный день** — `border-radius: var(--radius-leaf)` — форма листа
- **Декоративные акценты** — `border-radius: var(--radius-organic)`
- **Карточки, кнопки** — `border-radius: var(--radius-lg)` (18px)

## Тени и глубина

```css
--shadow-sm: 0 1px 3px rgba(45, 60, 36, 0.08);
--shadow-md: 0 4px 12px rgba(45, 60, 36, 0.1);
--shadow-lg: 0 8px 24px rgba(45, 60, 36, 0.12);
--shadow-inner: inset 0 2px 6px rgba(45, 60, 36, 0.06);
--shadow-button: 0 2px 8px rgba(74, 124, 89, 0.2);  /* Зелёный оттенок */
```

## Градиенты

```css
/* Заголовки и хедеры */
--gradient-header: linear-gradient(180deg, #F5F2EB 0%, #FDFBF7 100%);

/* Карточки */
--gradient-card: linear-gradient(145deg, #FFFFFF 0%, #F9F7F2 100%);

/* Акцентные кнопки */
--gradient-accent: linear-gradient(135deg, #5B8A3C 0%, #4A7C59 100%);
```

## Декоративные элементы

### Паттерн листьев (фон)
Тонкий SVG паттерн листьев на основном фоне с `opacity: 0.4` (светлая) / `0.15` (тёмная)

### Декоративные акценты
- Полупрозрачные листообразные формы в углах компонентов
- Используют `--radius-organic` или `--radius-leaf`
- Opacity: 0.03-0.08

### Пример (TopBar)
```css
.topbar::before {
  content: '';
  position: absolute;
  top: -10px;
  right: 20px;
  width: 40px;
  height: 40px;
  background: var(--color-accent);
  opacity: 0.06;
  border-radius: var(--radius-leaf);
  transform: rotate(30deg);
}
```

## Анимации

### Pulse для текущего дня
```css
@keyframes todayPulse {
  0%, 100% { opacity: 0; transform: scale(1); }
  50% { opacity: 0.15; transform: scale(1.3); }
}
```

### Leaf Sway (placeholder)
```css
@keyframes leafSway {
  0%, 100% { transform: rotate(-3deg) scale(1); }
  50% { transform: rotate(3deg) scale(1.02); }
}
```

### Transitions
```css
--transition-fast: 180ms cubic-bezier(0.4, 0, 0.2, 1);
--transition-normal: 280ms cubic-bezier(0.4, 0, 0.2, 1);
--transition-bounce: 500ms cubic-bezier(0.68, -0.55, 0.265, 1.55);
```

## Компоненты

### Кнопка "Сегодня" (TopBar)
- Форма листа (`--radius-leaf`)
- Зелёная рамка + фон акцента
- При hover заливается зелёным

### Выбранный день
- Форма листа (`--radius-leaf`)
- Градиентный зелёный фон
- Тень с зелёным оттенком

### Текущий день
- Круглый с градиентом berry
- Pulse анимация
- При выборе — кольцо berry вокруг leaf формы

### Карточка события (EventCard)
- Цветовая полоса слева (5px) по типу события
- Декоративная точка на полосе
- Hover: поднимается + зелёная рамка

### Кнопка "Добавить событие"
- Градиентный зелёный фон
- Shine эффект при hover
- Тень с зелёным оттенком

## Файлы стилей

```
webapp/src/styles/
├── variables.css      # Все CSS переменные, шрифты
├── global.css         # Глобальные стили, утилиты
├── reset.css          # CSS reset
└── themes/
    ├── light.css      # Светлая тема (Morning Garden)
    └── dark.css       # Тёмная тема (Moonlit Greenhouse)
```

## Принципы

1. **Органичность** — избегать острых углов, использовать мягкие формы
2. **Природные цвета** — зелёный, коричневый, кремовый, ягодный
3. **Элегантность** — serif для заголовков, сдержанные анимации
4. **Тактильность** — тени, градиенты, hover эффекты
5. **Тематичность** — каждый элемент ассоциируется с садом/природой
