// Placeholder Page Component
import styles from './PlaceholderPage.module.css'

interface PlaceholderPageProps {
  icon: string
  title: string
  description: string
}

export function PlaceholderPage({ icon, title, description }: PlaceholderPageProps) {
  return (
    <div className={styles.container}>
      <div className={styles.content}>
        <span className={styles.icon}>{icon}</span>
        <h1 className={styles.title}>{title}</h1>
        <p className={styles.description}>{description}</p>
        <div className={styles.badge}>В разработке</div>
      </div>
    </div>
  )
}
