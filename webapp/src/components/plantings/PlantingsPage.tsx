/**
 * PlantingsPage - Страница редактирования посадок
 * Full-screen страница для управления посадками пользователя
 */

import { useEffect } from 'react';
import { useUIStore } from '@store/uiStore';
import { usePlantingsStore } from '@store/plantingsStore';
import { useTelegramBackButton } from '@hooks/useTelegramBackButton';
import { useTelegramHaptic } from '@hooks/useTelegramHaptic';
import { REGIONS, getRegionLabel } from '@constants/plantingCultures';
import type { Region } from '@/types';
import { PlantingCard } from './PlantingCard';
import styles from './PlantingsPage.module.css';

export function PlantingsPage() {
  const { isPlantingsPageOpen, closePlantingsPage, openPlantingForm } = useUIStore();
  const {
    plantings,
    region,
    isLoading,
    fetchPlantings,
    fetchRegion,
    setRegion,
  } = usePlantingsStore();
  const { medium, light, success } = useTelegramHaptic();

  // Загружаем данные при открытии
  useEffect(() => {
    if (isPlantingsPageOpen) {
      fetchPlantings();
      fetchRegion();
    }
  }, [isPlantingsPageOpen, fetchPlantings, fetchRegion]);

  // BackButton закрывает страницу
  useTelegramBackButton(() => {
    medium();
    closePlantingsPage();
  }, isPlantingsPageOpen);

  const handleRegionChange = async (newRegion: Region) => {
    light();
    try {
      await setRegion(newRegion);
      success();
    } catch {
      // Error handled in store
    }
  };

  const handleAddPlanting = () => {
    light();
    openPlantingForm();
  };

  const handleEditPlanting = (id: string) => {
    light();
    openPlantingForm(id);
  };

  if (!isPlantingsPageOpen) return null;

  return (
    <div className={styles.page}>
      {/* Header */}
      <header className={styles.header}>
        <button
          className={styles.backButton}
          onClick={() => {
            medium();
            closePlantingsPage();
          }}
          aria-label="Назад"
        >
          <BackIcon />
        </button>
        <h1 className={styles.title}>Мои посадки</h1>
      </header>

      {/* Content */}
      <main className={styles.content}>
        {/* Region Section */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Регион</h2>
          <div className={styles.regionSelect}>
            <select
              value={region || ''}
              onChange={(e) => handleRegionChange(e.target.value as Region)}
              className={styles.select}
            >
              <option value="" disabled>
                Выберите регион
              </option>
              {REGIONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
            <ChevronIcon className={styles.selectIcon} />
          </div>
          {region && (
            <p className={styles.regionHint}>
              Ваш регион: {getRegionLabel(region)}
            </p>
          )}
        </section>

        {/* Plantings Section */}
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Культуры</h2>

          {isLoading && plantings.length === 0 ? (
            <div className={styles.loading}>Загрузка...</div>
          ) : plantings.length === 0 ? (
            <div className={styles.empty}>
              <p>У вас пока нет добавленных культур</p>
              <p className={styles.emptyHint}>
                Добавьте культуры, которые вы выращиваете
              </p>
            </div>
          ) : (
            <div className={styles.plantingsList}>
              {plantings.map((planting) => (
                <PlantingCard
                  key={planting.id}
                  planting={planting}
                  onEdit={() => handleEditPlanting(planting.id)}
                />
              ))}
            </div>
          )}
        </section>
      </main>

      {/* Add Button */}
      <button className={styles.addButton} onClick={handleAddPlanting}>
        <PlusIcon />
        <span>Добавить культуру</span>
      </button>
    </div>
  );
}

// Icons
function BackIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="15 18 9 12 15 6" />
    </svg>
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

function PlusIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}
