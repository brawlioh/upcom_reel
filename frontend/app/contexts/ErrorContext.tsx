'use client'

import React, { createContext, useState, useContext, ReactNode, useEffect } from 'react'
import AlertModal from '../components/AlertModal'

interface ErrorContextType {
  showError: (title: string, message: string) => void
  showWarning: (title: string, message: string) => void
  showInfo: (title: string, message: string) => void
  clearError: () => void
}

const ErrorContext = createContext<ErrorContextType>({
  showError: () => {},
  showWarning: () => {},
  showInfo: () => {},
  clearError: () => {},
})

interface ErrorProviderProps {
  children: ReactNode
}

export function ErrorProvider({ children }: ErrorProviderProps) {
  // Error state
  const [error, setError] = useState<{
    isOpen: boolean
    title: string
    message: string
    type: 'error' | 'warning' | 'info'
  }>({
    isOpen: false,
    title: '',
    message: '',
    type: 'error',
  })

  const showError = (title: string, message: string) => {
    // Filter out WebSocket and connection-related errors too
    if (
      title.toLowerCase().includes('connection') ||
      title.toLowerCase().includes('websocket') ||
      message.toLowerCase().includes('connection') ||
      message.toLowerCase().includes('websocket') ||
      message.toLowerCase().includes('disconnected') ||
      message.toLowerCase().includes('server')
    ) {
      // Just log to console instead of showing UI notification
      console.log(`[Error suppressed] ${title}: ${message}`);
      return;
    }
    
    setError({
      isOpen: true,
      title,
      message,
      type: 'error',
    })
  }

  const showWarning = (title: string, message: string) => {
    // Filter out WebSocket and connection-related warnings
    if (
      title.toLowerCase().includes('connection') ||
      title.toLowerCase().includes('websocket') ||
      message.toLowerCase().includes('connection') ||
      message.toLowerCase().includes('websocket') ||
      message.toLowerCase().includes('server') ||
      message.toLowerCase().includes('disconnect')
    ) {
      // Just log to console instead of showing UI notification
      console.log(`[Warning suppressed] ${title}: ${message}`);
      return;
    }
    
    // Show warnings for other cases
    setError({
      isOpen: true,
      title,
      message,
      type: 'warning'
    })
  }

  const showInfo = (title: string, message: string) => {
    setError({
      isOpen: true,
      title,
      message,
      type: 'info',
    })
  }

  const clearError = () => {
    setError((prev) => ({ ...prev, isOpen: false }))
  }

  return (
    <ErrorContext.Provider value={{ showError, showWarning, showInfo, clearError }}>
      {children}
      <AlertModal
        isOpen={error.isOpen}
        title={error.title}
        message={error.message}
        type={error.type}
        onClose={clearError}
      />
    </ErrorContext.Provider>
  )
}

export const useError = () => useContext(ErrorContext)
