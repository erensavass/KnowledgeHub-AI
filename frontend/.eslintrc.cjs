module.exports = {
  root: true,
  env: { browser: true, es2022: true },
  extends: ['eslint:recommended', 'plugin:@typescript-eslint/recommended'],
  ignorePatterns: ['dist', 'coverage'],
  parser: '@typescript-eslint/parser',
  plugins: ['react-hooks', 'react-refresh'],
  rules: {
    ...require('eslint-plugin-react-hooks').configs.recommended.rules,
    'react-refresh/only-export-components': 'off',
    '@typescript-eslint/no-explicit-any': 'off'
  }
}
