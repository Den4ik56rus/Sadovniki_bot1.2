/**
 * Planting Types - Типы для посадок пользователя
 */

// Типы культур
export type CultureType =
  | 'strawberry'   // Клубника
  | 'raspberry'    // Малина
  | 'blackberry'   // Ежевика
  | 'currant'      // Смородина
  | 'blueberry'    // Голубика
  | 'honeysuckle'  // Жимолость
  | 'gooseberry';  // Крыжовник

// Сорта клубники
export type StrawberryVariety = 'early' | 'mid' | 'late' | 'remontant';

// Сорта малины/ежевики
export type BerryVariety = 'summer' | 'remontant';

// Объединённый тип сорта
export type Variety = StrawberryVariety | BerryVariety | null;

// Регионы
export type Region = 'south' | 'central' | 'north';

// Посадка пользователя
export interface UserPlanting {
  id: string;
  userId?: number;
  cultureType: CultureType;
  variety: Variety;
  fruitingStart: string | null;  // YYYY-MM-DD
  fruitingEnd: string | null;    // YYYY-MM-DD
  createdAt: string;
  updatedAt: string;
}

// Данные для создания посадки
export interface CreatePlantingData {
  cultureType: CultureType;
  variety?: Variety;
  fruitingStart?: string | null;
  fruitingEnd?: string | null;
}

// Данные для обновления посадки
export interface UpdatePlantingData {
  cultureType?: CultureType;
  variety?: Variety;
  fruitingStart?: string | null;
  fruitingEnd?: string | null;
}

// Конфигурация культуры для UI
export interface CultureConfig {
  type: CultureType;
  label: string;
  icon: string;
  hasVariety: boolean;
  varieties?: { value: string; label: string }[];
}

// Конфигурация региона для UI
export interface RegionConfig {
  value: Region;
  label: string;
}
