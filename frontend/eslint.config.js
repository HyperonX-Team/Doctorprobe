// Flat ESLint config (ESLint 9) for the Doctordrobe SPA.
// TypeScript strict + React hooks rules + Prettier formatting.
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import prettier from "eslint-plugin-prettier";
import configPrettier from "eslint-config-prettier";

// Minimal set of browser/test globals (the `globals` package is not used
// to keep the dependency tree lean).
const GLOBALS = {
  window: "readonly",
  document: "readonly",
  localStorage: "readonly",
  navigator: "readonly",
  fetch: "readonly",
  console: "readonly",
  setTimeout: "readonly",
  clearTimeout: "readonly",
  setInterval: "readonly",
  clearInterval: "readonly",
  URL: "readonly",
  Blob: "readonly",
  FileReader: "readonly",
  structuredClone: "readonly",
  // Vitest globals (tests/setup.ts runs first).
  describe: "readonly",
  it: "readonly",
  test: "readonly",
  expect: "readonly",
  vi: "readonly",
  beforeEach: "readonly",
  afterEach: "readonly",
  beforeAll: "readonly",
  afterAll: "readonly",
};

export default tseslint.config(
  { ignores: ["dist/**", "node_modules/**", "coverage/**"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommended,
      configPrettier,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: GLOBALS,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
      prettier,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
      "prettier/prettier": "warn",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_" },
      ],
    },
  },
  // Context modules idiomatically export both the provider component and
  // a consumer hook; fast refresh still works for the component.
  {
    files: ["src/context/*.tsx", "src/components/ui/Toast.tsx"],
    rules: {
      "react-refresh/only-export-components": [
        "warn",
        {
          allowConstantExport: true,
          allowExportNames: ["useUserContext", "useToast"],
        },
      ],
    },
  },
);
