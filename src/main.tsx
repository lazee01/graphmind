import React from 'react';
import ReactDOM from 'react-dom/client';
import { GraphMindApp } from './GraphMindApp';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <GraphMindApp />
  </React.StrictMode>,
);
