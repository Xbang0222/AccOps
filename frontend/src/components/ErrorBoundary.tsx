import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  readonly hasError: boolean;
  readonly errorMessage: string;
}

const INITIAL_STATE: ErrorBoundaryState = {
  hasError: false,
  errorMessage: '',
};

// fallback 不依赖 antd: ErrorBoundary 处于 ConfigProvider/AntApp 之外,
// 而且当 ThemeProvider/ConfigProvider 自身抛错时, antd 组件可能根本渲染不出来。
class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = INITIAL_STATE;
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      errorMessage: error.message || '未知错误',
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('[ErrorBoundary] Uncaught render error:', error, errorInfo);
  }

  private handleReload = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '100vh',
            padding: 24,
            fontFamily:
              '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
            color: '#1f1f1f',
            background: '#ffffff',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: 48, lineHeight: 1, marginBottom: 16 }}>⚠️</div>
          <h1 style={{ fontSize: 22, fontWeight: 600, margin: '0 0 8px' }}>
            页面渲染出错
          </h1>
          <p
            style={{
              fontSize: 14,
              color: '#595959',
              margin: '0 0 24px',
              maxWidth: 480,
              wordBreak: 'break-word',
            }}
          >
            {this.state.errorMessage}
          </p>
          <button
            type="button"
            onClick={this.handleReload}
            style={{
              padding: '8px 20px',
              fontSize: 14,
              fontWeight: 500,
              color: '#ffffff',
              background: '#1677ff',
              border: 'none',
              borderRadius: 6,
              cursor: 'pointer',
            }}
          >
            重新加载
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
