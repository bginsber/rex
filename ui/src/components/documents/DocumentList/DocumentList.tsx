import type { SearchResult } from '@/types'
import { DocumentCard } from '../DocumentCard'
import styles from './DocumentList.module.css'

export interface DocumentListProps {
  documents: SearchResult[]
  selectedDocumentHash?: string
  onSelectDocument?: (document: SearchResult) => void
  emptyMessage?: string
}

export function DocumentList({
  documents,
  selectedDocumentHash,
  onSelectDocument,
  emptyMessage = 'No documents found'
}: DocumentListProps) {
  if (documents.length === 0) {
    return (
      <div className={styles.empty}>
        <p>{emptyMessage}</p>
      </div>
    )
  }

  return (
    <div className={styles.list}>
      {documents.map((doc, index) => (
        <DocumentCard
          key={doc.sha256}
          document={doc}
          isActive={doc.sha256 === selectedDocumentHash}
          onClick={() => onSelectDocument?.(doc)}
          index={index}
        />
      ))}
    </div>
  )
}
