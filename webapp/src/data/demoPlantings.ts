/**
 * ВРЕМЕННЫЙ ФАЙЛ - Демо-посадки для тестирования
 * Удалить после тестирования!
 */

import type { UserPlanting, CultureType, Variety } from '@/types';

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

interface DemoPlantingTemplate {
  cultureType: CultureType;
  variety: Variety;
}

// Демо-посадки: клубника ремонтантная, малина летняя, смородина
const DEMO_PLANTING_TEMPLATES: DemoPlantingTemplate[] = [
  { cultureType: 'strawberry', variety: 'remontant' },  // клубника ремонтантная
  { cultureType: 'raspberry', variety: 'summer' },      // малина летняя
  { cultureType: 'currant', variety: null },            // смородина
];

// Кэшируем демо-посадки (генерируются один раз)
let cachedDemoPlantings: UserPlanting[] | null = null;

/**
 * Генерирует демо-посадки для профиля пользователя
 */
export function generateDemoPlantings(): UserPlanting[] {
  // Возвращаем кэшированные посадки, чтобы ID оставались стабильными
  if (cachedDemoPlantings) {
    return cachedDemoPlantings;
  }

  const now = new Date();
  const pad = (n: number) => n.toString().padStart(2, '0');
  const nowLocal = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;

  cachedDemoPlantings = DEMO_PLANTING_TEMPLATES.map((template) => ({
    id: generateUUID(),
    cultureType: template.cultureType,
    variety: template.variety,
    fruitingStart: null,
    fruitingEnd: null,
    createdAt: nowLocal,
    updatedAt: nowLocal,
  }));

  return cachedDemoPlantings;
}

/**
 * Получить демо-посадки (кэшированные)
 */
export function getDemoPlantings(): UserPlanting[] {
  return generateDemoPlantings();
}
