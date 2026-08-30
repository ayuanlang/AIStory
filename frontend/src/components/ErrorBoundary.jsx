import React from 'react';
import { isStaleChunkError, reloadOnceForStaleChunk } from '../lib/lazyWithChunkReload';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
    this.resetErrorBoundary = this.resetErrorBoundary.bind(this);
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    try {
      if (isStaleChunkError(error) && reloadOnceForStaleChunk()) {
        return;
      }
      if (typeof this.props.onError === 'function') {
        this.props.onError(error, errorInfo);
      } else {
        console.error('ErrorBoundary caught an error:', error, errorInfo);
      }
    } catch {
      // ignore secondary reporting failures
    }
  }

  resetErrorBoundary() {
    this.setState({ hasError: false });
  }

  render() {
    if (this.state.hasError) {
      if (typeof this.props.fallbackRender === 'function') {
        return this.props.fallbackRender({
          resetErrorBoundary: this.resetErrorBoundary,
        });
      }
      if (this.props.fallback !== undefined) {
        return this.props.fallback;
      }
      return null;
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
