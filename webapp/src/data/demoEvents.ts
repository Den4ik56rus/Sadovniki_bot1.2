/**
 * ВРЕМЕННЫЙ ФАЙЛ - Демо-события для тестирования
 * Удалить после тестирования!
 */

import type { CalendarEvent, EventType } from '@/types';
import { getDemoPlantings } from './demoPlantings';
import { getCultureCode } from '@constants/plantingCultures';

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
  durationDays?: number; // Длительность события в днях (для длинных событий)
  cultureIndex: number; // Индекс культуры из демо-посадок (0, 1, 2)
}

// Компактные шаблоны: 2-3 события на месяц, одно длинное
// cultureIndex: 0 = клубника, 1 = малина, 2 = смородина
const demoEvents: EventTemplate[] = [
  // Месяц 0 (текущий)
  { monthOffset: 0, day: 3, type: 'nutrition', title: 'Подкормка клубники', description: 'Внести комплексные удобрения', durationDays: 1, cultureIndex: 0 },
  { monthOffset: 0, day: 10, type: 'protection', title: 'Обработка от вредителей', description: 'Профилактическое опрыскивание всех культур', durationDays: 3, cultureIndex: 1 },
  { monthOffset: 0, day: 18, type: 'planting', title: 'Обрезка малины', description: 'Санитарная обрезка кустов', durationDays: 7, cultureIndex: 1 },

  // Месяц 1
  { monthOffset: 1, day: 5, type: 'soil', title: 'Мульчирование грядок', description: 'Замульчировать клубнику и малину', durationDays: 10, cultureIndex: 0 },
  { monthOffset: 1, day: 20, type: 'nutrition', title: 'Подкормка смородины', description: 'Азотные удобрения для роста', durationDays: 1, cultureIndex: 2 },

  // Месяц 2
  { monthOffset: 2, day: 1, type: 'protection', title: 'Обработка от болезней', description: 'Профилактика грибковых заболеваний', durationDays: 5, cultureIndex: 0 },
  { monthOffset: 2, day: 15, type: 'harvest', title: 'Сбор урожая клубники', description: 'Первая волна плодоношения', durationDays: 14, cultureIndex: 0 },

  // Месяц 3
  { monthOffset: 3, day: 1, type: 'harvest', title: 'Сбор малины', description: 'Основной период плодоношения', durationDays: 21, cultureIndex: 1 },
  { monthOffset: 3, day: 25, type: 'nutrition', title: 'Подкормка после сбора', description: 'Восстановление сил растений', durationDays: 1, cultureIndex: 2 },

  // Месяц 4
  { monthOffset: 4, day: 5, type: 'harvest', title: 'Сбор смородины', description: 'Массовый сбор урожая', durationDays: 10, cultureIndex: 2 },
  { monthOffset: 4, day: 20, type: 'planting', title: 'Укоренение усов клубники', description: 'Размножение молодыми розетками', durationDays: 7, cultureIndex: 0 },

  // Месяц 5
  { monthOffset: 5, day: 1, type: 'planting', title: 'Обрезка отплодоносивших побегов', description: 'Удалить старые побеги малины', durationDays: 5, cultureIndex: 1 },
  { monthOffset: 5, day: 15, type: 'nutrition', title: 'Осенняя подкормка', description: 'Фосфорно-калийные удобрения', durationDays: 1, cultureIndex: 2 },
  { monthOffset: 5, day: 22, type: 'soil', title: 'Рыхление почвы', description: 'Прополка и рыхление междурядий', durationDays: 3, cultureIndex: 0 },

  // Месяц 6
  { monthOffset: 6, day: 5, type: 'protection', title: 'Обработка от клеща', description: 'Профилактика земляничного клеща', durationDays: 2, cultureIndex: 0 },
  { monthOffset: 6, day: 15, type: 'planting', title: 'Посадка новой клубники', description: 'Закладка новых грядок', durationDays: 7, cultureIndex: 0 },

  // Месяц 7
  { monthOffset: 7, day: 1, type: 'soil', title: 'Подготовка к зиме', description: 'Мульчирование и укрытие грядок', durationDays: 14, cultureIndex: 1 },
  { monthOffset: 7, day: 20, type: 'planting', title: 'Пригибание малины', description: 'Подготовка побегов к зимовке', durationDays: 5, cultureIndex: 1 },

  // Месяц 8
  { monthOffset: 8, day: 5, type: 'protection', title: 'Защита от грызунов', description: 'Установка защитных сеток и отпугивателей', durationDays: 3, cultureIndex: 2 },
  { monthOffset: 8, day: 15, type: 'soil', title: 'Снегозадержание', description: 'Обеспечить снежный покров для защиты', durationDays: 1, cultureIndex: 0 },

  // Месяц 9
  { monthOffset: 9, day: 10, type: 'protection', title: 'Проверка укрытий', description: 'Осмотр зимних укрытий после снегопадов', durationDays: 1, cultureIndex: 1 },

  // Месяц 10
  { monthOffset: 10, day: 5, type: 'planting', title: 'Планирование посадок', description: 'Составить план на следующий сезон', durationDays: 7, cultureIndex: 2 },
  { monthOffset: 10, day: 20, type: 'soil', title: 'Заготовка компоста', description: 'Подготовка органических удобрений', durationDays: 3, cultureIndex: 0 },

  // Месяц 11
  { monthOffset: 11, day: 1, type: 'planting', title: 'Закупка саженцев', description: 'Выбор и заказ посадочного материала', durationDays: 14, cultureIndex: 1 },
  { monthOffset: 11, day: 20, type: 'nutrition', title: 'Подготовка удобрений', description: 'Закупка удобрений на сезон', durationDays: 1, cultureIndex: 2 },
];

/**
 * Генерирует демо-события на год вперёд
 * События привязаны к демо-посадкам пользователя через cultureCode
 */
export function generateDemoEvents(): Record<string, CalendarEvent> {
  const events: Record<string, CalendarEvent> = {};
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth();

  // Получаем демо-посадки для генерации cultureCode
  const plantings = getDemoPlantings();

  const pad = (n: number) => n.toString().padStart(2, '0');
  const nowLocal = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;

  for (let i = 0; i < demoEvents.length; i++) {
    const template = demoEvents[i];
    const eventMonth = (currentMonth + template.monthOffset) % 12;
    const eventYear = currentYear + Math.floor((currentMonth + template.monthOffset) / 12);

    // Корректируем день если он больше количества дней в месяце
    const daysInMonth = new Date(eventYear, eventMonth + 1, 0).getDate();
    const eventDay = Math.min(template.day, daysInMonth);

    const id = generateUUID();
    const startDateTime = `${eventYear}-${pad(eventMonth + 1)}-${pad(eventDay)}T09:00:00`;

    // Вычисляем endDateTime для длинных событий
    let endDateTime: string | null = null;
    if (template.durationDays && template.durationDays > 1) {
      const endDate = new Date(eventYear, eventMonth, eventDay + template.durationDays - 1);
      endDateTime = `${endDate.getFullYear()}-${pad(endDate.getMonth() + 1)}-${pad(endDate.getDate())}T18:00:00`;
    }

    // Получаем cultureCode из демо-посадки
    const planting = plantings[template.cultureIndex];
    const cultureCode = planting ? getCultureCode(planting) : undefined;

    events[id] = {
      id,
      title: template.title,
      startDateTime,
      endDateTime,
      allDay: true,
      type: template.type,
      cultureCode,
      status: 'planned',
      description: template.description,
      createdAt: nowLocal,
      updatedAt: nowLocal,
    };
  }

  return events;
}
