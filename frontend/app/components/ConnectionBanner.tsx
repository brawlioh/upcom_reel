'use client'

import React, { useEffect, useState } from 'react'
import { useAutomation } from '../hooks/useAutomation'
import { X } from 'lucide-react'

/**
 * ConnectionBanner component overrides the default connection lost notification
 * It intercepts and prevents displaying connection notifications
 */
export default function ConnectionBanner() {
  const { isConnected } = useAutomation()
  const [isVisible, setIsVisible] = useState(false)
  
  // Force the banner to never be visible, overriding any connection-related notifications
  useEffect(() => {
    // Reset any other banners or notifications by adding this to the DOM
    const resetNotifications = () => {
      // Find any connection notification banners and remove them
      const banners = document.querySelectorAll('[data-connection-banner]')
      banners.forEach(banner => {
        if (banner.parentNode) {
          banner.parentNode.removeChild(banner)
        }
      })

      // Find any elements containing text about connection lost
      const elements = document.querySelectorAll('.fixed, [role="alert"], [role="status"], [aria-live]')
      elements.forEach(el => {
        if (el.textContent?.includes('Connection to the server was lost') ||
            el.textContent?.includes('Connection Lost') ||
            el.textContent?.includes('server was lost')) {
          // Target the specific connection notification element
          if (el.parentElement && !el.getAttribute('data-preserved')) {
            // Use setAttribute for style instead of direct property access to avoid TypeScript errors
            el.setAttribute('style', 'display: none !important; visibility: hidden !important')
            el.setAttribute('data-preserved', 'true')
            
            // Also hide any parent that might be a notification container
            if (el.parentElement) {
              el.parentElement.setAttribute('style', 'display: none !important')
            }
          }
        }
      })
      
      // Specifically target the connection banner shown in the screenshot
      document.querySelectorAll('.fixed[role="alert"]').forEach(banner => {
        if (banner && !banner.getAttribute('data-preserved')) {
          banner.setAttribute('style', 'display: none !important')
          banner.setAttribute('data-preserved', 'true')
        }
      })
    }

    // Run immediately and then on an interval
    resetNotifications()
    const intervalId = setInterval(resetNotifications, 1000)
    
    return () => clearInterval(intervalId)
  }, [isConnected])
  
  // Return an empty div where the banner would be,
  // but make it invisible so it takes no space
  return (
    <div 
      className="hidden" 
      style={{ display: 'none', visibility: 'hidden', position: 'absolute' }}
      data-custom-banner="true"
    />
  )
}
