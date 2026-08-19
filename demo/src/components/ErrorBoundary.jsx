import React from 'react';

/**
 * Catches render errors so a single broken component cannot blank the page.
 *
 * Without this, any exception during render unmounts the whole tree and the
 * user gets a white screen with nothing in it - no message, no indication that
 * anything failed. That is exactly what a production incident looked like, and
 * it took a jsdom probe to find out why.
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Keep the stack in the console for anyone with devtools open
    console.error('Dashboard render error:', error, info?.componentStack);
  }

  handleReload = () => {
    this.setState({ error: null });
    window.location.reload();
  };

  render() {
    const { error } = this.state;
    if (!error) {
      return this.props.children;
    }

    return (
      <div className="min-h-screen bg-slate-950 px-6 py-16 text-slate-100">
        <div className="mx-auto max-w-2xl rounded-2xl border border-red-500/40 bg-slate-900 p-8">
          <h1 className="text-xl font-semibold">Something broke while rendering</h1>
          <p className="mt-2 text-sm text-slate-400">
            The dashboard hit an unexpected error. The details below are what the
            page would otherwise have swallowed.
          </p>

          <pre className="mt-4 overflow-x-auto rounded-xl bg-slate-950 p-4 text-xs text-red-300">
            {String(error?.message || error)}
          </pre>

          <button
            type="button"
            onClick={this.handleReload}
            className="mt-6 rounded-xl border border-slate-700 px-4 py-2 text-sm font-semibold transition hover:bg-slate-800"
          >
            Reload the page
          </button>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
