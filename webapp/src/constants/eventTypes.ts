/**
 * Event Types Constants - Справочник типов событий
 */

import type { EventType, EventTypeInfo } from '@/types';

export const EVENT_TYPES: Record<EventType, EventTypeInfo> = {
  nutrition: {
    label: 'Питание',
    color: '#4CAF50',   // Зелёный
    icon: '🌱',
  },
  soil: {
    label: 'Почва',
    color: '#795548',   // Коричневый
    icon: '🪴',
  },
  protection: {
    label: 'Защита',
    color: '#F44336',   // Красный
    icon: '🛡️',
  },
  harvest: {
    label: 'Урожай',
    color: '#FF9800',   // Оранжевый
    icon: '🍓',
  },
  planting: {
    label: 'Посадка',
    color: '#2196F3',   // Синий
    icon: '🌿',
  },
  other: {
    label: 'Прочее',
    color: '#9E9E9E',   // Серый
    icon: '📌',
  },
};

/**
 * Получить информацию о типе события
 */
export function getEventTypeInfo(type: EventType): EventTypeInfo {
  return EVENT_TYPES[type] || EVENT_TYPES.other;
}

/**
 * Список типов для селекта
 */
export const EVENT_TYPE_OPTIONS = Object.entries(EVENT_TYPES).map(([value, info]) => ({
  value: value as EventType,
  label: info.label,
  icon: info.icon,
  color: info.color,
}));
