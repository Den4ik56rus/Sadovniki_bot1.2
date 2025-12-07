/**
 * Culture Icons - SVG иконки культур
 */

import StrawberryIcon from './strawberry.svg?react';
import RaspberryIcon from './raspberry.svg?react';
import BlackberryIcon from './blackberry.svg?react';
import CurrantIcon from './currant.svg?react';
import BlueberryIcon from './blueberry.svg?react';
import HoneysuckleIcon from './honeysuckle.svg?react';
import GooseberryIcon from './gooseberry.svg?react';

export {
  StrawberryIcon,
  RaspberryIcon,
  BlackberryIcon,
  CurrantIcon,
  BlueberryIcon,
  HoneysuckleIcon,
  GooseberryIcon,
};

// Маппинг типа культуры на иконку
export const CultureIcons = {
  strawberry: StrawberryIcon,
  raspberry: RaspberryIcon,
  blackberry: BlackberryIcon,
  currant: CurrantIcon,
  blueberry: BlueberryIcon,
  honeysuckle: HoneysuckleIcon,
  gooseberry: GooseberryIcon,
} as const;
