/**
 * PlantingForm - Форма создания/редактирования посадки
 */

import { useEffect, useState, useRef } from 'react';
import { useUIStore } from '@store/uiStore';
import { usePlantingsStore } from '@store/plantingsStore';
import { useTelegramBackButton } from '@hooks/useTelegramBackButton';
import { useTelegramHaptic } from '@hooks/useTelegramHaptic';
import { PLANTING_CULTURES, getCultureConfig, getCultureIconComponent } from '@constants/plantingCultures';
import type { CultureType, Variety } from '@/types';
import styles from './PlantingForm.module.css';

export function PlantingForm() {
  const { isPlantingFormOpen, editingPlantingId, closePlantingForm } = useUIStore();
  const { plantings, addPlanting, updatePlanting, getPlantingById } = usePlantingsStore();
  const { medium, light, success, error: hapticError } = useTelegramHaptic();

  const [cultureType, setCultureType] = useState<CultureType | ''>('');
  const [variety, setVariety] = useState<Variety>(null);
  const [fruitingStart, setFruitingStart] = useState('');
  const [fruitingEnd, setFruitingEnd] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCultureDropdownOpen, setIsCultureDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const isEditing = !!editingPlantingId;
  const cultureConfig = cultureType ? getCultureConfig(cultureType) : null;

  // Загружаем данные при редактировании
  useEffect(() => {
    if (isPlantingFormOpen && editingPlantingId) {
      const planting = getPlantingById(editingPlantingId);
      if (planting) {
        setCultureType(planting.cultureType);
        setVariety(planting.variety);
        setFruitingStart(planting.fruitingStart || '');
        setFruitingEnd(planting.fruitingEnd || '');
      }
    } else if (isPlantingFormOpen && !editingPlantingId) {
      // Reset form for new planting
      setCultureType('');
      setVariety(null);
      setFruitingStart('');
      setFruitingEnd('');
    }
    setIsCultureDropdownOpen(false);
  }, [isPlantingFormOpen, editingPlantingId, getPlantingById]);

  // Закрытие dropdown при клике вне
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsCultureDropdownOpen(false);
      }
    };
    if (isCultureDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isCultureDropdownOpen]);

  // BackButton закрывает форму
  useTelegramBackButton(() => {
    medium();
    closePlantingForm();
  }, isPlantingFormOpen);

  const handleCultureChange = (newCulture: CultureType) => {
    light();
    setCultureType(newCulture);
    setIsCultureDropdownOpen(false);
    // Reset variety when culture changes
    setVariety(null);
  };

  const selectedCultureConfig = cultureType ? getCultureConfig(cultureType) : null;
  const SelectedCultureIcon = cultureType ? getCultureIconComponent(cultureType) : null;

  const handleSubmit = async () => {
    if (!cultureType) return;

    // Валидация сорта для культур с сортами
    const config = getCultureConfig(cultureType);
    if (config?.hasVariety && !variety) {
      hapticError();
      return;
    }

    setIsSubmitting(true);
    light();

    try {
      if (isEditing && editingPlantingId) {
        await updatePlanting(editingPlantingId, {
          cultureType,
          variety,
          fruitingStart: fruitingStart || null,
          fruitingEnd: fruitingEnd || null,
        });
      } else {
        await addPlanting({
          cultureType,
          variety,
          fruitingStart: fruitingStart || null,
          fruitingEnd: fruitingEnd || null,
        });
      }
      success();
      closePlantingForm();
    } catch {
      hapticError();
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isPlantingFormOpen) return null;

  const canSubmit = cultureType && (!cultureConfig?.hasVariety || variety);

  return (
    <div className={styles.overlay}>
      <div className={styles.form}>
        {/* Header */}
        <header className={styles.header}>
          <button
            className={styles.cancelButton}
            onClick={() => {
              medium();
              closePlantingForm();
            }}
          >
            Отмена
          </button>
          <h2 className={styles.title}>
            {isEditing ? 'Редактировать' : 'Новая культура'}
          </h2>
          <button
            className={styles.saveButton}
            onClick={handleSubmit}
            disabled={!canSubmit || isSubmitting}
          >
            {isSubmitting ? '...' : 'Готово'}
          </button>
        </header>

        {/* Content */}
        <div className={styles.content}>
          {/* Culture Select - Custom dropdown with SVG icons */}
          <div className={styles.field}>
            <label className={styles.label}>Культура</label>
            <div className={styles.cultureDropdown} ref={dropdownRef}>
              <button
                type="button"
                className={styles.cultureButton}
                onClick={() => {
                  light();
                  setIsCultureDropdownOpen(!isCultureDropdownOpen);
                }}
              >
                {SelectedCultureIcon ? (
                  <>
                    <span className={styles.cultureButtonIcon}>
                      <SelectedCultureIcon width={24} height={24} />
                    </span>
                    <span className={styles.cultureButtonLabel}>
                      {selectedCultureConfig?.label}
                    </span>
                  </>
                ) : (
                  <span className={styles.cultureButtonPlaceholder}>
                    Выберите культуру
                  </span>
                )}
                <ChevronIcon
                  className={`${styles.cultureButtonChevron} ${isCultureDropdownOpen ? styles.cultureButtonChevronOpen : ''}`}
                />
              </button>

              {isCultureDropdownOpen && (
                <ul className={styles.cultureDropdownList}>
                  {PLANTING_CULTURES.map((c) => {
                    const CultureIcon = getCultureIconComponent(c.type);
                    return (
                      <li
                        key={c.type}
                        className={`${styles.cultureOption} ${cultureType === c.type ? styles.cultureOptionSelected : ''}`}
                        onClick={() => handleCultureChange(c.type)}
                      >
                        <span className={styles.cultureOptionIcon}>
                          <CultureIcon width={24} height={24} />
                        </span>
                        <span className={styles.cultureOptionLabel}>{c.label}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>

          {/* Variety Select (conditional) */}
          {cultureConfig?.hasVariety && cultureConfig.varieties && (
            <div className={styles.field}>
              <label className={styles.label}>Сорт</label>
              <div className={styles.selectWrapper}>
                <select
                  value={variety || ''}
                  onChange={(e) => {
                    light();
                    setVariety(e.target.value as Variety);
                  }}
                  className={styles.select}
                >
                  <option value="" disabled>
                    Выберите сорт
                  </option>
                  {cultureConfig.varieties.map((v) => (
                    <option key={v.value} value={v.value}>
                      {v.label}
                    </option>
                  ))}
                </select>
                <ChevronIcon className={styles.selectIcon} />
              </div>
            </div>
          )}

          {/* Fruiting Dates */}
          <div className={styles.field}>
            <label className={styles.label}>Даты плодоношения (опционально)</label>
            <div className={styles.dateRow}>
              <div className={styles.dateField}>
                <span className={styles.dateLabel}>Начало</span>
                <input
                  type="date"
                  value={fruitingStart}
                  onChange={(e) => {
                    light();
                    setFruitingStart(e.target.value);
                  }}
                  className={styles.dateInput}
                />
              </div>
              <div className={styles.dateSeparator}>—</div>
              <div className={styles.dateField}>
                <span className={styles.dateLabel}>Конец</span>
                <input
                  type="date"
                  value={fruitingEnd}
                  onChange={(e) => {
                    light();
                    setFruitingEnd(e.target.value);
                  }}
                  className={styles.dateInput}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      className={className}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}
