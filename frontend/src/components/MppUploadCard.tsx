import { useRef, useState } from 'react'

type Props = {
  filename: string | null
  busy?: boolean
  onUploaded: (info: { uploadId: string; filename: string; size: number }) => void
  onCleared: () => void
  onError: (message: string) => void
  uploadFn: (file: File) => Promise<{ upload_id: string; filename: string; size: number }>
}

/** Локальный/Vite picker. На Streamlit Cloud файл берётся нативным st.file_uploader. */
export function MppUploadCard({
  filename,
  busy,
  onUploaded,
  onCleared,
  onError,
  uploadFn,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)

  const onPick = async (file: File | null) => {
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.mpp')) {
      onError('Нужен файл с расширением .mpp')
      return
    }
    setUploading(true)
    try {
      const info = await uploadFn(file)
      onUploaded({
        uploadId: info.upload_id,
        filename: info.filename || file.name,
        size: info.size,
      })
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Не удалось загрузить .mpp')
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <div className="card form-section mpp-upload-card">
      <div className="card-head-row">
        <div>
          <p className="card-title">1. Исходный .mpp</p>
          <p className="field-caption">
            Загрузите эталонный график MS Project — затем заполните объёмы и пересчитайте.
          </p>
        </div>
      </div>
      <div className="mpp-upload-row">
        <input
          ref={inputRef}
          type="file"
          accept=".mpp,application/vnd.ms-project"
          hidden
          onChange={(e) => void onPick(e.target.files?.[0] ?? null)}
        />
        <button
          type="button"
          className="btn btn-secondary"
          disabled={busy || uploading}
          onClick={() => inputRef.current?.click()}
        >
          {uploading ? 'Загрузка…' : filename ? 'Заменить .mpp' : 'Выбрать .mpp'}
        </button>
        {filename ? (
          <>
            <span className="mpp-upload-name">{filename}</span>
            <button type="button" className="btn-link" disabled={busy || uploading} onClick={onCleared}>
              Убрать
            </button>
          </>
        ) : (
          <span className="mpp-upload-hint">Сначала загрузите исходный файл</span>
        )}
      </div>
    </div>
  )
}
