import { useState, useEffect, useCallback } from 'react';

const DEFAULT_API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export interface Document {
  id: string;
  name: string;
  pageCount: number;
  chunkCount?: number;
  date: string;
  demo?: boolean;
}

export interface Evidence {
  id: string;
  docName: string;
  page: number | string;
  section: string;
  text: string;
  relevance: number;
}

export interface GraphPath {
  id: string;
  source: string;
  relation: string;
  target: string;
  color: string;
}

export interface AnswerResponse {
  answer: string;
  confidence: number;
  evidence: Evidence[];
  paths: GraphPath[];
  agents: { name: string; completed: boolean }[];
}

const DEMO_DOCS: Document[] = [
  { id: 'demo-001', name: 'RAG-Lewis2020.txt', pageCount: 1, chunkCount: 4, date: new Date().toISOString(), demo: true },
  { id: 'demo-002', name: 'RAPTOR-Sarthi2024.txt', pageCount: 1, chunkCount: 4, date: new Date().toISOString(), demo: true },
  { id: 'demo-003', name: 'HippoRAG-Gutierrez2025.txt', pageCount: 1, chunkCount: 4, date: new Date().toISOString(), demo: true },
  { id: 'demo-004', name: 'BioASQ-Nentidis2025.txt', pageCount: 1, chunkCount: 4, date: new Date().toISOString(), demo: true },
  { id: 'demo-005', name: 'AgenticRAG-Suresh2026.txt', pageCount: 1, chunkCount: 4, date: new Date().toISOString(), demo: true },
];

const DEMO_ANSWER: AnswerResponse = {
  answer:
    'Retrieval-Augmented Generation (RAG) combines the parametric memory of large language models with non-parametric retrieval from an external knowledge corpus [1]. RAPTOR extends this by building a hierarchical tree index through recursive clustering and abstractive summarization, improving multi-hop accuracy by 20% [2]. HippoRAG further enriches retrieval using knowledge graph traversal with Personalized PageRank for multi-hop reasoning across scientific documents [3].',
  confidence: 0.92,
  evidence: [
    {
      id: 'demo-chunk-1',
      docName: 'RAG-Lewis2020.txt',
      page: 1,
      section: 'Introduction',
      text: 'Retrieval-Augmented Generation (RAG) combines parametric memory of large language models with non-parametric memory through dense passage retrieval.',
      relevance: 0.94,
    },
    {
      id: 'demo-chunk-2',
      docName: 'RAPTOR-Sarthi2024.txt',
      page: 1,
      section: 'Introduction',
      text: 'RAPTOR introduces recursive abstractive processing for tree-organized retrieval, improving performance by 20% on multi-hop questions.',
      relevance: 0.86,
    },
    {
      id: 'demo-chunk-3',
      docName: 'HippoRAG-Gutierrez2025.txt',
      page: 1,
      section: 'Methods',
      text: 'HippoRAG uses Personalized PageRank on an OpenIE knowledge graph for multi-hop retrieval across scientific documents.',
      relevance: 0.79,
    },
  ],
  paths: [
    { id: 'p1', source: 'RAG', relation: 'USES', target: 'Dense Retrieval', color: '#06b6d4' },
    { id: 'p2', source: 'RAPTOR', relation: 'IMPROVES', target: 'RAG', color: '#22c55e' },
    { id: 'p3', source: 'HippoRAG', relation: 'TRAVERSES', target: 'Knowledge Graph', color: '#a855f7' },
  ],
  agents: [
    { name: 'Planner', completed: true },
    { name: 'Retriever', completed: true },
    { name: 'Graph Reasoner', completed: true },
    { name: 'Verifier', completed: true },
    { name: 'Generator', completed: true },
  ],
};

function parseGraphPaths(rawPaths: string[]): GraphPath[] {
  const colors = ['#06b6d4', '#22c55e', '#a855f7', '#eab308', '#f97316'];
  return (rawPaths || []).map((p, idx) => {
    const m = p.match(/^(.+?)\s*--\[(.+?)\]-->\s*(.+)$/);
    if (m) {
      return {
        id: `path-${idx}`,
        source: m[1].trim(),
        relation: m[2].trim(),
        target: m[3].trim(),
        color: colors[idx % colors.length],
      };
    }
    return {
      id: `path-${idx}`,
      source: 'Concept',
      relation: 'RELATED_TO',
      target: p,
      color: colors[idx % colors.length],
    };
  });
}

export function useGraphMind(apiUrl: string = DEFAULT_API_URL) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [health, setHealth] = useState<'checking' | 'online' | 'offline'>('checking');
  const [demoMode, setDemoMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch(`${apiUrl}/api/health`, { signal: AbortSignal.timeout(4000) });
      if (!res.ok) throw new Error('API unhealthy');
      setHealth('online');
      setDemoMode(false);
    } catch {
      setHealth('offline');
      setDemoMode(true);
    }
  }, [apiUrl]);

  const fetchDocuments = useCallback(async () => {
    if (demoMode) {
      setDocuments(DEMO_DOCS);
      return;
    }
    try {
      const res = await fetch(`${apiUrl}/api/documents`);
      if (!res.ok) throw new Error('Failed to fetch documents');
      const raw: any[] = await res.json();
      setDocuments(
        raw.map(d => ({
          id: d.id,
          name: d.name,
          pageCount: d.page_count ?? d.pageCount ?? 1,
          chunkCount: d.chunk_count ?? d.chunkCount ?? 1,
          date: d.date || new Date().toISOString(),
          demo: d.demo,
        }))
      );
    } catch {
      setDocuments(DEMO_DOCS);
    }
  }, [apiUrl, demoMode]);

  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const uploadDocument = useCallback(
    async (file: File): Promise<boolean> => {
      if (demoMode) {
        const fakeDoc: Document = {
          id: `demo-upload-${Date.now()}`,
          name: file.name,
          pageCount: 1,
          chunkCount: 5,
          date: new Date().toISOString(),
          demo: true,
        };
        setDocuments(prev => [...prev, fakeDoc]);
        return true;
      }
      setLoading(true);
      setError(null);
      try {
        const form = new FormData();
        form.append('file', file);
        const res = await fetch(`${apiUrl}/api/documents`, { method: 'POST', body: form });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Upload failed');
        }
        const d = await res.json();
        const newDoc: Document = {
          id: d.id,
          name: d.name,
          pageCount: d.page_count ?? 1,
          chunkCount: d.chunk_count ?? 1,
          date: new Date().toISOString(),
          demo: d.demo,
        };
        setDocuments(prev => [...prev, newDoc]);
        return true;
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Upload failed');
        return false;
      } finally {
        setLoading(false);
      }
    },
    [apiUrl, demoMode]
  );

  const ask = useCallback(
    async (question: string, limit = 6, documentId?: string): Promise<AnswerResponse> => {
      if (demoMode) {
        await new Promise(r => setTimeout(r, 600));
        return DEMO_ANSWER;
      }
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${apiUrl}/api/ask`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question, limit, document_id: documentId }),
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Query failed');
        }
        const raw = await res.json();
        const evidence: Evidence[] = (raw.evidence || []).map((ev: any, i: number) => ({
          id: ev.chunk_id || `ev-${i}`,
          docName: ev.document_name || 'Document',
          page: ev.page ?? 1,
          section: ev.section || 'General',
          text: ev.text || '',
          relevance: Math.min(1, Math.max(0.15, (ev.score || 0.25) * 3.2)),
        }));
        const paths = parseGraphPaths(raw.graph_paths || []);
        return {
          answer: raw.answer || 'No answer generated.',
          confidence: raw.confidence ?? 0.85,
          evidence,
          paths,
          agents: [
            { name: 'Planner', completed: true },
            { name: 'Retriever', completed: true },
            { name: 'Graph Reasoner', completed: true },
            { name: 'Verifier', completed: true },
            { name: 'Generator', completed: true },
          ],
        };
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Query failed');
        return DEMO_ANSWER;
      } finally {
        setLoading(false);
      }
    },
    [apiUrl, demoMode]
  );

  return {
    documents,
    health,
    demoMode,
    loading,
    error,
    uploadDocument,
    ask,
  };
}
