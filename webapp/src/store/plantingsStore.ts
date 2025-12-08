/**
 * Plantings Store - Состояние посадок пользователя с синхронизацией через API
 *
 * В Telegram WebApp: данные загружаются с сервера
 * В браузере (dev mode): используется localStorage
 */

import { create } from 'zustand';
import type { UserPlanting, Region, CreatePlantingData, UpdatePlantingData } from '@/types';
import { getCultureCode, getPlantingLabel } from '@constants/plantingCultures';
import { api } from '@services/api';
// ВРЕМЕННО: демо-посадки - удалить после тестирования!
import { getDemoPlantings } from '@/data/demoPlantings';

// Полифил для crypto.randomUUID
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

interface PlantingsStore {
  // State
  plantings: UserPlanting[];
  region: Region | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchPlantings: () => Promise<void>;
  addPlanting: (data: CreatePlantingData) => Promise<string>;
  updatePlanting: (id: string, data: UpdatePlantingData) => Promise<void>;
  deletePlanting: (id: string) => Promise<void>;
  fetchRegion: () => Promise<void>;
  setRegion: (region: Region) => Promise<void>;
  clearError: () => void;

  // Selectors
  getPlantingById: (id: string) => UserPlanting | undefined;
  getCultureCodeForPlanting: (planting: UserPlanting) => string;
  getPlantingLabelForPlanting: (planting: UserPlanting) => string;
}

// Store для работы с API (Telegram WebApp)
const createApiStore = (
  set: (fn: (state: PlantingsStore) => Partial<PlantingsStore>) => void,
  get: () => PlantingsStore
): PlantingsStore => ({
  plantings: [],
  region: null,
  isLoading: false,
  error: null,

  fetchPlantings: async () => {
    set(() => ({ isLoading: true, error: null }));
    try {
      const plantings = await api.getPlantings();
      set(() => ({ plantings }));
    } catch (error) {
      console.error('Failed to fetch plantings:', error);
      set(() => ({
        error: error instanceof Error ? error.message : 'Failed to fetch plantings',
      }));
    } finally {
      set(() => ({ isLoading: false }));
    }
  },

  addPlanting: async (data) => {
    set(() => ({ isLoading: true, error: null }));
    try {
      const planting = await api.createPlanting(data);
      set((state) => ({
        plantings: [...state.plantings, planting],
      }));
      return planting.id;
    } catch (error) {
      console.error('Failed to create planting:', error);
      set(() => ({
        error: error instanceof Error ? error.message : 'Failed to create planting',
      }));
      throw error;
    } finally {
      set(() => ({ isLoading: false }));
    }
  },

  updatePlanting: async (id, data) => {
    set(() => ({ isLoading: true, error: null }));
    try {
      const planting = await api.updatePlanting(id, data);
      set((state) => ({
        plantings: state.plantings.map((p) => (p.id === id ? planting : p)),
      }));
    } catch (error) {
      console.error('Failed to update planting:', error);
      set(() => ({
        error: error instanceof Error ? error.message : 'Failed to update planting',
      }));
      throw error;
    } finally {
      set(() => ({ isLoading: false }));
    }
  },

  deletePlanting: async (id) => {
    set(() => ({ isLoading: true, error: null }));
    try {
      await api.deletePlanting(id);
      set((state) => ({
        plantings: state.plantings.filter((p) => p.id !== id),
      }));
    } catch (error) {
      console.error('Failed to delete planting:', error);
      set(() => ({
        error: error instanceof Error ? error.message : 'Failed to delete planting',
      }));
      throw error;
    } finally {
      set(() => ({ isLoading: false }));
    }
  },

  fetchRegion: async () => {
    try {
      const data = await api.getRegion();
      set(() => ({ region: data.region }));
    } catch (error) {
      console.error('Failed to fetch region:', error);
    }
  },

  setRegion: async (region) => {
    try {
      await api.updateRegion(region);
      set(() => ({ region }));
    } catch (error) {
      console.error('Failed to update region:', error);
      set(() => ({
        error: error instanceof Error ? error.message : 'Failed to update region',
      }));
      throw error;
    }
  },

  clearError: () => set(() => ({ error: null })),

  getPlantingById: (id) => get().plantings.find((p) => p.id === id),
  getCultureCodeForPlanting: (planting) => getCultureCode(planting),
  getPlantingLabelForPlanting: (planting) => getPlantingLabel(planting),
});

// ВРЕМЕННО: кэшируем демо-посадки - удалить после тестирования!
const DEMO_PLANTINGS = getDemoPlantings();

// Store для локальной разработки (localStorage)
const createLocalStore = (
  set: (fn: (state: PlantingsStore) => Partial<PlantingsStore>) => void,
  get: () => PlantingsStore
): PlantingsStore => ({
  // ВРЕМЕННО: используем демо-посадки - удалить после тестирования!
  plantings: DEMO_PLANTINGS,
  region: null,
  isLoading: false,
  error: null,

  fetchPlantings: async () => {
    // В локальном режиме данные уже в store через persist
  },

  addPlanting: async (data) => {
    const id = generateUUID();
    const now = new Date().toISOString();
    const planting: UserPlanting = {
      id,
      cultureType: data.cultureType,
      variety: data.variety || null,
      fruitingStart: data.fruitingStart || null,
      fruitingEnd: data.fruitingEnd || null,
      createdAt: now,
      updatedAt: now,
    };
    set((state) => ({
      plantings: [...state.plantings, planting],
    }));
    return id;
  },

  updatePlanting: async (id, data) => {
    set((state) => ({
      plantings: state.plantings.map((p) =>
        p.id === id
          ? {
              ...p,
              ...data,
              updatedAt: new Date().toISOString(),
            }
          : p
      ),
    }));
  },

  deletePlanting: async (id) => {
    set((state) => ({
      plantings: state.plantings.filter((p) => p.id !== id),
    }));
  },

  fetchRegion: async () => {
    // В локальном режиме данные уже в store через persist
  },

  setRegion: async (region) => {
    set(() => ({ region }));
  },

  clearError: () => set(() => ({ error: null })),

  getPlantingById: (id) => get().plantings.find((p) => p.id === id),
  getCultureCodeForPlanting: (planting) => getCultureCode(planting),
  getPlantingLabelForPlanting: (planting) => getPlantingLabel(planting),
});

// Определяем, какой store использовать
const shouldUseApi = () => {
  return api.isTelegramWebApp() && api.isApiConfigured();
};

// ВРЕМЕННО: отключаем persist и используем демо-посадки напрямую
// Удалить после тестирования и вернуть persist!
export const usePlantingsStore = create<PlantingsStore>()(
  shouldUseApi()
    ? (set, get) => createApiStore(set, get)
    : (set, get) => createLocalStore(set, get)
);
