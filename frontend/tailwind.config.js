/** Colors are CSS variables (src/index.css) so light/dark switch in one place. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["system-ui", "-apple-system", '"Segoe UI"', "sans-serif"] },
      colors: {
        page: "var(--page)",
        surface: "var(--surface)",
        ink: "var(--ink)",
        "ink-2": "var(--ink-2)",
        muted: "var(--muted)",
        grid: "var(--grid)",
        axis: "var(--axis)",
        edge: "var(--border)",
        ghost: "var(--ghost)",
        s1: "var(--s1)",
        s2: "var(--s2)",
        s3: "var(--s3)",
        "good-text": "var(--good-text)",
      },
    },
  },
  plugins: [],
};
