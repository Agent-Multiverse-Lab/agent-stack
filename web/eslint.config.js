import js from "@eslint/js"
import { globalIgnores } from "eslint/config"
import globals from "globals"
import tseslint from "typescript-eslint"
import reactHooks from "eslint-plugin-react-hooks"

export default [
  globalIgnores(["**/dist/**", "**/coverage/**"]),
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{js,mjs,cjs,ts,mts,tsx}"],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node
      },
      parserOptions: {
        sourceType: "module"
      }
    },
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/ban-ts-comment": "off",
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn"
    }
  },
  {
    files: ["src/**/*.{jsx,tsx}"],
    ignores: ["src/components/ui/**/*.{jsx,tsx}"],
    rules: {
      "no-restricted-syntax": [
        "error",
        ...[
          "button",
          "input",
          "textarea",
          "select",
          "option",
          "dialog",
          "details",
          "summary",
          "label",
          "table",
          "thead",
          "tbody",
          "tr",
          "th",
          "td"
        ].map((name) => ({
          selector: `JSXOpeningElement[name.name='${name}']`,
          message: `Use the shadcn/ui ${name} primitive instead of a native <${name}> element.`
        }))
      ]
    }
  },
  { plugins: { "react-hooks": reactHooks } }
]
