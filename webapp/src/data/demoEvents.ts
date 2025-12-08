/**
 * ВРЕМЕННЫЙ ФАЙЛ - Демо-события для тестирования
 * Удалить после тестирования!
 */

import type { CalendarEvent, EventType } from '@/types';

// Генератор UUID
function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

interface EventTemplate {
  title: string;
  type: EventType;
  description: string;
  monthOffset: number; // Смещение от текущего месяца
  day: number; // День месяца
}

// Шаблоны событий для клубники (ремонтантной)
const strawberryEvents: EventTemplate[] = [
  { monthOffset: 0, day: 5, type: 'nutrition', title: 'Подкормка клубники азотом', description: 'Внести азотные удобрения (мочевина 15г/м²) для активного роста листьев' },
  { monthOffset: 0, day: 15, type: 'protection', title: 'Обработка от долгоносика', description: 'Профилактическая обработка от малинно-земляничного долгоносика' },
  { monthOffset: 1, day: 1, type: 'soil', title: 'Мульчирование клубники', description: 'Замульчировать грядки соломой или агроволокном для сохранения влаги' },
  { monthOffset: 1, day: 20, type: 'nutrition', title: 'Подкормка калием', description: 'Внести калийные удобрения для формирования ягод' },
  { monthOffset: 2, day: 10, type: 'protection', title: 'Обработка от серой гнили', description: 'Профилактика грибковых заболеваний перед цветением' },
  { monthOffset: 2, day: 25, type: 'harvest', title: 'Начало сбора клубники', description: 'Первый сбор урожая ремонтантной клубники' },
  { monthOffset: 3, day: 5, type: 'harvest', title: 'Сбор клубники (основной)', description: 'Основной период плодоношения, собирать каждые 2-3 дня' },
  { monthOffset: 3, day: 20, type: 'nutrition', title: 'Подкормка после сбора', description: 'Комплексное удобрение для восстановления сил растений' },
  { monthOffset: 4, day: 10, type: 'planting', title: 'Укоренение усов клубники', description: 'Укоренить молодые розетки для размножения' },
  { monthOffset: 4, day: 25, type: 'harvest', title: 'Второй сбор клубники', description: 'Вторая волна плодоношения ремонтантной клубники' },
  { monthOffset: 5, day: 15, type: 'nutrition', title: 'Осенняя подкормка клубники', description: 'Фосфорно-калийные удобрения для подготовки к зиме' },
  { monthOffset: 6, day: 1, type: 'protection', title: 'Обработка от клеща', description: 'Профилактическая обработка от земляничного клеща' },
  { monthOffset: 6, day: 20, type: 'soil', title: 'Рыхление междурядий', description: 'Прополка и рыхление почвы между кустами' },
  { monthOffset: 7, day: 10, type: 'planting', title: 'Посадка новой клубники', description: 'Оптимальное время для посадки молодых саженцев' },
  { monthOffset: 8, day: 5, type: 'soil', title: 'Подготовка клубники к зиме', description: 'Укрытие грядок на зиму лапником или агроволокном' },
  { monthOffset: 9, day: 15, type: 'protection', title: 'Проверка укрытия', description: 'Проверить состояние зимнего укрытия после снегопадов' },
  { monthOffset: 10, day: 10, type: 'soil', title: 'Снегозадержание', description: 'Обеспечить достаточный снежный покров для защиты от морозов' },
  { monthOffset: 11, day: 20, type: 'planting', title: 'Планирование посадок', description: 'Спланировать расположение грядок на следующий сезон' },
];

// Шаблоны событий для малины (летней)
const raspberryEvents: EventTemplate[] = [
  { monthOffset: 0, day: 3, type: 'planting', title: 'Обрезка малины', description: 'Санитарная обрезка, удаление слабых и поврежденных побегов' },
  { monthOffset: 0, day: 18, type: 'nutrition', title: 'Подкормка малины', description: 'Внести комплексные удобрения в приствольный круг' },
  { monthOffset: 1, day: 8, type: 'soil', title: 'Мульчирование малины', description: 'Замульчировать перегноем или компостом слоем 5-7 см' },
  { monthOffset: 1, day: 22, type: 'protection', title: 'Обработка от тли', description: 'Профилактическое опрыскивание от малинной тли' },
  { monthOffset: 2, day: 5, type: 'planting', title: 'Подвязка малины', description: 'Подвязать побеги к шпалере для удобства ухода' },
  { monthOffset: 2, day: 18, type: 'nutrition', title: 'Подкормка перед цветением', description: 'Калийно-фосфорные удобрения для лучшего плодоношения' },
  { monthOffset: 3, day: 1, type: 'protection', title: 'Обработка от малинного жука', description: 'Защита от вредителей в период бутонизации' },
  { monthOffset: 3, day: 15, type: 'harvest', title: 'Начало сбора малины', description: 'Первый урожай летней малины' },
  { monthOffset: 4, day: 1, type: 'harvest', title: 'Основной сбор малины', description: 'Пик плодоношения, собирать ежедневно' },
  { monthOffset: 4, day: 20, type: 'planting', title: 'Обрезка отплодоносивших побегов', description: 'Удалить побеги, которые уже дали урожай' },
  { monthOffset: 5, day: 10, type: 'nutrition', title: 'Подкормка после сбора', description: 'Восстановительная подкормка органикой' },
  { monthOffset: 5, day: 25, type: 'soil', title: 'Рыхление почвы', description: 'Неглубокое рыхление и удаление сорняков' },
  { monthOffset: 6, day: 8, type: 'planting', title: 'Нормирование побегов', description: 'Оставить 8-10 сильных побегов на куст' },
  { monthOffset: 7, day: 1, type: 'nutrition', title: 'Осенняя подкормка малины', description: 'Фосфорно-калийные удобрения для подготовки к зиме' },
  { monthOffset: 7, day: 20, type: 'protection', title: 'Обработка от болезней', description: 'Профилактическое опрыскивание фунгицидами' },
  { monthOffset: 8, day: 10, type: 'planting', title: 'Пригибание малины на зиму', description: 'Пригнуть побеги к земле для защиты от морозов' },
  { monthOffset: 9, day: 5, type: 'soil', title: 'Укрытие малины', description: 'Дополнительное укрытие снегом или агроволокном' },
  { monthOffset: 10, day: 15, type: 'protection', title: 'Защита от грызунов', description: 'Проверить защиту от мышей и зайцев' },
  { monthOffset: 11, day: 10, type: 'planting', title: 'Планирование малинника', description: 'Спланировать расширение или обновление посадок' },
];

// Шаблоны событий для смородины (черной)
const currantEvents: EventTemplate[] = [
  { monthOffset: 0, day: 7, type: 'planting', title: 'Обрезка смородины', description: 'Формирующая обрезка до начала сокодвижения' },
  { monthOffset: 0, day: 20, type: 'protection', title: 'Обработка от почкового клеща', description: 'Опрыскивание против почкового клеща' },
  { monthOffset: 1, day: 5, type: 'nutrition', title: 'Подкормка смородины', description: 'Азотные удобрения для активного роста' },
  { monthOffset: 1, day: 18, type: 'soil', title: 'Рыхление приствольных кругов', description: 'Рыхление и мульчирование почвы под кустами' },
  { monthOffset: 2, day: 3, type: 'protection', title: 'Обработка от тли', description: 'Профилактика галловой тли на смородине' },
  { monthOffset: 2, day: 15, type: 'nutrition', title: 'Подкормка перед цветением', description: 'Комплексные удобрения с микроэлементами' },
  { monthOffset: 3, day: 8, type: 'protection', title: 'Защита от мучнистой росы', description: 'Обработка от американской мучнистой росы' },
  { monthOffset: 3, day: 22, type: 'harvest', title: 'Начало сбора смородины', description: 'Первые кисти черной смородины созрели' },
  { monthOffset: 4, day: 5, type: 'harvest', title: 'Основной сбор смородины', description: 'Массовый сбор урожая смородины' },
  { monthOffset: 4, day: 18, type: 'nutrition', title: 'Подкормка после сбора', description: 'Фосфорно-калийные удобрения для восстановления' },
  { monthOffset: 5, day: 1, type: 'planting', title: 'Черенкование смородины', description: 'Заготовка зеленых черенков для размножения' },
  { monthOffset: 5, day: 20, type: 'soil', title: 'Полив и рыхление', description: 'Глубокий полив и рыхление в засушливый период' },
  { monthOffset: 6, day: 10, type: 'protection', title: 'Обработка от стеклянницы', description: 'Профилактика смородинной стеклянницы' },
  { monthOffset: 6, day: 25, type: 'planting', title: 'Санитарная обрезка', description: 'Удаление больных и поврежденных ветвей' },
  { monthOffset: 7, day: 8, type: 'nutrition', title: 'Осенняя подкормка смородины', description: 'Органические удобрения под перекопку' },
  { monthOffset: 7, day: 22, type: 'planting', title: 'Посадка смородины', description: 'Оптимальное время для посадки саженцев' },
  { monthOffset: 8, day: 5, type: 'soil', title: 'Подготовка к зиме', description: 'Мульчирование и окучивание кустов' },
  { monthOffset: 9, day: 10, type: 'protection', title: 'Защита от морозов', description: 'Проверка укрытия молодых кустов' },
  { monthOffset: 10, day: 20, type: 'soil', title: 'Снегозадержание', description: 'Накидать снег под кусты для защиты корней' },
  { monthOffset: 11, day: 15, type: 'planting', title: 'Планирование обрезки', description: 'Спланировать весеннюю обрезку кустов' },
];

/**
 * Генерирует демо-события на год вперёд
 */
export function generateDemoEvents(): Record<string, CalendarEvent> {
  const events: Record<string, CalendarEvent> = {};
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth();


  const cultures = [
    // cultureCode должен совпадать с ключами в filterStore.visibleCultures
    { templates: strawberryEvents, cultureCode: 'клубника ремонтантная', name: 'Клубника ремонтантная' },
    { templates: raspberryEvents, cultureCode: 'малина летняя', name: 'Малина летняя' },
    { templates: currantEvents, cultureCode: 'смородина', name: 'Смородина' },
  ];

  for (const culture of cultures) {
    for (const template of culture.templates) {
      const eventMonth = (currentMonth + template.monthOffset) % 12;
      const eventYear = currentYear + Math.floor((currentMonth + template.monthOffset) / 12);

      // Корректируем день если он больше количества дней в месяце
      const daysInMonth = new Date(eventYear, eventMonth + 1, 0).getDate();
      const eventDay = Math.min(template.day, daysInMonth);

      const id = generateUUID();
      // Формат даты: YYYY-MM-DDTHH:mm:ss (без Z, локальное время)
      const pad = (n: number) => n.toString().padStart(2, '0');
      const startDateTime = `${eventYear}-${pad(eventMonth + 1)}-${pad(eventDay)}T09:00:00`;
      const nowLocal = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;

      events[id] = {
        id,
        title: template.title,
        startDateTime,
        endDateTime: null,
        allDay: true,
        type: template.type,
        cultureCode: culture.cultureCode,
        status: 'planned',
        description: template.description,
        createdAt: nowLocal,
        updatedAt: nowLocal,
      };
    }
  }

  return events;
}
