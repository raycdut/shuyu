/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 宋氏美学色板
        ink: {
          DEFAULT: '#2c2c2c',
          light: '#666660',
          lighter: '#999994',
        },
        paper: {
          DEFAULT: '#f5f0e8',
          dark: '#ece6db',
          light: '#faf7f2',
        },
        celadon: {
          DEFAULT: '#7ba893',
          light: '#a8c9b8',
          dark: '#5c8a76',
        },
        cinnabar: {
          DEFAULT: '#c23a2b',
          light: '#d96b5e',
        },
        tea: {
          DEFAULT: '#d4c9b8',
          light: '#e5ddd2',
        },
        smoke: {
          DEFAULT: '#e8e3d8',
          dark: '#ddd8cc',
        },
      },
      fontFamily: {
        song: ['"Noto Serif SC"', '"Source Han Serif SC"', '"SimSun"', '"PingFang SC"', 'sans-serif'],
        kai: ['"KaiTi"', '"STKaiti"', '"ZCOOL XiaoWei"', '"Noto Serif SC"', '"PingFang SC"', 'sans-serif'],
        sans: ['-apple-system', 'BlinkMacSystemFont', '"PingFang SC"', '"Hiragino Sans GB"', '"Microsoft YaHei"', '"Noto Sans SC"', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
