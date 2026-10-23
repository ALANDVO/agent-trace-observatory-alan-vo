import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { RedactionRulesManager } from '../components/RedactionRulesManager';
import { RedactionRule } from '../types';

// Mock the API module
vi.mock('../api', () => ({
  api: {
    getRedactionRules: vi.fn(),
    createRedactionRule: vi.fn(),
    updateRedactionRule: vi.fn(),
    deleteRedactionRule: vi.fn(),
    testRedactionPattern: vi.fn(),
  },
}));

import { api } from '../api';

const mockRules: RedactionRule[] = [
  {
    id: 1,
    rule_name: 'builtin-openai',
    pattern: '\\bsk-[A-Za-z0-9_-]{20,}\\b',
    replacement: '[REDACTED:OPENAI_KEY]',
    category: 'SECRET_KEY',
    pattern_type: 'regex',
    is_builtin: true,
    enabled: true,
    created_at: 1000,
    updated_at: 1000,
  },
  {
    id: 2,
    rule_name: 'internal-api-key',
    pattern: '\\bINT_API_[A-Z0-9]{24}\\b',
    replacement: '[REDACTED:INTERNAL_API_KEY]',
    category: 'SECRET_KEY',
    pattern_type: 'regex',
    is_builtin: false,
    enabled: true,
    created_at: 2000,
    updated_at: 2000,
  },
  {
    id: 3,
    rule_name: 'disabled-rule',
    pattern: '\\bDISABLED_[A-Z0-9]{10}\\b',
    replacement: '[REDACTED:DISABLED]',
    category: 'CUSTOM',
    pattern_type: 'regex',
    is_builtin: false,
    enabled: false,
    created_at: 3000,
    updated_at: 3000,
  },
];

describe('RedactionRulesManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getRedactionRules).mockResolvedValue(mockRules);
    vi.mocked(api.createRedactionRule).mockImplementation(async (r) => ({ ...r, id: 4, is_builtin: false, created_at: Date.now(), updated_at: Date.now() }));
    vi.mocked(api.updateRedactionRule).mockImplementation(async (id, r) => ({ ...mockRules.find(x => x.id === id)!, ...r, updated_at: Date.now() }));
    vi.mocked(api.deleteRedactionRule).mockResolvedValue(undefined);
    vi.mocked(api.testRedactionPattern).mockResolvedValue({
      matches: [{ match: 'INT_API_ABC123', start: 0, end: 14 }],
      sanitized_text: '[REDACTED:INTERNAL_API_KEY]',
      pattern_valid: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders rules table with built-in and custom rules', async () => {
    render(<RedactionRulesManager isOpen={true} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('Redaction Rules')).toBeInTheDocument();
    });

    // Check built-in rule is shown
    expect(screen.getByText('builtin-openai')).toBeInTheDocument();
    expect(screen.getByText('[REDACTED:OPENAI_KEY]')).toBeInTheDocument();
    expect(screen.getAllByText('regex')).toHaveLength(3);
    expect(screen.getAllByText('SECRET_KEY')).toHaveLength(2);

    // Check custom rules
    expect(screen.getByText('internal-api-key')).toBeInTheDocument();
    expect(screen.getByText('disabled-rule')).toBeInTheDocument();
    expect(screen.getByText('CUSTOM')).toBeInTheDocument();
  });

  it('shows On/Off status correctly', async () => {
    render(<RedactionRulesManager isOpen={true} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getAllByText('On')).toHaveLength(2);
    });

    // Two enabled (On), one disabled (Off)
    const onBadges = screen.getAllByText('On');
    const offBadges = screen.getAllByText('Off');
    expect(onBadges.length).toBe(2);
    expect(offBadges.length).toBe(1);
  });

  it('shows Yes/No for built-in status correctly', async () => {
    render(<RedactionRulesManager isOpen={true} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getAllByText('Yes')).toHaveLength(1);
    });

    // One built-in (Yes), two custom (No)
    const yesBadges = screen.getAllByText('Yes');
    const noBadges = screen.getAllByText('No');
    expect(yesBadges.length).toBe(1);
    expect(noBadges.length).toBe(2);
  });

  it('deletes a custom rule on confirm', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(<RedactionRulesManager isOpen={true} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('internal-api-key')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByText('Del');
    fireEvent.click(deleteButtons[0]); // First delete for custom rule

    await waitFor(() => {
      expect(api.deleteRedactionRule).toHaveBeenCalledWith(2);
    });
  });

  it('closes when clicking the close button', async () => {
    const onClose = vi.fn();
    render(<RedactionRulesManager isOpen={true} onClose={onClose} />);

    await waitFor(() => {
      expect(screen.getByText('Redaction Rules')).toBeInTheDocument();
    });

    const closeButton = screen.getByText('✕');
    fireEvent.click(closeButton);

    expect(onClose).toHaveBeenCalled();
  });

  it('opens edit form when clicking Edit', async () => {
    render(<RedactionRulesManager isOpen={true} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('internal-api-key')).toBeInTheDocument();
    });

    const editButtons = screen.getAllByText('Edit');
    fireEvent.click(editButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Edit Rule')).toBeInTheDocument();
    });
  });

  it('cancels edit form when clicking Cancel', async () => {
    render(<RedactionRulesManager isOpen={true} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('internal-api-key')).toBeInTheDocument();
    });

    const editButtons = screen.getAllByText('Edit');
    fireEvent.click(editButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Edit Rule')).toBeInTheDocument();
    });

    const cancelButton = screen.getByText('Cancel');
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(screen.queryByText('Edit Rule')).not.toBeInTheDocument();
    });
  });

  it('renders loading state', async () => {
    vi.mocked(api.getRedactionRules).mockImplementation(async () => {
      await new Promise(resolve => setTimeout(resolve, 100));
      return mockRules;
    });

    render(<RedactionRulesManager isOpen={true} onClose={() => {}} />);

    expect(screen.getByText('Loading...')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
    });
  });

  it('renders error state on API failure', async () => {
    vi.mocked(api.getRedactionRules).mockRejectedValue(new Error('Network error'));

    render(<RedactionRulesManager isOpen={true} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });
});