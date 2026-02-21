// Photo Uploader — загрузка фото для рассылки

import { useState, useRef } from 'react'
import { useBroadcastStore } from '@/store/broadcastStore'
import styles from './BroadcastForm.module.css'

const API_BASE = import.meta.env.VITE_API_URL || '/api/admin'

interface Props {
  photoPath: string
  onPhotoChange: (path: string) => void
}

export function PhotoUploader({ photoPath, onPhotoChange }: Props) {
  const { uploadPhoto } = useBroadcastStore()
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    const path = await uploadPhoto(file)
    if (path) {
      onPhotoChange(path)
    }
    setUploading(false)
    // Reset input
    if (fileRef.current) {
      fileRef.current.value = ''
    }
  }

  const handleRemove = () => {
    onPhotoChange('')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {photoPath ? (
        <div style={{
          position: 'relative',
          display: 'inline-block',
          maxWidth: '300px',
          borderRadius: '8px',
          overflow: 'hidden',
          border: '1px solid var(--border-default)',
        }}>
          <img
            src={`${API_BASE}/broadcasts/photo/${photoPath}`}
            alt="Фото рассылки"
            style={{
              display: 'block',
              width: '100%',
              maxHeight: '200px',
              objectFit: 'cover',
            }}
          />
          <button
            onClick={handleRemove}
            style={{
              position: 'absolute',
              top: '6px',
              right: '6px',
              width: '28px',
              height: '28px',
              borderRadius: '50%',
              border: 'none',
              background: 'rgba(0,0,0,0.6)',
              color: 'white',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '14px',
            }}
            title="Удалить фото"
          >
            ✕
          </button>
        </div>
      ) : (
        <div>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            style={{ display: 'none' }}
          />
          <button
            type="button"
            className={styles.draftButton}
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              cursor: uploading ? 'wait' : 'pointer',
              opacity: uploading ? 0.6 : 1,
            }}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <rect x="1" y="2" width="12" height="10" rx="2" stroke="currentColor" strokeWidth="1.3"/>
              <circle cx="4.5" cy="5.5" r="1" stroke="currentColor" strokeWidth="1.2"/>
              <path d="M1 10L4.5 7L7 9L10 6L13 9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            {uploading ? 'Загрузка...' : 'Выбрать фото'}
          </button>
        </div>
      )}
    </div>
  )
}
