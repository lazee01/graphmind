import { useState, useEffect, useCallback } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Document {
  id: string;
  name: string;
  page_count: number;
  chunk_count: number;
  demo?: boolean;
}

export interface EvidenceChunk {
  chunk_id: string;
  document_id: string;
  document_name: string;
  text: string;
  page: number | null;
  section: string;
  score: number;
  citation: string;
}

export interface Citation {
  ref: number;
  citation: string;
  document_id: string;
  document_name: string;
  page: number | null;
  section: string;
  chunk_id: string;
}

export interface AgentStep {
  agent: string;
  mode?: string;
  output?: string[];
  chunks_found?: number;
  paths_found?: number;
  answer_length?: number;
  result?: { verified: boolean; confidence: number; warnings: string[] };
}

export interface AskResult {
  answer: string;
  subqueries: string[];
  evidence: EvidenceChunk[];
  citations: Citation[];
  graph_paths: string[];
  confidence: number;
  verified: boolean;
  warnings: string[];
  agent_trace: AgentStep[];
}

export interface HealthStatus {
  status: string;
  documents: number;
  chunks: number;
  neo4j: boolean;
  provider: { provider: string; active: boolean; fallback: string };
  agents: { name: string; mode: string }[];
}

// ── Demo corpus fallback ──────────────────────────────────────────────────────

const DEMO_DOCS: Document[] = [
  { id: 'demo-001', name: 'RAG-Lewis2020.txt', page_count: 1, chunk_count: 4, demo: true },
  { id: 'demo-002', name: 'RAPTOR-Sarthi2024.txt', page_count: 1, chunk_count: 4, demo: true },
  { id: 'demo-003', name: 'HippoRAG-Gutierrez2025.txt', page_count: 1, chunk_count: 4, demo: true },
  { id: 'demo-004', name: 'BioASQ-Nentidis2025.txt', page_count: 1, chunk_count: 4, demo: true },
  { id: 'demo-005', name: 'AgenticRAG-Suresh2026.txt', page_count: 1, chunk_count: 4, demo: true },
];

const DEMO_ANSWER: AskResult = {
  answer:
    'Retrieval-Augmented Generation (RAG) combines the parametric memory of large language models with non-parametric retrieval from an external knowledge corpus [1]. RAG uses a dense passage retriever (DPR) to fetch relevant documents, then conditions a seq2seq generator on the retrieved context [1]. RAPTOR extends this by building a hierarchical tree index through recursive clustering and abstractive summarization, enabling both fine-grained and global-context retrieval [2]. HippoRAG further enriches retrieval using knowledge graph traversal with Personalized PageRank for multi-hop reasoning [3].',
  subqueries: ['What is RAG?', 'How does retrieval work?', 'What are RAG improvements?'],
  evidence: [
    {
      chunk_id: 'demo-chunk-1',
      document_id: 'demo-001',
      document_name: 'RAG-Lewis2020.txt',
      text: 'Retrieval-Augmented Generation (RAG) combines parametric memory of large language models with non-parametric memory through dense passage retrieval.',
      page: 1,
      section: 'Abstract',
      score: 0.92,
      citation: 'RAG-Lewis2020.txt (p. 1)',
    },
    {
      chunk_id: 'demo-chunk-2',
      document_id: 'demo-002',
      document_name: 'RAPTOR-Sarthi2024.txt',
      text: 'RAPTOR introduces recursive abstractive processing for tree-organized retrieval, improving performance by 20% on multi-hop questions.',
      page: 1,
      section: 'Introduction',
      score: 0.81,
      citation: 'RAPTOR-Sarthi2024.txt (p. 1)',
    },
    {
      chunk_id: 'demo-chunk-3',
      document_id: 'demo-003',
      document_name: 'HippoRAG-Gutierrez2025.txt',
      text: 'HippoRAG uses Personalized PageRank on an OpenIE knowledge graph for multi-hop retrieval across scientific documents.',
      page: 1,
      section: 'Methods',
      score: 0.74,
      citation: 'HippoRAG-Gutierrez2025.txt (p. 1)',
    },
  ],
  citations: [
    { ref: 1, citation: 'RAG-Lewis2020.txt (p. 1)', document_id: 'demo-001', document_name: 'RAG-Lewis2020.txt', page: 1, section: 'Abstract', chunk_id: 'demo-chunk-1' },
    { ref: 2, citation: 'RAPTOR-Sarthi2024.txt (p. 1)', document_id: 'demo-002', document_name: 'RAPTOR-Sarthi2024.txt', page: 1, section: 'Introduction', chunk_id: 'demo-chunk-2' },
    { ref: 3, citation: 'HippoRAG-Gutierrez2025.txt (p. 1)', document_id: 'demo-003', document_name: 'HippoRAG-Gutierrez2025.txt', page: 1, section: 'Methods', chunk_id: 'demo-chunk-3' },
  ],
  graph_paths: [
    'RAG --[USES]--> Dense Retrieval',
    'RAPTOR --[IMPROVES]--> RAG',
    'HippoRAG --[USES]--> Knowledge Graph',
    'GraphMind --[EXTENDS]--> HippoRAG',
  ],
  confidence: 0.87,
  verified: true,
  warnings: [],
  agent_trace: [
    { agent: 'planner', output: ['What is RAG?', 'How does retrieval work?'] },
    { agent: 'retriever', chunks_found: 3 },
    { agent: 'graph_reasoner', paths_found: 4 },
    { agent: 'generator', answer_length: 420 },
    { agent: 'verifier', result: { verified: true, confidence: 0.87, warnings: [] } },
  ],
};

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useGraphMind() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [demoMode, setDemoMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/health`, { signal: AbortSignal.timeout(4000) });
      if (!res.ok) throw new Error('API unhealthy');
      const data: HealthStatus = await res.json();
      setHealth(data);
      setDemoMode(false);
    } catch {
      setDemoMode(true);
      setHealth(null);
    }
  }, []);

  const fetchDocuments = useCallback(async () => {
    if (demoMode) {
      setDocuments(DEMO_DOCS);
      return;
    }
    try {
      const res = await fetch(`${API_URL}/api/documents`);
      if (!res.ok) throw new Error('Failed to fetch documents');
      setDocuments(await res.json());
    } catch {
      setDocuments(DEMO_DOCS);
    }
  }, [demoMode]);

  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments, demoMode]);

  const uploadDocument = useCallback(async (file: File): Promise<Document | null> => {
    if (demoMode) {
      const fakeDoc: Document = {
        id: `demo-upload-${Date.now()}`,
        name: file.name,
        page_count: 1,
        chunk_count: 5,
        demo: true,
      };
      setDocuments(prev => [...prev, fakeDoc]);
      return fakeDoc;
    }
    setLoading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${API_URL}/api/documents`, { method: 'POST', body: form });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Upload failed');
      }
      const doc: Document = await res.json();
      setDocuments(prev => [...prev, doc]);
      return doc;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed');
      return null;
    } finally {
      setLoading(false);
    }
  }, [demoMode]);

  const deleteDocument = useCallback(async (docId: string) => {
    if (demoMode) {
      setDocuments(prev => prev.filter(d => d.id !== docId));
      return;
    }
    try {
      await fetch(`${API_URL}/api/documents/${docId}`, { method: 'DELETE' });
      setDocuments(prev => prev.filter(d => d.id !== docId));
    } catch (e) {
      setError('Failed to delete document');
    }
  }, [demoMode]);

  const ask = useCallback(async (
    question: string,
    limit = 6,
    documentId?: string,
  ): Promise<AskResult> => {
    if (demoMode) {
      await new Promise(r => setTimeout(r, 800)); // simulate latency
      return { ...DEMO_ANSWER };
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, limit, document_id: documentId }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Query failed');
      }
      return await res.json();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Query failed');
      return DEMO_ANSWER;
    } finally {
      setLoading(false);
    }
  }, [demoMode]);

  return {
    documents,
    health,
    demoMode,
    loading,
    error,
    uploadDocument,
    deleteDocument,
    ask,
    refresh: checkHealth,
  };
}
