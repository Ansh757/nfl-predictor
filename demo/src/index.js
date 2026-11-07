import React from 'react';
import ReactDOM from 'react-dom/client';
/*
 * Fonts are bundled, not linked from Google Fonts. The service's
 * Content-Security-Policy allows fonts and stylesheets from its own origin
 * only (font-src 'self'), so a fonts.googleapis.com <link> is blocked in
 * production and every heading falls back to Arial Narrow. Latin subset, and
 * only the weights the design uses.
 */
import '@fontsource/barlow/latin-400.css';
import '@fontsource/barlow/latin-500.css';
import '@fontsource/barlow/latin-600.css';
import '@fontsource/barlow-condensed/latin-500.css';
import '@fontsource/barlow-condensed/latin-600.css';
import '@fontsource/barlow-condensed/latin-700.css';
import '@fontsource/barlow-condensed/latin-800.css';
import './tailwind.generated.css';
import './index.css';
import App from './App';
import ErrorBoundary from './components/ErrorBoundary';
import reportWebVitals from './reportWebVitals';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  // <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  // </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
