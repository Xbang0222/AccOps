import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

function getPackageName(id: string) {
  const segments = id.split('node_modules/').filter(Boolean)
  const packagePath = segments[segments.length - 1]
  if (!packagePath) {
    return ''
  }

  const parts = packagePath.split('/')
  return parts[0].startsWith('@') ? `${parts[0]}/${parts[1]}` : parts[0]
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return
          }

          const packageName = getPackageName(id)

          if (
            packageName === 'react' ||
            packageName === 'react-dom' ||
            packageName === 'react-router-dom' ||
            packageName === 'scheduler'
          ) {
            return 'react-vendor'
          }

          if (packageName === 'antd') {
            return 'antd'
          }

          if (packageName === '@ant-design/icons') {
            return 'ant-design-icons'
          }

          if (
            packageName.startsWith('@ant-design/') ||
            packageName.startsWith('@rc-component/') ||
            packageName.startsWith('rc-')
          ) {
            return 'antd-ecosystem'
          }

          if (packageName === 'axios') {
            return 'http-client'
          }

          if (packageName === 'otpauth') {
            return 'otp'
          }

          return 'vendor'
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
})
