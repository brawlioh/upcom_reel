'use client'

import { X, AlertCircle, CheckCircle } from 'lucide-react'
import { useEffect, useState, useRef } from 'react'

interface AlertModalProps {
  isOpen: boolean
  title: string
  message: string
  type: 'error' | 'warning' | 'info'
  onClose: () => void
}

export default function AlertModal({ isOpen, title, message, type, onClose }: AlertModalProps) {
  const [visible, setVisible] = useState(false)
  const timerRef = useRef<NodeJS.Timeout | null>(null)
  
  useEffect(() => {
    setVisible(isOpen)
    
    // Clear any existing timers
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [isOpen])
  
  // Auto-dismiss all notifications after a delay
  useEffect(() => {
    if (visible) {
      // Auto-dismiss based on type - even shorter times to be less intrusive
      const dismissTime = 
        type === 'error' ? 5000 :    // 5 seconds for errors (reduced from 6)
        type === 'warning' ? 2500 :  // 2.5 seconds for warnings (reduced from 3)
        1500;                        // 1.5 seconds for info (reduced from 2)
      
      timerRef.current = setTimeout(() => {
        handleClose()
      }, dismissTime)
    }
    
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
        timerRef.current = null
      }
    }
  }, [visible, type])

  const handleClose = () => {
    setVisible(false)
    setTimeout(onClose, 200) // Allow animation to complete
  }
  
  if (!isOpen && !visible) return null
  
  return (
    <div 
      className={`fixed top-2 right-2 z-50 max-w-xs rounded-lg shadow-xl transform transition-all duration-200 
                ${visible ? 'translate-x-0 opacity-90' : 'translate-x-full opacity-0'}`}
      onClick={(e) => e.stopPropagation()}
    >
      <div className={`bg-dark-800 border rounded-lg overflow-hidden ${
        type === 'error' ? 'border-red-600' : 
        type === 'warning' ? 'border-yellow-600' : 
        'border-blue-600'
      }`}>
        <div className={`px-4 py-3 flex items-center justify-between ${
          type === 'error' ? 'bg-red-900/20' : 
          type === 'warning' ? 'bg-yellow-900/20' : 
          'bg-blue-900/20'
        }`}>
          <div className="flex items-center">
            <AlertCircle className={`w-4 h-4 mr-2 ${
              type === 'error' ? 'text-red-500' : 
              type === 'warning' ? 'text-yellow-500' : 
              'text-blue-500'
            }`} />
            <h3 className="text-xs font-medium text-white/90">{title}</h3>
          </div>
          <button 
            onClick={handleClose}
            className="text-dark-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        {message && (
          <div className="px-4 py-2 border-t border-dark-700">
            <div className="text-xs text-dark-300/90 whitespace-pre-wrap">{message}</div>
          </div>
        )}
      </div>
    </div>
  )
}
