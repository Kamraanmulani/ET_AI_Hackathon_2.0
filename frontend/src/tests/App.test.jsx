import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../App';
import ErrorBoundary from '../ErrorBoundary';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';

// Setup Mock for window.fetch
beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url) => {
    if (url.includes('/api/v1/documents')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ documents: [], total: 0 }),
      });
    }
    if (url.includes('/api/v1/assets')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ assets: [], total: 0 }),
      });
    }
    if (url.includes('/api/v1/drawings')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve([]),
      });
    }
    if (url.includes('/api/v1/review/tasks')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ tasks: [], total: 0 }),
      });
    }
    return Promise.reject(new Error('not mocked'));
  }));
});

describe('Frontend Hardening Regression Tests', () => {
  it('renders the App layout without throwing nested router errors', () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    // Render the App component wrapped inside QueryClient and BrowserRouter (like main.jsx does)
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Verify it renders Topbar and Rail navigation successfully
    expect(screen.getByText('Pragyan Plant Intelligence')).toBeInTheDocument();
    expect(screen.getByText('P&ID Explorer')).toBeInTheDocument();
  });

  it('renders ErrorBoundary fallback when a child component throws an error', () => {
    const ThrowingComponent = () => {
      throw new Error('Test rendering crash');
    };

    // Suppress console.error in tests for throwing component
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText(/Test rendering crash/)).toBeInTheDocument();
    // Force fetch to reject/fail
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('API Down')));

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Wait and ensure the app loads skeleton or generic state rather than crashing completely
    expect(screen.getByText('Pragyan Plant Intelligence')).toBeInTheDocument();
  });
});
