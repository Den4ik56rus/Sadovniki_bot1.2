/**
 * SideMenu - Боковое меню
 * Slide-in меню с навигацией и фильтрами
 */

import { useState } from 'react';
import { useUIStore } from '@store/uiStore';
import { useFilterStore } from '@store/filterStore';
import { useTelegramBackButton } from '@hooks/useTelegramBackButton';
import { useTelegramHaptic } from '@hooks/useTelegramHaptic';
import { UI_TEXT } from '@constants/ui';
import { EVENT_TYPES } from '@constants/eventTypes';
import type { EventType } from '@/types';
import styles from './SideMenu.module.css';

// Культуры с подтипами (клубника и малина)
const CULTURES_WITH_SUBTYPES = [
  {
    key: 'strawberry',
    code: 'клубника',
    label: 'Клубника',
    Icon: StrawberryIcon,
    options: [
      { code: 'клубника ремонтантная', label: 'ремонтантная' },
      { code: 'клубника летняя', label: 'летняя' },
    ],
  },
  {
    key: 'raspberry',
    code: 'малина',
    label: 'Малина',
    Icon: RaspberryIcon,
    options: [
      { code: 'малина ремонтантная', label: 'ремонтантная' },
      { code: 'малина летняя', label: 'летняя' },
    ],
  },
];

// Остальные культуры без подтипов
const SIMPLE_CULTURES = [
  { code: 'смородина', label: 'Смородина', Icon: CurrantIcon },
  { code: 'голубика', label: 'Голубика', Icon: BlueberryIcon },
  { code: 'жимолость', label: 'Жимолость', Icon: HoneysuckleIcon },
  { code: 'крыжовник', label: 'Крыжовник', Icon: GooseberryIcon },
  { code: 'ежевика', label: 'Ежевика', Icon: BlackberryIcon },
];

export function SideMenu() {
  const { isSideMenuOpen, closeSideMenu } = useUIStore();
  const {
    visibleTypes,
    visibleCultures,
    toggleTypeVisibility,
    toggleCultureVisibility,
  } = useFilterStore();
  const { light } = useTelegramHaptic();
  const [expandedCultures, setExpandedCultures] = useState<Record<string, boolean>>({});
  const [isClosing, setIsClosing] = useState(false);

  // BackButton закрывает меню
  useTelegramBackButton(() => handleClose(), isSideMenuOpen);

  const handleClose = () => {
    light();
    setIsClosing(true);
    setTimeout(() => {
      setIsClosing(false);
      closeSideMenu();
    }, 200);
  };

  const handleToggleType = (type: EventType) => {
    light();
    toggleTypeVisibility(type);
  };

  const handleToggleCulture = (culture: string) => {
    light();
    toggleCultureVisibility(culture);
  };

  const toggleCultureExpanded = (key: string) => {
    light();
    setExpandedCultures((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  if (!isSideMenuOpen && !isClosing) return null;

  return (
    <div className={`${styles.overlay} ${isClosing ? styles.overlayClosing : ''}`} onClick={handleClose}>
      <nav
        className={`${styles.menu} ${isClosing ? styles.menuClosing : ''}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.header}>
          <h2 className={styles.title}>Садовники</h2>
        </div>

        <ul className={styles.list}>
          <li>
            <button className={`${styles.item} ${styles.active}`}>
              <CalendarIcon />
              <span>{UI_TEXT.menuCalendar}</span>
            </button>
          </li>
          <li>
            <button className={styles.item} disabled>
              <SettingsIcon />
              <span>{UI_TEXT.menuSettings}</span>
            </button>
          </li>
          <li>
            <button className={styles.item} disabled>
              <InfoIcon />
              <span>{UI_TEXT.menuAbout}</span>
            </button>
          </li>
        </ul>

        {/* Filter section: Event Types */}
        <div className={styles.filterSection}>
          <div className={styles.filterHeader}>
            <span className={styles.filterTitle}>Типы работ</span>
          </div>
          <ul className={styles.filterList}>
            {(Object.keys(EVENT_TYPES) as EventType[]).map((type) => {
              const info = EVENT_TYPES[type];
              const isVisible = visibleTypes[type];
              return (
                <li key={type} className={styles.filterItem}>
                  <div className={styles.filterItemContent}>
                    <span
                      className={styles.filterColor}
                      style={{ backgroundColor: info.color }}
                    />
                    <span className={`${styles.filterLabel} ${!isVisible ? styles.filterLabelHidden : ''}`}>
                      {info.label}
                    </span>
                  </div>
                  <button
                    className={styles.visibilityButton}
                    onClick={() => handleToggleType(type)}
                    aria-label={isVisible ? 'Скрыть' : 'Показать'}
                  >
                    {isVisible ? <EyeIcon /> : <EyeOffIcon />}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        {/* Filter section: Cultures */}
        <div className={styles.filterSection}>
          <div className={styles.filterHeader}>
            <span className={styles.filterTitle}>Культуры</span>
          </div>
          <ul className={styles.filterList}>
            {/* Культуры с подтипами (клубника, малина) */}
            {CULTURES_WITH_SUBTYPES.map((culture) => {
              const isExpanded = expandedCultures[culture.key];
              const isCultureVisible = visibleCultures[culture.code] ?? true;
              return (
                <li key={culture.key} className={styles.filterGroup}>
                  <div className={styles.filterItem}>
                    <button
                      className={styles.filterExpandButton}
                      onClick={() => toggleCultureExpanded(culture.key)}
                    >
                      <span className={styles.filterGroupIcon}><culture.Icon /></span>
                      <span className={`${styles.filterLabel} ${!isCultureVisible ? styles.filterLabelHidden : ''}`}>
                        {culture.label}
                      </span>
                      <span className={`${styles.expandIcon} ${isExpanded ? styles.expandIconOpen : ''}`}>
                        <ChevronIcon />
                      </span>
                    </button>
                    <button
                      className={styles.visibilityButton}
                      onClick={() => handleToggleCulture(culture.code)}
                      aria-label={isCultureVisible ? 'Скрыть' : 'Показать'}
                    >
                      {isCultureVisible ? <EyeIcon /> : <EyeOffIcon />}
                    </button>
                  </div>
                  {isExpanded && (
                    <ul className={styles.filterSubList}>
                      {culture.options.map((option) => {
                        const isVisible = visibleCultures[option.code] ?? true;
                        return (
                          <li key={option.code} className={styles.filterItem}>
                            <div className={styles.filterItemContent}>
                              <span className={`${styles.filterLabel} ${!isVisible ? styles.filterLabelHidden : ''}`}>
                                {option.label}
                              </span>
                            </div>
                            <button
                              className={styles.visibilityButton}
                              onClick={() => handleToggleCulture(option.code)}
                              aria-label={isVisible ? 'Скрыть' : 'Показать'}
                            >
                              {isVisible ? <EyeIcon /> : <EyeOffIcon />}
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </li>
              );
            })}
            {/* Простые культуры без подтипов */}
            {SIMPLE_CULTURES.map((culture) => {
              const isVisible = visibleCultures[culture.code] ?? true;
              return (
                <li key={culture.code} className={styles.filterItem}>
                  <div className={styles.filterItemContent}>
                    <span className={styles.filterGroupIcon}><culture.Icon /></span>
                    <span className={`${styles.filterLabel} ${!isVisible ? styles.filterLabelHidden : ''}`}>
                      {culture.label}
                    </span>
                  </div>
                  <button
                    className={styles.visibilityButton}
                    onClick={() => handleToggleCulture(culture.code)}
                    aria-label={isVisible ? 'Скрыть' : 'Показать'}
                  >
                    {isVisible ? <EyeIcon /> : <EyeOffIcon />}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        <div className={styles.footer}>
          <span className={styles.version}>v1.0.0</span>
        </div>
      </nav>
    </div>
  );
}

// Inline SVG icons
function CalendarIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

function InfoIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}

function ChevronIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

// Berry icons
function StrawberryIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <path d="M12 2C10.5 2 9.5 3 9.5 3L8 4.5C8 4.5 6 3.5 5 4.5C4 5.5 5 7.5 5 7.5L4 9C4 9 2 10 2 12C2 18 7 22 12 22C17 22 22 18 22 12C22 10 20 9 20 9L19 7.5C19 7.5 20 5.5 19 4.5C18 3.5 16 4.5 16 4.5L14.5 3C14.5 3 13.5 2 12 2Z" fill="#E53935" stroke="#C62828" strokeWidth="1"/>
      <ellipse cx="8" cy="12" rx="1" ry="1.5" fill="#FFEB3B"/>
      <ellipse cx="12" cy="10" rx="1" ry="1.5" fill="#FFEB3B"/>
      <ellipse cx="16" cy="12" rx="1" ry="1.5" fill="#FFEB3B"/>
      <ellipse cx="10" cy="15" rx="1" ry="1.5" fill="#FFEB3B"/>
      <ellipse cx="14" cy="15" rx="1" ry="1.5" fill="#FFEB3B"/>
      <ellipse cx="12" cy="18" rx="1" ry="1.5" fill="#FFEB3B"/>
      <path d="M10 3L12 1L14 3" stroke="#4CAF50" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  );
}

function RaspberryIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <circle cx="9" cy="10" r="3" fill="#E91E63" stroke="#C2185B" strokeWidth="0.5"/>
      <circle cx="15" cy="10" r="3" fill="#E91E63" stroke="#C2185B" strokeWidth="0.5"/>
      <circle cx="12" cy="8" r="3" fill="#E91E63" stroke="#C2185B" strokeWidth="0.5"/>
      <circle cx="9" cy="14" r="3" fill="#E91E63" stroke="#C2185B" strokeWidth="0.5"/>
      <circle cx="15" cy="14" r="3" fill="#E91E63" stroke="#C2185B" strokeWidth="0.5"/>
      <circle cx="12" cy="12" r="3" fill="#E91E63" stroke="#C2185B" strokeWidth="0.5"/>
      <circle cx="12" cy="16" r="3" fill="#E91E63" stroke="#C2185B" strokeWidth="0.5"/>
      <path d="M10 5L12 2L14 5" stroke="#4CAF50" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  );
}

function CurrantIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <circle cx="8" cy="14" r="3.5" fill="#7B1FA2" stroke="#6A1B9A" strokeWidth="0.5"/>
      <circle cx="14" cy="12" r="3.5" fill="#7B1FA2" stroke="#6A1B9A" strokeWidth="0.5"/>
      <circle cx="10" cy="18" r="3" fill="#7B1FA2" stroke="#6A1B9A" strokeWidth="0.5"/>
      <circle cx="16" cy="17" r="2.5" fill="#7B1FA2" stroke="#6A1B9A" strokeWidth="0.5"/>
      <path d="M12 4L12 10" stroke="#4CAF50" strokeWidth="1.5"/>
      <path d="M12 4C12 4 8 6 8 10" stroke="#4CAF50" strokeWidth="1.5" fill="none"/>
      <path d="M12 4C12 4 16 6 16 9" stroke="#4CAF50" strokeWidth="1.5" fill="none"/>
      <ellipse cx="12" cy="3" rx="2" ry="1" fill="#81C784"/>
    </svg>
  );
}

function BlueberryIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="13" r="7" fill="#3949AB" stroke="#303F9F" strokeWidth="1"/>
      <circle cx="12" cy="8" r="2" fill="#5C6BC0"/>
      <path d="M9 7L12 5L15 7" stroke="#1B5E20" strokeWidth="1.5" strokeLinecap="round"/>
      <ellipse cx="12" cy="5" rx="1.5" ry="1" fill="#4CAF50"/>
    </svg>
  );
}

function HoneysuckleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <ellipse cx="12" cy="14" rx="5" ry="7" fill="#3F51B5" stroke="#303F9F" strokeWidth="1"/>
      <ellipse cx="12" cy="12" rx="3" ry="4" fill="#5C6BC0" opacity="0.5"/>
      <path d="M10 5L12 3L14 5" stroke="#4CAF50" strokeWidth="2" strokeLinecap="round"/>
      <ellipse cx="12" cy="4" rx="2" ry="1" fill="#81C784"/>
    </svg>
  );
}

function GooseberryIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <ellipse cx="12" cy="13" rx="6" ry="7" fill="#8BC34A" stroke="#689F38" strokeWidth="1"/>
      <path d="M7 10C7 10 9 8 12 10C15 12 17 10 17 10" stroke="#689F38" strokeWidth="0.8" opacity="0.6"/>
      <path d="M7 13C7 13 9 11 12 13C15 15 17 13 17 13" stroke="#689F38" strokeWidth="0.8" opacity="0.6"/>
      <path d="M8 16C8 16 10 14 12 16C14 18 16 16 16 16" stroke="#689F38" strokeWidth="0.8" opacity="0.6"/>
      <path d="M10 4L12 2L14 4" stroke="#33691E" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  );
}

function BlackberryIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <circle cx="9" cy="10" r="3" fill="#37474F" stroke="#263238" strokeWidth="0.5"/>
      <circle cx="15" cy="10" r="3" fill="#37474F" stroke="#263238" strokeWidth="0.5"/>
      <circle cx="12" cy="8" r="3" fill="#37474F" stroke="#263238" strokeWidth="0.5"/>
      <circle cx="9" cy="14" r="3" fill="#37474F" stroke="#263238" strokeWidth="0.5"/>
      <circle cx="15" cy="14" r="3" fill="#37474F" stroke="#263238" strokeWidth="0.5"/>
      <circle cx="12" cy="12" r="3" fill="#37474F" stroke="#263238" strokeWidth="0.5"/>
      <circle cx="12" cy="16" r="3" fill="#37474F" stroke="#263238" strokeWidth="0.5"/>
      <path d="M10 5L12 2L14 5" stroke="#4CAF50" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  );
}
