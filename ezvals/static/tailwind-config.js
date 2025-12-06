tailwind.config = {
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      colors: {
        theme: {
          bg: 'var(--bg)',
          'bg-secondary': 'var(--bg-secondary)',
          'bg-elevated': 'var(--bg-elevated)',
          text: 'var(--text)',
          'text-secondary': 'var(--text-secondary)',
          'text-muted': 'var(--text-muted)',
          border: 'var(--border)',
          'border-subtle': 'var(--border-subtle)',
          'btn-bg': 'var(--btn-bg)',
          'btn-bg-hover': 'var(--btn-bg-hover)',
          'btn-border': 'var(--btn-border)',
        },
        accent: {
          link: 'var(--accent-link)',
          'link-hover': 'var(--accent-link-hover)',
          success: 'var(--accent-success)',
          'success-bg': 'var(--accent-success-bg)',
          error: 'var(--accent-error)',
          'error-bg': 'var(--accent-error-bg)',
        },
      },
    },
  },
};
