import { defineConfig, globalIgnores } from 'eslint/config';
import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import react from 'eslint-plugin-react';
import hooks from 'eslint-plugin-react-hooks';
import a11y from 'eslint-plugin-jsx-a11y';

export default defineConfig([
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    ...react.configs.flat.recommended,
    settings: { react: { version: 'detect' } },
    rules: { ...react.configs.flat.recommended.rules,
      'react/react-in-jsx-scope': 'off', 'react/prop-types': 'off' },
  },
  { files: ['**/*.{ts,tsx}'], ...hooks.configs.flat.recommended },
  { files: ['**/*.{ts,tsx}'], ...a11y.flatConfigs.recommended },
  { languageOptions: { globals: { console: 'readonly', process: 'readonly', Buffer: 'readonly',
    crypto: 'readonly', URL: 'readonly', Uint8Array: 'readonly', window: 'readonly',
    React: 'readonly' } } },
  globalIgnores(['.next/**', 'out/**', 'build/**', 'next-env.d.ts']),
]);
