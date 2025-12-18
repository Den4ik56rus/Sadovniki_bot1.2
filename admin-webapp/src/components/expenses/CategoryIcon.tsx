// Category Icons - Spendee-style icons for expense categories

import React from 'react'

// Map of icon names to SVG components
const icons: Record<string, React.ReactNode> = {
  // Реклама - megaphone
  megaphone: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M14 3V13C14 13 10 11 7 11H4C3.45 11 3 10.55 3 10V6C3 5.45 3.45 5 4 5H7C10 5 14 3 14 3Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M7 11V15L9 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx="15" cy="8" r="1" fill="currentColor"/>
    </svg>
  ),

  // Claude/AI - brain
  brain: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M9 2C6.5 2 5 4 5 6C4 6 3 7 3 8.5C3 10 4 11 5 11C5 13 6.5 15 9 15C11.5 15 13 13 13 11C14 11 15 10 15 8.5C15 7 14 6 13 6C13 4 11.5 2 9 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
      <path d="M9 6V11M7 8H11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),

  // LLM - cpu/chip
  cpu: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="5" y="5" width="8" height="8" rx="1" stroke="currentColor" strokeWidth="1.5"/>
      <rect x="7" y="7" width="4" height="4" rx="0.5" fill="currentColor"/>
      <path d="M7 3V5M11 3V5M7 13V15M11 13V15M3 7H5M3 11H5M13 7H15M13 11H15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),

  // Server
  server: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="3" y="3" width="12" height="5" rx="1" stroke="currentColor" strokeWidth="1.5"/>
      <rect x="3" y="10" width="12" height="5" rx="1" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="6" cy="5.5" r="1" fill="currentColor"/>
      <circle cx="6" cy="12.5" r="1" fill="currentColor"/>
      <path d="M10 5.5H12M10 12.5H12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),

  // Default - star
  default: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M9 2L11 7H16L12 10L13.5 15L9 12L4.5 15L6 10L2 7H7L9 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
    </svg>
  ),

  // Food & Drink - fork and knife
  food: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M5 2V7C5 8 6 9 7 9V16M7 2V5M9 2V5M9 9V16C9 9 10 8 10 7V2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M13 2C13 2 14 3 14 5C14 7 13 8 13 8V16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),

  // Shopping - bag
  shopping: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M4 5L5 15H13L14 5H4Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
      <path d="M7 5V4C7 3 8 2 9 2C10 2 11 3 11 4V5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),

  // Transport - car
  transport: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M3 10V13H4.5M14.5 13H15V10M3 10L4 6H14L15 10M3 10H15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx="5.5" cy="13" r="1.5" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="12.5" cy="13" r="1.5" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  ),

  // Home
  home: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M3 7L9 2L15 7V15H11V11H7V15H3V7Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
    </svg>
  ),

  // Bills
  bills: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="3" y="4" width="12" height="10" rx="1" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="9" cy="9" r="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M3 7H5M13 7H15M3 11H5M13 11H15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),

  // Entertainment
  entertainment: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="9" cy="9" r="6" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M7 7L12 9L7 11V7Z" fill="currentColor"/>
    </svg>
  ),

  // Travel
  travel: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M9 2L11 6H15L14 8L15 14H11L9 16L7 14H3L4 8L3 6H7L9 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
    </svg>
  ),

  // Healthcare
  healthcare: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="3" y="3" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M9 6V12M6 9H12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),

  // Education
  education: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M2 7L9 3L16 7L9 11L2 7Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
      <path d="M5 8.5V13L9 15L13 13V8.5" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
    </svg>
  ),

  // Subscriptions
  subscription: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="9" cy="9" r="6" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M9 5V9L12 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),

  // Salary/Income
  income: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M9 3V15M9 3L5 7M9 3L13 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),

  // Investments
  investment: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M3 14L7 10L10 12L15 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M12 4H15V7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),

  // Wallet/Money
  wallet: (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="2" y="4" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M2 8H16" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="13" cy="11" r="1" fill="currentColor"/>
    </svg>
  ),
}

interface CategoryIconProps {
  icon?: string
  color?: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export function CategoryIcon({ icon = 'default', color = '#6B7280', size = 'md', className }: CategoryIconProps) {
  const sizeMap = {
    sm: 28,
    md: 36,
    lg: 44,
  }

  const iconSize = sizeMap[size]
  const iconElement = icons[icon] || icons.default

  return (
    <div
      className={className}
      style={{
        width: iconSize,
        height: iconSize,
        borderRadius: '50%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: `${color}20`,
        color: color,
        flexShrink: 0,
      }}
    >
      {iconElement}
    </div>
  )
}

// Helper to get icon name from category name (fallback when icon field is not set)
export function getIconFromCategoryName(categoryName: string | undefined): string {
  const name = categoryName?.toLowerCase() || ''

  if (name.includes('реклама') || name.includes('advert') || name.includes('market')) return 'megaphone'
  if (name.includes('claude') || name.includes('ai') || name.includes('brain')) return 'brain'
  if (name.includes('llm') || name.includes('gpt') || name.includes('model')) return 'cpu'
  if (name.includes('server') || name.includes('сервер') || name.includes('host')) return 'server'
  if (name.includes('еда') || name.includes('food') || name.includes('ресторан')) return 'food'
  if (name.includes('покупк') || name.includes('shop')) return 'shopping'
  if (name.includes('транспорт') || name.includes('transport') || name.includes('такси')) return 'transport'
  if (name.includes('дом') || name.includes('home') || name.includes('аренда')) return 'home'
  if (name.includes('счет') || name.includes('bill') || name.includes('комм')) return 'bills'
  if (name.includes('развлеч') || name.includes('entertain')) return 'entertainment'
  if (name.includes('путешеств') || name.includes('travel')) return 'travel'
  if (name.includes('здоров') || name.includes('health') || name.includes('медиц')) return 'healthcare'
  if (name.includes('образован') || name.includes('educat') || name.includes('курс')) return 'education'
  if (name.includes('подписк') || name.includes('subscr')) return 'subscription'
  if (name.includes('доход') || name.includes('зарплата') || name.includes('income')) return 'income'
  if (name.includes('инвестиц') || name.includes('invest')) return 'investment'

  return 'default'
}
