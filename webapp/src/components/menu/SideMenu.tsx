/**
 * SideMenu - Боковое меню
 * Slide-in меню с навигацией и фильтрами
 */

import { useState, useEffect } from 'react';
import { useUIStore } from '@store/uiStore';
import { useFilterStore } from '@store/filterStore';
import { usePlantingsStore } from '@store/plantingsStore';
import { useTelegramBackButton } from '@hooks/useTelegramBackButton';
import { useTelegramHaptic } from '@hooks/useTelegramHaptic';
import { EVENT_TYPES } from '@constants/eventTypes';
import { getCultureIconComponent, getPlantingLabel, getCultureCode } from '@constants/plantingCultures';
import type { EventType } from '@/types';
import styles from './SideMenu.module.css';

export function SideMenu() {
  const { isSideMenuOpen, closeSideMenu, openPlantingsPage } = useUIStore();
  const {
    visibleTypes,
    visibleCultures,
    toggleTypeVisibility,
    toggleCultureVisibility,
  } = useFilterStore();
  const { plantings, fetchPlantings } = usePlantingsStore();
  const { light } = useTelegramHaptic();
  const [isClosing, setIsClosing] = useState(false);

  // Загружаем посадки при открытии меню
  useEffect(() => {
    if (isSideMenuOpen) {
      fetchPlantings();
    }
  }, [isSideMenuOpen, fetchPlantings]);

  // Получаем данные пользователя из Telegram
  const tg = window.Telegram?.WebApp;
  const user = tg?.initDataUnsafe?.user;
  const userName = user?.first_name || 'Пользователь';
  const userEmail = user?.username ? `@${user.username}` : '';
  const userInitial = userName.charAt(0).toUpperCase();

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

  const handleToggleCulture = (cultureCode: string) => {
    light();
    toggleCultureVisibility(cultureCode);
  };

  const handleOpenPlantings = () => {
    light();
    openPlantingsPage();
  };

  if (!isSideMenuOpen && !isClosing) return null;

  return (
    <div className={`${styles.overlay} ${isClosing ? styles.overlayClosing : ''}`} onClick={handleClose}>
      <nav
        className={`${styles.menu} ${isClosing ? styles.menuClosing : ''}`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* User profile header */}
        <div className={styles.header}>
          <div className={styles.userProfile}>
            <div className={styles.userAvatar}>
              {userInitial}
            </div>
            <div className={styles.userInfo}>
              <span className={styles.userName}>{userName}</span>
              {userEmail && <span className={styles.userEmail}>{userEmail}</span>}
            </div>
            <button className={styles.settingsButton} disabled aria-label="Настройки">
              <SettingsIcon />
            </button>
          </div>
        </div>

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

        {/* Filter section: User Plantings */}
        <div className={styles.filterSection}>
          <div className={styles.filterHeader}>
            <span className={styles.filterTitle}>Мои посадки</span>
          </div>

          {plantings.length === 0 ? (
            <div className={styles.emptyPlantings}>
              <p>Добавьте свои культуры</p>
            </div>
          ) : (
            <ul className={styles.filterList}>
              {plantings.map((planting) => {
                const cultureCode = getCultureCode(planting);
                const isVisible = visibleCultures[cultureCode] ?? true;
                const CultureIcon = getCultureIconComponent(planting.cultureType);
                return (
                  <li key={planting.id} className={styles.filterItem}>
                    <div className={styles.filterItemContent}>
                      <span className={styles.filterGroupIcon}>
                        <CultureIcon width={20} height={20} />
                      </span>
                      <span className={`${styles.filterLabel} ${!isVisible ? styles.filterLabelHidden : ''}`}>
                        {getPlantingLabel(planting)}
                      </span>
                    </div>
                    <button
                      className={styles.visibilityButton}
                      onClick={() => handleToggleCulture(cultureCode)}
                      aria-label={isVisible ? 'Скрыть' : 'Показать'}
                    >
                      {isVisible ? <EyeIcon /> : <EyeOffIcon />}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          {/* Edit plantings button */}
          <button
            className={styles.editPlantingsButton}
            onClick={handleOpenPlantings}
          >
            <EditIcon />
            <span>Редактировать посадки</span>
          </button>
        </div>

        <div className={styles.footer}>
          <span className={styles.version}>v1.0.0</span>
        </div>
      </nav>
    </div>
  );
}

// Inline SVG icons
function SettingsIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
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

function EditIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}
