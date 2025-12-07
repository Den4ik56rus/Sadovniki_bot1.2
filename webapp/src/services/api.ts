/**
 * API Service - Взаимодействие с backend
 */

import type { CalendarEvent, EventStatus } from '@/types';

const API_BASE = import.meta.env.VITE_API_URL || '';

interface ApiError {
  message: string;
  status: number;
}

class ApiService {
  private getInitData(): string {
    return window.Telegram?.WebApp?.initData || '';
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const initData = this.getInitData();

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'X-Telegram-Init-Data': initData,
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error: ApiError = {
        message: await response.text(),
        status: response.status,
      };
      throw error;
    }

    // Для DELETE возвращаем null
    if (response.status === 204) {
      return null as T;
    }

    return response.json();
  }

  /**
   * Проверка, работаем ли мы в Telegram WebApp
   */
  isTelegramWebApp(): boolean {
    return !!window.Telegram?.WebApp?.initData;
  }

  /**
   * Проверка, настроен ли API URL
   */
  isApiConfigured(): boolean {
    return !!API_BASE;
  }

  /**
   * Получить все события пользователя
   */
  async getEvents(start?: string, end?: string): Promise<CalendarEvent[]> {
    const params = new URLSearchParams();
    if (start) params.set('start', start);
    if (end) params.set('end', end);

    const query = params.toString();
    const endpoint = `/api/events${query ? `?${query}` : ''}`;

    return this.request<CalendarEvent[]>(endpoint);
  }

  /**
   * Получить событие по ID
   */
  async getEvent(id: string): Promise<CalendarEvent> {
    return this.request<CalendarEvent>(`/api/events/${id}`);
  }

  /**
   * Создать событие
   */
  async createEvent(
    event: Omit<CalendarEvent, 'id' | 'createdAt' | 'updatedAt'>
  ): Promise<CalendarEvent> {
    return this.request<CalendarEvent>('/api/events', {
      method: 'POST',
      body: JSON.stringify(event),
    });
  }

  /**
   * Обновить событие
   */
  async updateEvent(
    id: string,
    event: Partial<CalendarEvent>
  ): Promise<CalendarEvent> {
    return this.request<CalendarEvent>(`/api/events/${id}`, {
      method: 'PUT',
      body: JSON.stringify(event),
    });
  }

  /**
   * Удалить событие
   */
  async deleteEvent(id: string): Promise<void> {
    return this.request<void>(`/api/events/${id}`, {
      method: 'DELETE',
    });
  }

  /**
   * Изменить статус события
   */
  async updateEventStatus(
    id: string,
    status: EventStatus
  ): Promise<CalendarEvent> {
    return this.request<CalendarEvent>(`/api/events/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
  }
}

export const api = new ApiService();
