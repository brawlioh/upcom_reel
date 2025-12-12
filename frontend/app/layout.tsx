import './globals.css'
import { Inter } from 'next/font/google'
import { ErrorProvider } from './contexts/ErrorContext'
import ConnectionBanner from './components/ConnectionBanner'

const inter = Inter({ subsets: ['latin'] })

export const metadata = {
  title: 'YouTube Reels Automation',
  description: 'Automated gaming content creation for YouTube Shorts',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <ErrorProvider>
          {/* ConnectionBanner intercepts and removes any connection lost notifications */}
          <ConnectionBanner />
          <div className="min-h-screen bg-dark-900">
            {children}
          </div>
        </ErrorProvider>
      </body>
    </html>
  )
}
