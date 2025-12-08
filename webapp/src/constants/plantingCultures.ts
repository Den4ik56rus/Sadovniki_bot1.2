/**
 * Planting Cultures Constants - Справочник культур для посадок
 */

import type { FunctionComponent, SVGProps } from 'react';
import type { CultureConfig, CultureType, RegionConfig, Region, UserPlanting } from '@/types';

// SVG иконки культур
import StrawberryIcon from '@assets/icons/cultures/strawberry.svg?react';
import RaspberryIcon from '@assets/icons/cultures/raspberry.svg?react';
import BlackberryIcon from '@assets/icons/cultures/blackberry.svg?react';
import CurrantIcon from '@assets/icons/cultures/currant.svg?react';
import BlueberryIcon from '@assets/icons/cultures/blueberry.svg?react';
import HoneysuckleIcon from '@assets/icons/cultures/honeysuckle.svg?react';
import GooseberryIcon from '@assets/icons/cultures/gooseberry.svg?react';

// Маппинг типа культуры на SVG компонент
export const CultureIconComponents: Record<CultureType, FunctionComponent<SVGProps<SVGSVGElement>>> = {
  strawberry: StrawberryIcon,
  raspberry: RaspberryIcon,
  blackberry: BlackberryIcon,
  currant: CurrantIcon,
  blueberry: BlueberryIcon,
  honeysuckle: HoneysuckleIcon,
  gooseberry: GooseberryIcon,
};

// Конфигурация культур с сортами
export const PLANTING_CULTURES: CultureConfig[] = [
  {
    type: 'strawberry',
    label: 'Клубника',
    icon: '🍓',
    hasVariety: true,
    varieties: [
      { value: 'early', label: 'Ранний' },
      { value: 'mid', label: 'Средний' },
      { value: 'late', label: 'Поздний' },
      { value: 'remontant', label: 'Ремонтантный (НСД)' },
    ],
  },
  {
    type: 'raspberry',
    label: 'Малина',
    icon: '🫐',
    hasVariety: true,
    varieties: [
      { value: 'summer', label: 'Летняя' },
      { value: 'remontant', label: 'Ремонтантная' },
    ],
  },
  {
    type: 'blackberry',
    label: 'Ежевика',
    icon: '🫐',
    hasVariety: true,
    varieties: [
      { value: 'summer', label: 'Летняя' },
      { value: 'remontant', label: 'Ремонтантная' },
    ],
  },
  {
    type: 'currant',
    label: 'Смородина',
    icon: '🍇',
    hasVariety: false,
  },
  {
    type: 'blueberry',
    label: 'Голубика',
    icon: '🫐',
    hasVariety: false,
  },
  {
    type: 'honeysuckle',
    label: 'Жимолость',
    icon: '🍇',
    hasVariety: false,
  },
  {
    type: 'gooseberry',
    label: 'Крыжовник',
    icon: '🍈',
    hasVariety: false,
  },
];

// Регионы
export const REGIONS: RegionConfig[] = [
  { value: 'south', label: 'Юг' },
  { value: 'central', label: 'Средняя полоса' },
  { value: 'north', label: 'Север' },
];

// Хелперы

/**
 * Получить конфигурацию культуры по типу
 */
export function getCultureConfig(type: CultureType): CultureConfig | undefined {
  return PLANTING_CULTURES.find((c) => c.type === type);
}

/**
 * Получить label региона
 */
export function getRegionLabel(region: Region): string {
  return REGIONS.find((r) => r.value === region)?.label || region;
}

/**
 * Получить culture_code для события из посадки
 * Маппинг: { cultureType, variety } -> "клубника ремонтантная"
 */
export function getCultureCode(planting: UserPlanting): string {
  const cultureMap: Record<CultureType, string> = {
    strawberry: 'клубника',
    raspberry: 'малина',
    blackberry: 'ежевика',
    currant: 'смородина',
    blueberry: 'голубика',
    honeysuckle: 'жимолость',
    gooseberry: 'крыжовник',
  };

  const varietyMap: Record<string, string> = {
    early: 'ранняя',
    mid: 'средняя',
    late: 'поздняя',
    remontant: 'ремонтантная',
    summer: 'летняя',
  };

  const cultureName = cultureMap[planting.cultureType];

  if (planting.variety) {
    const varietyName = varietyMap[planting.variety];
    return `${cultureName} ${varietyName}`;
  }

  return cultureName;
}

/**
 * Получить label посадки для отображения
 * Например: "Клубника (ремонтантный)" или "Смородина"
 */
export function getPlantingLabel(planting: UserPlanting): string {
  const config = getCultureConfig(planting.cultureType);
  if (!config) return planting.cultureType;

  if (planting.variety && config.varieties) {
    const varietyConfig = config.varieties.find((v) => v.value === planting.variety);
    if (varietyConfig) {
      return `${config.label} (${varietyConfig.label})`;
    }
  }

  return config.label;
}

/**
 * Получить emoji иконку культуры (для select options)
 */
export function getCultureIcon(type: CultureType): string {
  return getCultureConfig(type)?.icon || '🌱';
}

/**
 * Получить SVG компонент иконки культуры
 */
export function getCultureIconComponent(type: CultureType): FunctionComponent<SVGProps<SVGSVGElement>> {
  return CultureIconComponents[type];
}

/**
 * Получить CultureType из cultureCode
 * Обратный маппинг: "клубника ремонтантная" -> "strawberry"
 */
export function getCultureTypeFromCode(cultureCode: string): CultureType | null {
  const cultureMap: Record<string, CultureType> = {
    'клубника': 'strawberry',
    'малина': 'raspberry',
    'ежевика': 'blackberry',
    'смородина': 'currant',
    'голубика': 'blueberry',
    'жимолость': 'honeysuckle',
    'крыжовник': 'gooseberry',
  };

  // Проверяем полное совпадение
  if (cultureMap[cultureCode]) {
    return cultureMap[cultureCode];
  }

  // Проверяем, начинается ли с названия культуры (для "клубника ремонтантная" и т.д.)
  for (const [name, type] of Object.entries(cultureMap)) {
    if (cultureCode.startsWith(name)) {
      return type;
    }
  }

  return null;
}

/**
 * Получить SVG компонент иконки по cultureCode
 */
export function getCultureIconFromCode(cultureCode: string): FunctionComponent<SVGProps<SVGSVGElement>> | null {
  const cultureType = getCultureTypeFromCode(cultureCode);
  if (cultureType) {
    return CultureIconComponents[cultureType];
  }
  return null;
}
