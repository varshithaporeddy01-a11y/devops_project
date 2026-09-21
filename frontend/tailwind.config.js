/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0d1016",
          900: "#12141c",
          800: "#191c26",
          700: "#242836",
          600: "#333849",
          500: "#4a5068",
        },
        paper: "#eef0f5",
        signal: "#e8a33d",
        node: {
          module: "#4a5068",
          function: "#8b7cf6",
          loop: "#e8a33d",
          condition: "#f0648c",
          variable: "#3fc5b7",
          call: "#5b9ee8",
          return: "#5fd68f",
          import: "#9aa2b8",
          class: "#e0857a",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
