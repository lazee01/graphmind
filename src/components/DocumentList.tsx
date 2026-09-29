import React from 'react';
import { Document } from '../hooks/useGraphMind';

interface DocumentListProps {
  documents: Document[];
}

export const DocumentList: React.FC<DocumentListProps> = ({ documents }) => {
  if (documents.length === 0) {
    return (
      <div className="document-list empty">
        <p>No documents uploaded yet.</p>
      </div>
    );
  }

  return (
    <div className="document-list">
      {documents.map((doc) => (
        <div key={doc.id} className="document-item">
          <svg className="doc-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
            <line x1="16" y1="13" x2="8" y2="13"></line>
            <line x1="16" y1="17" x2="8" y2="17"></line>
            <polyline points="10 9 9 9 8 9"></polyline>
          </svg>
          <div className="doc-info">
            <div className="doc-name" title={doc.name}>{doc.name}</div>
            <div className="doc-meta">
              {doc.pageCount} pages • {new Date(doc.date).toLocaleDateString()}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};
