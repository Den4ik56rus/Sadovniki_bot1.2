/**
 * CultureFilter - Dropdown для фильтрации событий по культурам
 * Отображается в хедере когда календарь развёрнут
 */

import { useRef, useEffect } from 'react';
import { useUIStore } from '@store/uiStore';
import { usePlantingsStore } from '@store/plantingsStore';
import { useTelegramHaptic } from '@hooks/useTelegramHaptic';
import { getCultureIconComponent, getPlantingLabel } from '@constants/plantingCultures';
import styles from './CultureFilter.module.css';

export function CultureFilter() {
  const {
    isCultureFilterOpen,
    selectedCultureFilter,
    toggleCultureFilter,
    closeCultureFilter,
    setCultureFilter
  } = useUIStore();
  const { plantings } = usePlantingsStore();
  const { light } = useTelegramHaptic();
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Закрытие по клику вне dropdown
  useEffect(() => {
    if (!isCultureFilterOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        closeCultureFilter();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isCultureFilterOpen, closeCultureFilter]);

  const handleToggle = () => {
    light();
    toggleCultureFilter();
  };

  const handleSelect = (plantingId: string | null) => {
    light();
    setCultureFilter(plantingId);
  };

  // Текущий выбранный фильтр для отображения
  const selectedPlanting = selectedCultureFilter
    ? plantings.find(p => p.id === selectedCultureFilter)
    : null;

  const displayLabel = selectedPlanting
    ? getPlantingLabel(selectedPlanting)
    : 'Все культуры';

  // Иконка для кнопки
  const IconComponent = selectedPlanting
    ? getCultureIconComponent(selectedPlanting.cultureType)
    : null;

  return (
    <div className={styles.container} ref={dropdownRef}>
      <button
        className={`${styles.filterButton} ${isCultureFilterOpen ? styles.active : ''}`}
        onClick={handleToggle}
        aria-label="Фильтр по культурам"
        aria-expanded={isCultureFilterOpen}
      >
        {IconComponent ? (
          <span className={styles.buttonIcon}>
            <IconComponent />
          </span>
        ) : (
          <FilterIcon />
        )}
        <span className={styles.buttonText}>{displayLabel}</span>
        <span className={`${styles.chevron} ${isCultureFilterOpen ? styles.chevronUp : ''}`}>
          <ChevronDownIcon />
        </span>
      </button>

      {isCultureFilterOpen && (
        <div className={styles.dropdown}>
          {/* Вариант "Все культуры" */}
          <button
            className={`${styles.option} ${selectedCultureFilter === null ? styles.selected : ''}`}
            onClick={() => handleSelect(null)}
          >
            <span className={styles.optionIcon}>
              <AllCulturesIcon />
            </span>
            <span className={styles.optionLabel}>Все культуры</span>
            {selectedCultureFilter === null && <CheckIcon />}
          </button>

          {/* Разделитель если есть посадки */}
          {plantings.length > 0 && <div className={styles.divider} />}

          {/* Посадки пользователя */}
          {plantings.map(planting => {
            const PlantingIcon = getCultureIconComponent(planting.cultureType);
            const isSelected = selectedCultureFilter === planting.id;

            return (
              <button
                key={planting.id}
                className={`${styles.option} ${isSelected ? styles.selected : ''}`}
                onClick={() => handleSelect(planting.id)}
              >
                <span className={styles.optionIcon}>
                  <PlantingIcon />
                </span>
                <span className={styles.optionLabel}>{getPlantingLabel(planting)}</span>
                {isSelected && <CheckIcon />}
              </button>
            );
          })}

          {/* Пусто - нет посадок */}
          {plantings.length === 0 && (
            <div className={styles.emptyHint}>
              Добавьте посадки в разделе<br />"Мои посадки"
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// SVG иконки
function FilterIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="22,3 2,3 10,12.46 10,19 14,21 14,12.46" />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="6,9 12,15 18,9" />
    </svg>
  );
}

function AllCulturesIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="12" cy="12" r="3" />
      <circle cx="12" cy="5" r="2" />
      <circle cx="12" cy="19" r="2" />
      <circle cx="5" cy="12" r="2" />
      <circle cx="19" cy="12" r="2" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <polyline points="20,6 9,17 4,12" />
    </svg>
  );
}
