'use client'

import React, { useState, useEffect } from 'react'
import { Play, Square, Settings, AlertCircle, AlertTriangle } from 'lucide-react'
import { useAutomation } from '../hooks/useAutomation'
import { useError } from '../contexts/ErrorContext'

interface AutomationControlProps {
  isRunning: boolean
  setIsRunning: (running: boolean) => void
  setCurrentStep: (step: number) => void
}

export default function AutomationControl({ isRunning, setIsRunning, setCurrentStep }: AutomationControlProps) {
  const [steamAppId, setSteamAppId] = useState('')
  const [customVideoUrl, setCustomVideoUrl] = useState('')
  const [allkeyshopUrl, setAllkeyshopUrl] = useState('')
  const [mode, setMode] = useState<'steam'>('steam')
  const [error, setError] = useState<string | null>(null)
  
  const { startAutomation, stopJob, currentJob, isConnected } = useAutomation()
  const { showError, showWarning } = useError()

  const handleStart = async () => {
    try {
      setError(null)
      
      // Validate input
      if (!steamAppId.trim()) {
        setError('Steam App ID is required')
        showWarning('Validation Error', 'Steam App ID is required to run automation')
        return
      }
      
      // Connection check removed - allow starting even if temporarily disconnected
      // The system will attempt to reconnect automatically
      
      setIsRunning(true)
      
      // Prepare request for Steam App ID mode
      // IMPORTANT: Use exact field names matching the API expectations
      const request: {
        mode: 'steam' | 'single' | 'trending';
        steam_app_id: string;
        custom_video_url?: string;
        allkeyshop_url?: string;
      } = {
        mode: 'steam',  // Must be 'steam' as specified in API validation
        steam_app_id: steamAppId.trim()
      }
      
      // Only add custom_video_url if it's not empty
      if (customVideoUrl && customVideoUrl.trim()) {
        request.custom_video_url = customVideoUrl.trim()
      }
      
      // Add AllKeyShop URL if provided
      if (allkeyshopUrl && allkeyshopUrl.trim()) {
        request.allkeyshop_url = allkeyshopUrl.trim()
      }
      
      console.log('Sending request:', request)
      
      // Start the automation
      const jobId = await startAutomation(request)
      console.log('Started automation job:', jobId)
      
    } catch (error) {
      console.error('Error starting automation:', error)
      setError(error instanceof Error ? error.message : 'Failed to start automation')
      setIsRunning(false)
      
      // Error is already shown by useAutomation hook
    }
  }

  const handleStop = async () => {
    try {
      if (currentJob?.job_id) {
        await stopJob(currentJob.job_id)
      }
      setIsRunning(false)
      setCurrentStep(0)
    } catch (error) {
      console.error('Error stopping automation:', error)
    }
  }

  // Update local state based on current job
  React.useEffect(() => {
    if (currentJob) {
      setIsRunning(currentJob.status === 'running' || currentJob.status === 'queued')
      setCurrentStep(currentJob.current_step)
      
      if (currentJob.status === 'completed' || currentJob.status === 'failed') {
        setIsRunning(false)
        if (currentJob.status === 'failed') {
          setError(currentJob.error_message || 'Automation failed')
          showError('Automation Failed', currentJob.error_message || 'The operation failed during processing')
        }
      }
    }
  }, [currentJob, showError])
  
  // Connection status monitoring - DISABLED
  // Completely removed all connection warning notifications
  const [wasConnected, setWasConnected] = useState(false)
  
  useEffect(() => {
    // Silently track connection status but never show warnings
    // This allows us to maintain the connection state without bothering the user
    setWasConnected(isConnected)
  }, [isConnected])

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-xl font-bold text-white">Automation Control</h2>
        <div className="flex items-center space-x-2">
          <div className="relative group">
            <button className="btn-secondary text-xs flex items-center py-1.5 px-3 relative transition-colors">
              {/* More subtle connection status indicator */}
              <div className={`absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'} transition-colors`}>
                {/* Ultra-subtle pulse effect only when connected */}
                {isConnected && (
                  <span className="absolute inset-0 rounded-full bg-green-500 animate-ping opacity-25"></span>
                )}
              </div>
              
              <Settings className="w-3 h-3 mr-1" />
              <span>Config</span>
            </button>
            
            {/* Tooltip that shows on hover - positioned better */}
            <div className="absolute right-0 mt-1 bg-dark-800 text-xs px-2 py-1 rounded shadow-lg border border-dark-600 opacity-0 group-hover:opacity-100 transition-opacity z-10 text-center pointer-events-none whitespace-nowrap">
              <span className={`inline-block w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'} mr-1`}></span>
              {isConnected ? 'Server Connected' : 'Server Disconnected'}
            </div>
          </div>
        </div>
      </div>


      {/* Input Fields */}
      <div className="space-y-2 mb-2.5">
        <div>
          <label className="block text-sm font-medium text-white mb-1.5">Steam App ID</label>
          <input
            type="text"
            value={steamAppId}
            onChange={(e) => setSteamAppId(e.target.value)}
            placeholder="Enter Steam App ID (e.g., 1962700)"
            className="input-field w-full"
            disabled={isRunning}
          />
          <p className="text-xs text-dark-400 mt-1">Find Steam App IDs at steamdb.info</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-white mb-1.5">Custom Video URL (Optional)</label>
          <input
            type="url"
            value={customVideoUrl}
            onChange={(e) => setCustomVideoUrl(e.target.value)}
            placeholder="YouTube, Steam, or other video platform URL"
            className="input-field w-full"
            disabled={isRunning}
          />
          <p className="text-xs text-dark-400 mt-1">Leave empty to use Steam videos automatically</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-white mb-1.5">AllKeyShop URL (Optional)</label>
          <input
            type="url"
            value={allkeyshopUrl}
            onChange={(e) => setAllkeyshopUrl(e.target.value)}
            placeholder="https://www.allkeyshop.com/blog/buy-game-cd-key-compare-prices/"
            className="input-field w-full"
            disabled={isRunning}
          />
          <p className="text-xs text-dark-400 mt-1">For price comparison banner generation</p>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="mb-4 p-3 bg-red-600/10 border border-red-600/20 rounded-lg flex items-start space-x-2">
          <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm text-red-400 font-medium">
              {error.includes('Network Error') ? 'Connection Failed' : 'Error'}
            </p>
            <p className="text-sm text-red-400">
              {error.includes('Network Error') ? (
                <>
                  Cannot connect to API server. Please ensure:
                  <ul className="list-disc ml-4 mt-1 space-y-1">
                    <li>API server is running on port 8000</li>
                    <li>No firewall is blocking the connection</li>
                    <li>Try refreshing the page</li>
                  </ul>
                </>
              ) : (
                error
              )}
            </p>
            {!isConnected && (
              <div className="mt-2 text-xs text-red-400/70">
                <span className="font-medium">Status:</span> API server appears to be disconnected
              </div>
            )}
          </div>
        </div>
      )}
      
      {/* Network Status Display - Only show when disconnected */}
      {!error && !isConnected && (
        <div className="mb-4 p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg flex items-center space-x-2">
          <AlertTriangle className="w-4 h-4 text-yellow-400 flex-shrink-0" />
          <p className="text-sm text-yellow-400">
            API server disconnected. Attempting to reconnect...
          </p>
        </div>
      )}

      {/* Control Buttons */}
      <div className="flex space-x-3">
        {!isRunning ? (
          <button
            onClick={handleStart}
            disabled={!steamAppId}
            className="btn-primary flex-1 flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Play className="w-4 h-4 mr-2" />
            Start Automation
          </button>
        ) : (
          <button
            onClick={handleStop}
            className="bg-red-600 hover:bg-red-700 text-white font-medium py-2 px-4 rounded-lg transition-colors duration-200 flex-1 flex items-center justify-center"
          >
            <Square className="w-4 h-4 mr-2" />
            Stop Process
          </button>
        )}
        
        <button className="btn-secondary">
          <Settings className="w-4 h-4" />
        </button>
      </div>

    </div>
  )
}
